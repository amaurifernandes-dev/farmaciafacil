"""Troca e devolução de itens: o cliente traz parte da compra de volta.

O valor de cada item é o que o cliente pagou por ele (os descontos da venda inteira são
divididos entre os itens, e a taxa de entrega não volta). O produto volta ao mesmo lote de
onde saiu, menos remédio, que não pode voltar para a prateleira e vira descarte.
"""

import secrets
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.security import TokenDados
from app.modules.auth.models import Usuario
from app.modules.clientes.models import Cliente
from app.modules.devolucoes.integracao import vale_pelo_codigo
from app.modules.devolucoes.models import Devolucao, ItemDevolucao, ValeTroca
from app.modules.devolucoes.schemas import (
    DevolucaoCriar,
    DevolucaoSaida,
    ItemDevolucaoSaida,
    ItemDevolvivel,
    ListaDevolucoes,
    ValeSaida,
    VendaParaDevolver,
)
from app.modules.estoque.models import Lote, MovimentoEstoque
from app.modules.estoque.service import Referencia, devolver_ao_lote
from app.modules.fidelidade.service import acertar_devolucao
from app.modules.lojas.models import Loja, Terminal
from app.modules.lojas.service import matriz
from app.modules.produtos.models import Produto
from app.modules.vendas.models import Caixa, Venda, VendaItem
from app.modules.vendas.service import caixa_para_vender
from app.shared.datas import FUSO, hoje
from app.shared.erros import ErroDeNegocio, NaoEncontrado

ZERO = Decimal(0)
CENTAVO = Decimal("0.01")
VALIDADE_VALE_DIAS = 90
LETRAS_DO_VALE = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem 0/O e 1/I, que se confundem
# Essas formas têm conta a receber, convênio ou governo por trás: só cancelando a venda inteira.
FORMAS_SEM_DEVOLUCAO = {
    "prazo": "a prazo (fiado)",
    "convenio": "no convênio",
    "popular": "pela Farmácia Popular",
}


# --- Cálculo ---

def _liquido_por_item(venda: Venda) -> dict[UUID, Decimal]:
    """Quanto o cliente pagou por cada linha, com o desconto da venda inteira dividido entre elas."""
    soma = sum((i.total for i in venda.itens), ZERO)
    pago = venda.total - venda.taxa_entrega
    fator = min(pago / soma, Decimal(1)) if soma > 0 else ZERO
    return {i.id: (i.total * fator).quantize(CENTAVO, ROUND_HALF_UP) for i in venda.itens}


def _ja_devolvido(db: Session, venda: Venda) -> dict[UUID, tuple[Decimal, Decimal]]:
    """{venda_item_id: (quantidade, valor)} já devolvidos em devoluções anteriores."""
    linhas = db.execute(
        select(ItemDevolucao.venda_item_id, func.sum(ItemDevolucao.quantidade), func.sum(ItemDevolucao.valor))
        .where(ItemDevolucao.venda_item_id.in_([i.id for i in venda.itens]))
        .group_by(ItemDevolucao.venda_item_id)
    ).all()
    return {item_id: (qtd, valor) for item_id, qtd, valor in linhas}


def _bloqueio_da_venda(venda: Venda) -> str | None:
    if venda.status != "finalizada":
        return "Esta venda foi cancelada"
    for pagamento in venda.pagamentos:
        if pagamento.forma in FORMAS_SEM_DEVOLUCAO:
            return (
                f"Esta venda foi paga {FORMAS_SEM_DEVOLUCAO[pagamento.forma]}. "
                "Para desfazer, um gerente precisa cancelar a venda inteira."
            )
    return None


def _bloqueio_do_produto(produto: Produto) -> str | None:
    if produto.controle:
        return "Remédio controlado não pode ser trocado: a saída já foi informada à Anvisa (SNGPC)"
    return None


def _sugere_voltar(produto: Produto) -> bool:
    # Remédio que saiu da farmácia não volta para a venda (não dá para garantir como foi guardado).
    return produto.tipo != "medicamento"


# --- Consulta ---

