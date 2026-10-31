"""Relatórios de gestão: vendas do período, lucro por produto (curva ABC) e produtos parados."""

from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import Date, case, cast, func, literal_column, select
from sqlalchemy.orm import Session

from app.modules.auth.models import Usuario
from app.modules.devolucoes.models import Devolucao, ItemDevolucao
from app.modules.estoque.models import Lote
from app.modules.produtos.models import Produto
from app.modules.relatorios.schemas import (
    DiaVendas,
    FormaVendas,
    OperadorVendas,
    ProdutoParado,
    ProdutoVendido,
    RelatorioParados,
    RelatorioProdutos,
    RelatorioVendas,
    ResumoVendas,
)
from app.modules.vendas.models import Caixa, Venda, VendaItem, VendaPagamento
from app.shared.datas import FUSO, hoje

CENTAVO = Decimal("0.01")
ZERO = Decimal(0)


def _pct(parte: Decimal, todo: Decimal) -> Decimal:
    return (parte * 100 / todo).quantize(Decimal("0.1"), ROUND_HALF_UP) if todo else ZERO


def _dia_local():
    # Agrupa pela data local da venda, não pela data UTC. O fuso vai como texto fixo para o
    # GROUP BY reconhecer a mesma expressão do SELECT.
    return cast(func.timezone(literal_column(f"'{FUSO.key}'"), Venda.finalizada_em), Date)


def _vendas(inicio: date, fim: date, loja_id: UUID | None, status: str = "finalizada"):
    filtro = select(Venda.id).where(Venda.status == status, _dia_local().between(inicio, fim))
    if loja_id is not None:
        filtro = filtro.join(Caixa, Caixa.id == Venda.caixa_id).where(Caixa.loja_id == loja_id)
    return filtro


def _custo_item():
    """Custo do item: o gravado na venda; nas vendas antigas, o custo atual do produto."""
    return VendaItem.quantidade * func.coalesce(VendaItem.custo_unitario, Produto.preco_custo)


def _devolvido_por_venda(db: Session, vendas) -> list[tuple]:
    """(venda_id, valor devolvido, custo do que voltou ao estoque, nº de devoluções) das vendas.

    A devolução sai do dia da venda, como nas metas e comissões. O custo só sai do que voltou
    para o estoque: o que foi para descarte continua sendo custo (é perda da farmácia).
    """
    custo = func.coalesce(VendaItem.custo_unitario, Produto.preco_custo, 0)
    return db.execute(
        select(
            Devolucao.venda_id,
            func.sum(ItemDevolucao.valor),
            func.sum(case((ItemDevolucao.volta_estoque, ItemDevolucao.quantidade * custo), else_=0)),
            func.count(func.distinct(Devolucao.id)),
        )
        .join(ItemDevolucao, ItemDevolucao.devolucao_id == Devolucao.id)
        .join(VendaItem, VendaItem.id == ItemDevolucao.venda_item_id)
        .join(Produto, Produto.id == VendaItem.produto_id)
        .where(Devolucao.venda_id.in_(vendas))
        .group_by(Devolucao.venda_id)
    ).all()


def _resumo(db: Session, inicio: date, fim: date, loja_id: UUID | None) -> ResumoVendas:
    vendas = _vendas(inicio, fim, loja_id)
    quantidade, faturamento, descontos = db.execute(
        select(func.count(), func.coalesce(func.sum(Venda.total), 0), func.coalesce(func.sum(Venda.desconto), 0))
        .where(Venda.id.in_(vendas))
    ).one()
    promocao, custo, sem_custo = db.execute(
        select(
            func.coalesce(func.sum(VendaItem.desconto_promocao), 0),
            func.coalesce(func.sum(_custo_item()), 0),
            func.count().filter(func.coalesce(VendaItem.custo_unitario, Produto.preco_custo).is_(None)),
        )
        .join(Produto, Produto.id == VendaItem.produto_id)
        .where(VendaItem.venda_id.in_(vendas))
    ).one()
    canceladas, valor_cancelado = db.execute(
        select(func.count(), func.coalesce(func.sum(Venda.total), 0))
        .where(Venda.id.in_(_vendas(inicio, fim, loja_id, "cancelada")))
    ).one()
    devolvidas = _devolvido_por_venda(db, vendas)
    valor_devolvido = sum((valor for _, valor, _, _ in devolvidas), ZERO)
    faturamento -= valor_devolvido
    custo = Decimal(custo) - sum((Decimal(c) for _, _, c, _ in devolvidas), ZERO)
    custo = custo.quantize(CENTAVO, ROUND_HALF_UP)
    lucro = faturamento - custo
    return ResumoVendas(
        quantidade=quantidade,
        faturamento=faturamento,
        devolucoes=sum((n for _, _, _, n in devolvidas), 0),
        valor_devolvido=valor_devolvido,
        descontos=descontos,
        descontos_promocao=promocao,
        ticket_medio=(faturamento / quantidade).quantize(CENTAVO, ROUND_HALF_UP) if quantidade else ZERO,
        custo=custo,
        lucro_bruto=lucro,
        margem=_pct(lucro, faturamento),
        itens_sem_custo=sem_custo,
        canceladas=canceladas,
        valor_cancelado=valor_cancelado,
    )


