from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import TokenDados
from app.modules.auth.models import Usuario
from app.modules.estoque.models import MovimentoEstoque
from app.modules.estoque.service import Referencia, baixar_fefo, devolver_movimento
from app.modules.clientes.models import Cliente
from app.modules.farmacias.models import Farmacia
from app.modules.fidelidade.service import desconto_do_resgate, estornar_da_venda, pontuar_venda
from app.modules.financeiro.service import cancelar_fiado_da_venda, lancar_fiado, recebido_no_caixa
from app.modules.lojas.models import Loja, Terminal
from app.modules.lojas.service import matriz, obter_loja, pode_receber
from app.modules.produtos.models import Produto
from app.modules.promocoes.service import melhor, vigentes_por_produto
from app.modules.vendas.models import Caixa, PreVenda, Venda, VendaItem, VendaPagamento
from app.modules.vendas.schemas import CaixaSaida, PreVendaCriar, PreVendaSaida, ResumoCaixa, VendaCriar
from app.shared.erros import Conflito, ErroDeNegocio, NaoEncontrado, SemPermissao

CENTAVO = Decimal("0.01")
GERENTES = ("admin", "gerente")
OPERADORES = ("admin", "gerente", "farmaceutico", "caixa")


def _agora() -> datetime:
    return datetime.now(timezone.utc)


# --- Caixa ---

def caixa_do_terminal(db: Session, terminal: Terminal) -> Caixa | None:
    return db.scalar(select(Caixa).where(Caixa.terminal_id == terminal.id, Caixa.status == "aberto"))


def caixa_do_usuario(db: Session, usuario_id: UUID) -> Caixa | None:
    return db.scalar(select(Caixa).where(Caixa.usuario_id == usuario_id, Caixa.status == "aberto"))


def _exigir_terminal(terminal: Terminal | None) -> Terminal:
    if terminal is None:
        raise ErroDeNegocio(
            "Este computador não está registrado como PDV. Peça a um gerente para registrá-lo em Caixas."
        )
    return terminal


def abrir_caixa(db: Session, usuario: TokenDados, terminal: Terminal | None, valor_abertura: Decimal) -> Caixa:
    terminal = _exigir_terminal(terminal)
    if usuario.papel not in OPERADORES:
        raise SemPermissao("Seu perfil não pode abrir caixa")
    loja = db.get(Loja, terminal.loja_id)
    motivo = pode_receber(loja, terminal)
    if motivo:
        raise ErroDeNegocio(motivo)
    if caixa_do_terminal(db, terminal) is not None:
        raise Conflito(f"O {terminal.nome} já tem um caixa aberto")
    if caixa_do_usuario(db, usuario.usuario_id) is not None:
        raise Conflito("Você já tem um caixa aberto em outro PDV. Feche-o antes de abrir este.")
    caixa = Caixa(
        usuario_id=usuario.usuario_id,
        terminal_id=terminal.id,
        loja_id=loja.id,
        valor_abertura=valor_abertura,
        aberto_em=_agora(),
    )
    db.add(caixa)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflito("Este PDV ou este operador já tem um caixa aberto")
    return caixa


def caixa_para_vender(db: Session, usuario: TokenDados, terminal: Terminal | None) -> Caixa:
    """O caixa aberto deste PDV, desde que o operador possa usá-lo."""
    terminal = _exigir_terminal(terminal)
    caixa = caixa_do_terminal(db, terminal)
    if caixa is None:
        raise ErroDeNegocio("Abra o caixa antes de vender")
    if caixa.usuario_id != usuario.usuario_id and usuario.papel not in GERENTES:
        raise SemPermissao("Este caixa foi aberto por outro operador. Feche-o antes de abrir o seu.")
    return caixa


def obter_caixa(db: Session, caixa_id: UUID) -> Caixa:
    caixa = db.get(Caixa, caixa_id)
    if caixa is None:
        raise NaoEncontrado("Caixa não encontrado")
    return caixa


def listar_caixas(db: Session, status: str | None, pagina: int, por_pagina: int) -> list[ResumoCaixa]:
    filtro = select(Caixa)
    if status:
        filtro = filtro.where(Caixa.status == status)
    caixas = db.scalars(
        filtro.order_by(Caixa.aberto_em.desc()).offset((pagina - 1) * por_pagina).limit(por_pagina)
    ).all()
    return [resumo_caixa(db, caixa) for caixa in caixas]