def _venda(db: Session, venda_id: UUID | None, numero: int | None) -> Venda:
    if venda_id is not None:
        venda = db.get(Venda, venda_id)
    elif numero is not None:
        venda = db.scalar(select(Venda).where(Venda.numero == numero))
    else:
        raise ErroDeNegocio("Informe o número da venda")
    if venda is None:
        raise NaoEncontrado(f"Venda nº {numero} não encontrada" if numero else "Venda não encontrada")
    return venda


def para_devolver(db: Session, venda_id: UUID | None = None, numero: int | None = None) -> VendaParaDevolver:
    venda = _venda(db, venda_id, numero)
    liquido = _liquido_por_item(venda)
    devolvido = _ja_devolvido(db, venda)
    produtos = {p.id: p for p in db.scalars(select(Produto).where(Produto.id.in_([i.produto_id for i in venda.itens])))}
    itens = []
    for item in venda.itens:
        produto = produtos[item.produto_id]
        qtd_dev, _ = devolvido.get(item.id, (ZERO, ZERO))
        itens.append(ItemDevolvivel(
            venda_item_id=item.id, produto_id=item.produto_id, descricao=item.descricao, tipo_produto=produto.tipo,
            quantidade=item.quantidade, devolvida=qtd_dev, disponivel=item.quantidade - qtd_dev,
            valor_pago=liquido[item.id],
            valor_unitario=(liquido[item.id] / item.quantidade).quantize(CENTAVO, ROUND_HALF_UP),
            bloqueio=_bloqueio_do_produto(produto), volta_estoque_sugerido=_sugere_voltar(produto),
        ))
    bloqueio = _bloqueio_da_venda(venda)
    if bloqueio is None and all(i.disponivel <= 0 for i in itens):
        bloqueio = "Todos os itens desta venda já foram devolvidos"
    cliente = db.get(Cliente, venda.cliente_id) if venda.cliente_id else None
    anteriores = db.scalars(select(Devolucao).where(Devolucao.venda_id == venda.id).order_by(Devolucao.numero)).all()
    return VendaParaDevolver(
        venda_id=venda.id, numero=venda.numero, finalizada_em=venda.finalizada_em, status=venda.status,
        total=venda.total, cliente_id=venda.cliente_id, cliente_nome=cliente.nome if cliente else None,
        formas=sorted({p.forma for p in venda.pagamentos}), bloqueio=bloqueio, itens=itens,
        devolucoes=_saidas(db, anteriores),
    )


def _status_vale(vale: ValeTroca) -> str:
    if vale.status == "ativo" and vale.validade < hoje():
        return "vencido"
    return vale.status


def saida_vale(db: Session, vale: ValeTroca, clientes: dict | None = None) -> ValeSaida:
    nome = None
    if vale.cliente_id:
        nome = clientes[vale.cliente_id] if clientes is not None else db.get(Cliente, vale.cliente_id).nome
    return ValeSaida(
        id=vale.id, codigo=vale.codigo, valor=vale.valor, saldo=vale.saldo, validade=vale.validade,
        status=_status_vale(vale), cliente_id=vale.cliente_id, cliente_nome=nome, criado_em=vale.criado_em,
    )


def _saidas(db: Session, devolucoes: list[Devolucao]) -> list[DevolucaoSaida]:
    if not devolucoes:
        return []
    usuarios = dict(db.execute(select(Usuario.id, Usuario.nome)).all())
    lojas = dict(db.execute(select(Loja.id, Loja.nome)).all())
    vendas = dict(db.execute(
        select(Venda.id, Venda.numero).where(Venda.id.in_({d.venda_id for d in devolucoes}))
    ).all())
    ids_clientes = {d.vale.cliente_id for d in devolucoes if d.vale and d.vale.cliente_id}
    clientes = dict(db.execute(select(Cliente.id, Cliente.nome).where(Cliente.id.in_(ids_clientes))).all()) \
        if ids_clientes else {}
    return [
        DevolucaoSaida(
            id=d.id, numero=d.numero, venda_id=d.venda_id, venda_numero=vendas[d.venda_id], loja_id=d.loja_id,
            loja=lojas[d.loja_id],
            usuario=usuarios[d.usuario_id], destino=d.destino, valor_total=d.valor_total, pontos=d.pontos,
            motivo=d.motivo,
            criado_em=d.criado_em, itens=[ItemDevolucaoSaida.model_validate(i) for i in d.itens],
            vale=saida_vale(db, d.vale, clientes) if d.vale else None,
        )
        for d in devolucoes
    ]