def vendas(db: Session, inicio: date, fim: date, loja_id: UUID | None) -> RelatorioVendas:
    dias = (fim - inicio).days + 1
    anterior_fim = inicio - timedelta(days=1)
    finalizadas = _vendas(inicio, fim, loja_id)

    dia_local = _dia_local()
    por_dia = {
        dia: (quantidade, total)
        for dia, quantidade, total in db.execute(
            select(dia_local, func.count(), func.sum(Venda.total))
            .where(Venda.id.in_(finalizadas))
            .group_by(dia_local)
        )
    }
    # Devoluções saem do dia e do operador da venda.
    devolvido = (
        select(Venda.id.label("venda_id"), dia_local.label("dia"), Venda.usuario_id.label("usuario_id"),
               func.sum(Devolucao.valor_total).label("valor"))
        .join(Devolucao, Devolucao.venda_id == Venda.id)
        .where(Venda.id.in_(finalizadas))
        .group_by(Venda.id, dia_local, Venda.usuario_id)
    ).subquery()
    for dia, valor in db.execute(select(devolvido.c.dia, func.sum(devolvido.c.valor)).group_by(devolvido.c.dia)):
        quantidade, total = por_dia[dia]
        por_dia[dia] = (quantidade, total - valor)
    devolvido_por_operador = dict(db.execute(
        select(Usuario.nome, func.sum(devolvido.c.valor))
        .join(Usuario, Usuario.id == devolvido.c.usuario_id)
        .group_by(Usuario.nome)
    ).all())
    # Troco sai do dinheiro: o que ficou na gaveta é o pago menos o troco.
    troco = db.scalar(select(func.coalesce(func.sum(Venda.troco), 0)).where(Venda.id.in_(finalizadas)))
    formas = dict(
        db.execute(
            select(VendaPagamento.forma, func.sum(VendaPagamento.valor))
            .where(VendaPagamento.venda_id.in_(finalizadas))
            .group_by(VendaPagamento.forma)
        ).all()
    )
    if "dinheiro" in formas:
        formas["dinheiro"] -= troco
    operadores = db.execute(
        select(Usuario.nome, func.count(), func.sum(Venda.total))
        .join(Usuario, Usuario.id == Venda.usuario_id)
        .where(Venda.id.in_(finalizadas))
        .group_by(Usuario.nome)
        .order_by(func.sum(Venda.total).desc())
    ).all()

    return RelatorioVendas(
        inicio=inicio,
        fim=fim,
        resumo=_resumo(db, inicio, fim, loja_id),
        anterior=_resumo(db, anterior_fim - timedelta(days=dias - 1), anterior_fim, loja_id),
        por_dia=[
            DiaVendas(data=dia, quantidade=por_dia.get(dia, (0, ZERO))[0], total=por_dia.get(dia, (0, ZERO))[1])
            for dia in (inicio + timedelta(days=i) for i in range(dias))
        ],
        por_forma=[FormaVendas(forma=f, valor=v) for f, v in sorted(formas.items(), key=lambda x: -x[1])],
        por_operador=sorted(
            (OperadorVendas(nome=n, quantidade=q, total=t - devolvido_por_operador.get(n, ZERO)) for n, q, t in operadores),
            key=lambda o: -o.total,
        ),
    )