def resumo_caixa(db: Session, caixa: Caixa) -> ResumoCaixa:
    finalizadas = select(Venda.id).where(Venda.caixa_id == caixa.id, Venda.status == "finalizada")
    quantidade, total, troco = db.execute(
        select(func.count(), func.coalesce(func.sum(Venda.total), 0), func.coalesce(func.sum(Venda.troco), 0))
        .where(Venda.id.in_(finalizadas))
    ).one()
    por_forma = dict(
        db.execute(
            select(VendaPagamento.forma, func.sum(VendaPagamento.valor))
            .where(VendaPagamento.venda_id.in_(finalizadas))
            .group_by(VendaPagamento.forma)
        ).all()
    )
    # Fiado recebido em dinheiro neste caixa também está na gaveta.
    recebimentos = recebido_no_caixa(db, caixa.id)
    esperado = caixa.valor_abertura + por_forma.get("dinheiro", Decimal(0)) - troco + recebimentos
    diferenca = None
    if caixa.valor_fechamento_informado is not None:
        diferenca = caixa.valor_fechamento_informado - esperado
    terminal = db.get(Terminal, caixa.terminal_id) if caixa.terminal_id else None
    loja = db.get(Loja, caixa.loja_id) if caixa.loja_id else None
    return ResumoCaixa(
        caixa=CaixaSaida.model_validate(caixa),
        operador=db.get(Usuario, caixa.usuario_id).nome,
        terminal=terminal.nome if terminal else None,
        loja=loja.nome if loja else None,
        quantidade_vendas=quantidade,
        total_vendido=total,
        por_forma=por_forma,
        recebimentos_dinheiro=recebimentos,
        dinheiro_esperado=esperado,
        diferenca=diferenca,
    )


def fechar_caixa(db: Session, usuario: TokenDados, caixa_id: UUID, valor_informado: Decimal) -> ResumoCaixa:
    caixa = obter_caixa(db, caixa_id)
    if caixa.usuario_id != usuario.usuario_id and usuario.papel not in GERENTES:
        raise SemPermissao("Só o próprio operador ou um gerente pode fechar este caixa")
    if caixa.status != "aberto":
        raise Conflito("Este caixa já está fechado")
    caixa.status = "fechado"
    caixa.fechado_em = _agora()
    caixa.valor_fechamento_informado = valor_informado
    resumo = resumo_caixa(db, caixa)
    db.commit()
    return resumo


# --- Venda ---

def _proximo_numero(db: Session) -> int:
    # Trava por farmácia durante a transação, para dois caixas não pegarem o mesmo número.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(current_setting('app.farmacia_id')))"))
    return db.scalar(select(func.coalesce(func.max(Venda.numero), 0) + 1))


def _venda_pela_chave(db: Session, chave: UUID) -> Venda | None:
    return db.scalar(select(Venda).where(Venda.chave_idempotencia == chave))