def obter(db: Session, devolucao_id: UUID) -> DevolucaoSaida:
    devolucao = db.get(Devolucao, devolucao_id)
    if devolucao is None:
        raise NaoEncontrado("Devolução não encontrada")
    return _saidas(db, [devolucao])[0]


def listar(db: Session, inicio: date, fim: date, loja_id: UUID | None) -> ListaDevolucoes:
    de = datetime.combine(inicio, time.min, FUSO)
    ate = datetime.combine(fim + timedelta(days=1), time.min, FUSO)
    consulta = select(Devolucao).where(Devolucao.criado_em >= de, Devolucao.criado_em < ate)
    if loja_id is not None:
        consulta = consulta.where(Devolucao.loja_id == loja_id)
    devolucoes = db.scalars(consulta.order_by(Devolucao.numero.desc())).all()
    totais: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for d in devolucoes:
        totais[d.destino] += d.valor_total
    return ListaDevolucoes(
        itens=_saidas(db, devolucoes), quantidade=len(devolucoes), total=totais["dinheiro"] + totais["vale"],
        em_dinheiro=totais["dinheiro"], em_vale=totais["vale"],
    )


# --- Registrar ---

def _novo_codigo(db: Session) -> str:
    while True:
        codigo = "".join(secrets.choice(LETRAS_DO_VALE) for _ in range(8))
        if db.scalar(select(ValeTroca.id).where(ValeTroca.codigo == codigo)) is None:
            return codigo


def _voltar_ao_estoque(db: Session, usuario_id: UUID, item: VendaItem, devolvido: ItemDevolucao, motivo: str) -> None:
    """Põe a quantidade de volta nos lotes de onde ela saiu na venda, sem passar do que saiu de cada um."""
    # Na mesma ordem em que a venda tirou (FEFO: o que vence antes primeiro).
    saidas = db.scalars(
        select(MovimentoEstoque)
        .join(Lote, Lote.id == MovimentoEstoque.lote_id)
        .where(MovimentoEstoque.referencia_tipo == "venda_item", MovimentoEstoque.referencia_id == item.id)
        .order_by(Lote.validade.asc().nulls_last(), Lote.id)
    ).all()
    anteriores = select(ItemDevolucao.id).where(ItemDevolucao.venda_item_id == item.id)
    ja_voltou = dict(db.execute(
        select(MovimentoEstoque.lote_id, func.sum(MovimentoEstoque.quantidade))
        .where(MovimentoEstoque.referencia_tipo == "devolucao_item", MovimentoEstoque.referencia_id.in_(anteriores))
        .group_by(MovimentoEstoque.lote_id)
    ).all())
    falta = devolvido.quantidade
    for saida in saidas:
        cabe = -saida.quantidade - ja_voltou.get(saida.lote_id, ZERO)
        if cabe <= 0:
            continue
        por = min(cabe, falta)
        devolver_ao_lote(db, saida.lote_id, por, usuario_id, Referencia("devolucao_item", devolvido.id), motivo)
        ja_voltou[saida.lote_id] = ja_voltou.get(saida.lote_id, ZERO) + por
        falta -= por
        if falta <= 0:
            return
    # Venda sem movimento de estoque (não deveria acontecer): não inventa lote, só não devolve.