def produtos(db: Session, inicio: date, fim: date, loja_id: UUID | None) -> RelatorioProdutos:
    linhas = db.execute(
        select(
            VendaItem.produto_id,
            Produto.nome,
            Produto.apresentacao,
            func.sum(VendaItem.quantidade),
            func.sum(VendaItem.total),
            func.sum(_custo_item()),
            func.count().filter(func.coalesce(VendaItem.custo_unitario, Produto.preco_custo).is_(None)),
        )
        .join(Produto, Produto.id == VendaItem.produto_id)
        .where(VendaItem.venda_id.in_(_vendas(inicio, fim, loja_id)))
        .group_by(VendaItem.produto_id, Produto.nome, Produto.apresentacao)
        .order_by(func.sum(VendaItem.total).desc())
    ).all()
    # Tira o que voltou: a quantidade e a parte do valor do item; o custo, só do que voltou ao estoque.
    custo_unitario = func.coalesce(VendaItem.custo_unitario, Produto.preco_custo, 0)
    devolvidos = {
        produto_id: (quantidade, valor, custo)
        for produto_id, quantidade, valor, custo in db.execute(
            select(
                VendaItem.produto_id,
                func.sum(ItemDevolucao.quantidade),
                func.sum(VendaItem.total * ItemDevolucao.quantidade / VendaItem.quantidade),
                func.sum(case((ItemDevolucao.volta_estoque, ItemDevolucao.quantidade * custo_unitario), else_=0)),
            )
            .join(VendaItem, VendaItem.id == ItemDevolucao.venda_item_id)
            .join(Produto, Produto.id == VendaItem.produto_id)
            .where(VendaItem.venda_id.in_(_vendas(inicio, fim, loja_id)))
            .group_by(VendaItem.produto_id)
        )
    }
    ajustadas = []
    for produto_id, nome, apresentacao, quantidade, faturamento, custo, sem_custo in linhas:
        qtd_dev, valor_dev, custo_dev = devolvidos.get(produto_id, (ZERO, ZERO, ZERO))
        faturamento = faturamento - Decimal(valor_dev).quantize(CENTAVO, ROUND_HALF_UP)
        custo = Decimal(custo) - Decimal(custo_dev) if custo is not None else None
        if quantidade - qtd_dev > 0:
            ajustadas.append((produto_id, nome, apresentacao, quantidade - qtd_dev, faturamento, custo, sem_custo))
    linhas = sorted(ajustadas, key=lambda linha: -linha[4])
    total = sum((linha[4] for linha in linhas), ZERO)

    # Curva ABC: os que somam 80% do faturamento são A, até 95% são B, o resto é C.
    resultado, acumulado = [], ZERO
    for produto_id, nome, apresentacao, quantidade, faturamento, custo, sem_custo in linhas:
        participacao = _pct(faturamento, total)
        curva = "A" if acumulado < total * Decimal("0.8") else "B" if acumulado < total * Decimal("0.95") else "C"
        acumulado += faturamento
        # Sem custo em algum item, o lucro do produto ficaria errado: não mostra.
        custo = None if sem_custo else Decimal(custo).quantize(CENTAVO, ROUND_HALF_UP)
        lucro = faturamento - custo if custo is not None else None
        resultado.append(
            ProdutoVendido(
                produto_id=produto_id,
                nome=nome if not apresentacao else f"{nome} {apresentacao}",
                quantidade=quantidade,
                faturamento=faturamento,
                custo=custo,
                lucro=lucro,
                margem=_pct(lucro, faturamento) if lucro is not None else None,
                participacao=participacao,
                curva=curva,
            )
        )
    return RelatorioProdutos(
        inicio=inicio,
        fim=fim,
        faturamento=total,
        produtos=resultado,
        curva_a=sum(1 for p in resultado if p.curva == "A"),
        curva_b=sum(1 for p in resultado if p.curva == "B"),
        curva_c=sum(1 for p in resultado if p.curva == "C"),
    )


def parados(db: Session, dias: int, loja_id: UUID | None) -> RelatorioParados:
    """Produtos com estoque que não vendem há `dias` dias (ou nunca venderam): dinheiro parado na prateleira."""
    estoque = select(
        Lote.produto_id,
        func.sum(Lote.quantidade).label("saldo"),
        func.min(Lote.validade).label("validade"),
    ).where(Lote.quantidade > 0)
    if loja_id is not None:
        estoque = estoque.where(Lote.loja_id == loja_id)
    estoque = estoque.group_by(Lote.produto_id).subquery()

    vendidas = select(VendaItem.produto_id, func.max(Venda.finalizada_em).label("ultima")).join(
        Venda, Venda.id == VendaItem.venda_id
    ).where(Venda.status == "finalizada")
    if loja_id is not None:
        vendidas = vendidas.join(Caixa, Caixa.id == Venda.caixa_id).where(Caixa.loja_id == loja_id)
    vendidas = vendidas.group_by(VendaItem.produto_id).subquery()

    limite = datetime.now(FUSO) - timedelta(days=dias)
    linhas = db.execute(
        select(Produto, estoque.c.saldo, estoque.c.validade, vendidas.c.ultima)
        .join(estoque, estoque.c.produto_id == Produto.id)
        .outerjoin(vendidas, vendidas.c.produto_id == Produto.id)
        .where(Produto.ativo.is_(True), (vendidas.c.ultima.is_(None)) | (vendidas.c.ultima < limite))
        .order_by((estoque.c.saldo * func.coalesce(Produto.preco_custo, 0)).desc(), Produto.nome)
    ).all()

    resultado = []
    for produto, saldo, validade, ultima in linhas:
        valor = (saldo * produto.preco_custo).quantize(CENTAVO, ROUND_HALF_UP) if produto.preco_custo is not None else None
        resultado.append(
            ProdutoParado(
                produto_id=produto.id,
                nome=produto.nome if not produto.apresentacao else f"{produto.nome} {produto.apresentacao}",
                saldo=saldo,
                custo_unitario=produto.preco_custo,
                valor_parado=valor,
                ultima_venda=ultima,
                dias_parado=(hoje() - ultima.astimezone(FUSO).date()).days if ultima else None,
                validade_mais_proxima=validade,
            )
        )
    return RelatorioParados(
        dias=dias,
        produtos=resultado,
        valor_total=sum((p.valor_parado or ZERO for p in resultado), ZERO),
    )