def registrar_venda(
    db: Session, usuario: TokenDados, terminal: Terminal | None, dados: VendaCriar
) -> tuple[Venda, bool]:
    """Grava a venda, baixa o estoque e registra os pagamentos numa transação só.

    Devolve (venda, criada). Se a chave já foi usada, devolve a venda existente e criada=False.
    """
    existente = _venda_pela_chave(db, dados.chave_idempotencia)
    if existente is not None:
        return existente, False

    caixa = caixa_para_vender(db, usuario, terminal)
    pre_venda = _pre_venda_para_receber(db, dados.pre_venda_id) if dados.pre_venda_id else None

    if dados.cliente_id is not None and db.get(Cliente, dados.cliente_id) is None:
        raise NaoEncontrado("Cliente não encontrado")
    venda = Venda(
        caixa_id=caixa.id,
        usuario_id=usuario.usuario_id,
        chave_idempotencia=dados.chave_idempotencia,
        cliente_cpf=dados.cliente_cpf,
        cliente_id=dados.cliente_id,
        finalizada_em=_agora(),
    )

    # Caixas antigos, de antes das lojas, vendem do estoque da matriz.
    loja_id = caixa.loja_id or matriz(db).id
    promocoes = vigentes_por_produto(db, [i.produto_id for i in dados.itens], loja_id)

    subtotal = Decimal(0)
    descontos = dados.desconto
    manuais = dados.desconto  # só o desconto dado pelo operador conta no limite do caixa
    for ordem, entrada in enumerate(dados.itens, start=1):
        produto = db.get(Produto, entrada.produto_id)
        if produto is None or not produto.ativo:
            raise NaoEncontrado("Produto não encontrado")
        bruto = (produto.preco_venda * entrada.quantidade).quantize(CENTAVO)
        promocao, desconto_promocao = melhor(
            promocoes.get(produto.id, []), produto.preco_venda, entrada.quantidade, dados.cliente_id is not None
        )
        if entrada.desconto + desconto_promocao > bruto:
            raise ErroDeNegocio(f"Desconto maior que o valor de {produto.nome}")
        desconto_item = entrada.desconto + desconto_promocao
        venda.itens.append(
            VendaItem(
                ordem=ordem,
                produto_id=produto.id,
                descricao=produto.nome if not produto.apresentacao else f"{produto.nome} {produto.apresentacao}",
                quantidade=entrada.quantidade,
                preco_unitario=produto.preco_venda,
                desconto=desconto_item,
                total=bruto - desconto_item,
                custo_unitario=produto.preco_custo,
                promocao_id=promocao.id if promocao else None,
                desconto_promocao=desconto_promocao,
            )
        )
        subtotal += bruto
        descontos += desconto_item
        manuais += entrada.desconto

    if descontos > subtotal:
        raise ErroDeNegocio("Desconto maior que o valor da venda")
    farmacia = db.get(Farmacia, usuario.farmacia_id)
    maximo = farmacia.desconto_maximo_caixa
    if usuario.papel not in GERENTES and subtotal > 0 and manuais * 100 / subtotal > maximo:
        raise SemPermissao(f"Desconto acima de {maximo:g}% precisa de um gerente")

    # A troca de pontos vira desconto, mas não conta no limite de desconto do caixa.
    if dados.pontos_resgatados:
        desconto_pontos = desconto_do_resgate(db, farmacia, dados.cliente_id, dados.pontos_resgatados)
        if descontos + desconto_pontos > subtotal:
            raise ErroDeNegocio("Os pontos valem mais que o restante da compra. Use menos pontos.")
        venda.pontos_resgatados = dados.pontos_resgatados
        venda.desconto_pontos = desconto_pontos
        descontos += desconto_pontos

    venda.subtotal = subtotal
    venda.desconto = descontos
    venda.total = subtotal - descontos

    pago = sum((p.valor for p in dados.pagamentos), Decimal(0))
    em_dinheiro = sum((p.valor for p in dados.pagamentos if p.forma == "dinheiro"), Decimal(0))
    if pago < venda.total:
        raise ErroDeNegocio(f"Faltam R$ {venda.total - pago:.2f} para fechar a venda")
    troco = pago - venda.total
    if troco > em_dinheiro:
        raise ErroDeNegocio("Troco só pode sair do pagamento em dinheiro")
    venda.troco = troco
    venda.pagamentos = [VendaPagamento(forma=p.forma, valor=p.valor) for p in dados.pagamentos]

    venda.numero = _proximo_numero(db)
    db.add(venda)
    db.flush()  # gera os ids dos itens para referenciar nos movimentos

    for item in venda.itens:
        produto = db.get(Produto, item.produto_id)
        baixar_fefo(db, loja_id, produto, item.quantidade, usuario.usuario_id, Referencia("venda_item", item.id))

    a_prazo = [p for p in dados.pagamentos if p.forma == "prazo"]
    if a_prazo:
        valor = sum((p.valor for p in a_prazo), Decimal(0))
        vencimento = next((p.vencimento for p in a_prazo if p.vencimento), None)
        lancar_fiado(db, usuario.usuario_id, venda, loja_id, valor, vencimento, farmacia.dias_prazo_padrao)
    pontuar_venda(db, farmacia, usuario.usuario_id, venda)

    if pre_venda is not None:
        pre_venda.status = "recebida"
        pre_venda.venda_id = venda.id
        pre_venda.finalizada_em = venda.finalizada_em

    try:
        db.commit()
    except IntegrityError:
        # Outro envio com a mesma chave chegou junto: devolve o que foi gravado por ele.
        db.rollback()
        existente = _venda_pela_chave(db, dados.chave_idempotencia)
        if existente is None:
            raise
        return existente, False
    return venda, True


def obter_venda(db: Session, venda_id: UUID) -> Venda:
    venda = db.get(Venda, venda_id)
    if venda is None:
        raise NaoEncontrado("Venda não encontrada")
    return venda


def listar_vendas(db: Session, caixa_id: UUID | None, pagina: int, por_pagina: int) -> list[Venda]:
    filtro = select(Venda)
    if caixa_id is not None:
        filtro = filtro.where(Venda.caixa_id == caixa_id)
    return db.scalars(
        filtro.order_by(Venda.numero.desc()).offset((pagina - 1) * por_pagina).limit(por_pagina)
    ).all()