def registrar(db: Session, usuario: TokenDados, terminal: Terminal | None, dados: DevolucaoCriar) -> DevolucaoSaida:
    venda = db.scalar(select(Venda).where(Venda.id == dados.venda_id).with_for_update(of=Venda))
    if venda is None:
        raise NaoEncontrado("Venda não encontrada")
    bloqueio = _bloqueio_da_venda(venda)
    if bloqueio:
        raise ErroDeNegocio(bloqueio)

    caixa_id = None
    if dados.destino == "dinheiro" and any(p.forma == "vale" for p in venda.pagamentos):
        raise ErroDeNegocio("Esta venda foi paga com vale-troca: a devolução também precisa ser em vale")
    if dados.destino == "dinheiro":
        try:
            caixa_id = caixa_para_vender(db, usuario, terminal).id
        except ErroDeNegocio:
            raise ErroDeNegocio(
                "Para devolver em dinheiro, faça a devolução num PDV com o caixa aberto. Ou gere um vale-troca."
            )

    itens_da_venda = {i.id: i for i in venda.itens}
    liquido = _liquido_por_item(venda)
    devolvido = _ja_devolvido(db, venda)
    pedidos: dict[UUID, Decimal] = defaultdict(lambda: ZERO)
    for entrada in dados.itens:
        if entrada.venda_item_id not in itens_da_venda:
            raise ErroDeNegocio("Este item não é desta venda")
        pedidos[entrada.venda_item_id] += entrada.quantidade
    volta = {e.venda_item_id: e.volta_estoque for e in dados.itens}

    caixa = db.get(Caixa, venda.caixa_id)
    loja_id = caixa.loja_id or matriz(db).id
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext('devolucao:' || current_setting('app.farmacia_id')))"))
    devolucao = Devolucao(
        numero=(db.scalar(select(func.max(Devolucao.numero))) or 0) + 1,
        venda_id=venda.id, loja_id=loja_id, usuario_id=usuario.usuario_id, destino=dados.destino,
        caixa_id=caixa_id, motivo=dados.motivo.strip(), valor_total=ZERO,
    )
    total = ZERO
    para_estoque = []
    for item_id, quantidade in pedidos.items():
        item = itens_da_venda[item_id]
        produto = db.get(Produto, item.produto_id)
        motivo_produto = _bloqueio_do_produto(produto)
        if motivo_produto:
            raise ErroDeNegocio(f"{item.descricao}: {motivo_produto}")
        qtd_dev, valor_dev = devolvido.get(item_id, (ZERO, ZERO))
        disponivel = item.quantidade - qtd_dev
        if quantidade > disponivel:
            if disponivel <= 0:
                raise ErroDeNegocio(f"{item.descricao} já foi devolvido")
            raise ErroDeNegocio(f"De {item.descricao} só dá para devolver {disponivel:g}")
        if quantidade == disponivel:
            valor = liquido[item_id] - valor_dev  # o último pega os centavos que sobraram
        else:
            valor = (liquido[item_id] * quantidade / item.quantidade).quantize(CENTAVO, ROUND_HALF_UP)
        voltar = volta[item_id] if volta[item_id] is not None else _sugere_voltar(produto)
        linha = ItemDevolucao(
            venda_item_id=item_id, produto_id=item.produto_id, descricao=item.descricao, quantidade=quantidade,
            valor=valor, volta_estoque=voltar,
        )
        devolucao.itens.append(linha)
        total += valor
        if voltar:
            para_estoque.append((item, linha))
    devolucao.valor_total = total

    if dados.destino == "vale":
        if total <= 0:
            raise ErroDeNegocio("O valor a devolver é zero: não dá para gerar vale")
        vale = ValeTroca(
            codigo=_novo_codigo(db), cliente_id=venda.cliente_id, valor=total, saldo=total,
            validade=hoje() + timedelta(days=VALIDADE_VALE_DIAS), status="ativo",
        )
        db.add(vale)
        db.flush()
        devolucao.vale_id = vale.id

    motivo = f"Devolução {devolucao.numero} da venda {venda.numero}"
    ja_devolvido = sum((valor for _, valor in devolvido.values()), ZERO)
    devolucao.pontos = acertar_devolucao(db, usuario.usuario_id, venda, ja_devolvido + total, motivo)
    db.add(devolucao)
    db.flush()  # gera os ids dos itens para referenciar nos movimentos
    for item, linha in para_estoque:
        _voltar_ao_estoque(db, usuario.usuario_id, item, linha, motivo)
    db.commit()
    db.refresh(devolucao)
    return obter(db, devolucao.id)


def consultar_vale(db: Session, codigo: str) -> ValeSaida:
    return saida_vale(db, vale_pelo_codigo(db, codigo))