def cancelar_venda(db: Session, usuario: TokenDados, venda_id: UUID, motivo: str) -> Venda:
    venda = db.scalar(select(Venda).where(Venda.id == venda_id).with_for_update(of=Venda))
    if venda is None:
        raise NaoEncontrado("Venda não encontrada")
    if venda.status == "cancelada":
        raise Conflito("Esta venda já foi cancelada")

    # Devolve a cada lote exatamente o que saiu dele.
    movimentos = db.scalars(
        select(MovimentoEstoque).where(
            MovimentoEstoque.referencia_tipo == "venda_item",
            MovimentoEstoque.referencia_id.in_([item.id for item in venda.itens]),
        )
    ).all()
    cancelar_fiado_da_venda(db, venda)
    estornar_da_venda(db, usuario.usuario_id, venda)
    for movimento in movimentos:
        devolver_movimento(db, movimento, usuario.usuario_id, motivo=f"Cancelamento da venda {venda.numero}")

    venda.status = "cancelada"
    venda.cancelada_em = _agora()
    venda.motivo_cancelamento = motivo
    db.commit()
    return venda


# --- Pré-venda ---

def _descricao(produto: Produto) -> str:
    return produto.nome if not produto.apresentacao else f"{produto.nome} {produto.apresentacao}"


def criar_pre_venda(db: Session, usuario: TokenDados, terminal: Terminal | None, dados: PreVendaCriar) -> PreVenda:
    if dados.loja_id is not None:
        loja = obter_loja(db, dados.loja_id)
    elif terminal is not None:
        loja = db.get(Loja, terminal.loja_id)
    else:
        loja = matriz(db)

    itens = []
    total = Decimal(0)
    for entrada in dados.itens:
        produto = db.get(Produto, entrada.produto_id)
        if produto is None or not produto.ativo:
            raise NaoEncontrado("Produto não encontrado")
        valor = (produto.preco_venda * entrada.quantidade).quantize(CENTAVO)
        itens.append(
            {
                "produto_id": str(produto.id),
                "ean": produto.ean,
                "descricao": _descricao(produto),
                "quantidade": str(entrada.quantidade),
                "preco_unitario": str(produto.preco_venda),
                "total": str(valor),
            }
        )
        total += valor

    # Trava separada da numeração de vendas.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext('pre_venda:' || current_setting('app.farmacia_id')))"))
    numero = db.scalar(select(func.coalesce(func.max(PreVenda.numero), 0) + 1))
    pre_venda = PreVenda(
        loja_id=loja.id,
        numero=numero,
        usuario_id=usuario.usuario_id,
        itens=itens,
        total=total,
        cliente_cpf=dados.cliente_cpf,
    )
    db.add(pre_venda)
    db.commit()
    return pre_venda


def saida_pre_venda(db: Session, pre_venda: PreVenda) -> PreVendaSaida:
    return PreVendaSaida.model_validate(
        {
            **{c: getattr(pre_venda, c) for c in PreVendaSaida.model_fields if c != "vendedor"},
            "vendedor": db.get(Usuario, pre_venda.usuario_id).nome,
        }
    )


def listar_pre_vendas(db: Session, status: str | None, loja_id: UUID | None) -> list[PreVenda]:
    filtro = select(PreVenda)
    if status:
        filtro = filtro.where(PreVenda.status == status)
    if loja_id:
        filtro = filtro.where(PreVenda.loja_id == loja_id)
    return db.scalars(filtro.order_by(PreVenda.numero.desc()).limit(100)).all()


def obter_pre_venda(db: Session, pre_venda_id: UUID) -> PreVenda:
    pre_venda = db.get(PreVenda, pre_venda_id)
    if pre_venda is None:
        raise NaoEncontrado("Pré-venda não encontrada")
    return pre_venda


def pre_venda_pelo_numero(db: Session, numero: int) -> PreVenda:
    pre_venda = db.scalar(select(PreVenda).where(PreVenda.numero == numero))
    if pre_venda is None:
        raise NaoEncontrado(f"Pré-venda nº {numero} não encontrada")
    return pre_venda


def _pre_venda_para_receber(db: Session, pre_venda_id: UUID) -> PreVenda:
    pre_venda = db.scalar(select(PreVenda).where(PreVenda.id == pre_venda_id).with_for_update())
    if pre_venda is None:
        raise NaoEncontrado("Pré-venda não encontrada")
    if pre_venda.status != "aberta":
        raise Conflito(f"A pré-venda nº {pre_venda.numero} já foi {pre_venda.status}")
    return pre_venda


def cancelar_pre_venda(db: Session, pre_venda_id: UUID) -> PreVenda:
    pre_venda = _pre_venda_para_receber(db, pre_venda_id)
    pre_venda.status = "cancelada"
    pre_venda.finalizada_em = _agora()
    db.commit()
    return pre_venda
