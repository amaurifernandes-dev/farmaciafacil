from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import TokenDados
from app.modules.estoque.models import MovimentoEstoque
from app.modules.estoque.service import Referencia, baixar_fefo, devolver_movimento
from app.modules.produtos.models import Produto
from app.modules.vendas.models import Caixa, Venda, VendaItem, VendaPagamento
from app.modules.vendas.schemas import CaixaSaida, ResumoCaixa, VendaCriar
from app.shared.erros import Conflito, ErroDeNegocio, NaoEncontrado, SemPermissao

# Desconto máximo que um operador de caixa pode dar sozinho, em % do subtotal.
DESCONTO_MAXIMO_CAIXA = Decimal("10")
CENTAVO = Decimal("0.01")


def _agora() -> datetime:
    return datetime.now(timezone.utc)


# --- Caixa ---

def caixa_aberto(db: Session, usuario_id: UUID) -> Caixa | None:
    return db.scalar(select(Caixa).where(Caixa.usuario_id == usuario_id, Caixa.status == "aberto"))


def abrir_caixa(db: Session, usuario_id: UUID, valor_abertura: Decimal) -> Caixa:
    if caixa_aberto(db, usuario_id) is not None:
        raise Conflito("Você já tem um caixa aberto")
    caixa = Caixa(usuario_id=usuario_id, valor_abertura=valor_abertura, aberto_em=_agora())
    db.add(caixa)
    db.commit()
    return caixa


def obter_caixa(db: Session, caixa_id: UUID) -> Caixa:
    caixa = db.get(Caixa, caixa_id)
    if caixa is None:
        raise NaoEncontrado("Caixa não encontrado")
    return caixa


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
    esperado = caixa.valor_abertura + por_forma.get("dinheiro", Decimal(0)) - troco
    diferenca = None
    if caixa.valor_fechamento_informado is not None:
        diferenca = caixa.valor_fechamento_informado - esperado
    return ResumoCaixa(
        caixa=CaixaSaida.model_validate(caixa),
        quantidade_vendas=quantidade,
        total_vendido=total,
        por_forma=por_forma,
        dinheiro_esperado=esperado,
        diferenca=diferenca,
    )


def fechar_caixa(db: Session, usuario: TokenDados, caixa_id: UUID, valor_informado: Decimal) -> ResumoCaixa:
    caixa = obter_caixa(db, caixa_id)
    if caixa.usuario_id != usuario.usuario_id and usuario.papel == "caixa":
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


def registrar_venda(db: Session, usuario: TokenDados, dados: VendaCriar) -> tuple[Venda, bool]:
    """Grava a venda, baixa o estoque e registra os pagamentos numa transação só.

    Devolve (venda, criada). Se a chave já foi usada, devolve a venda existente e criada=False.
    """
    existente = _venda_pela_chave(db, dados.chave_idempotencia)
    if existente is not None:
        return existente, False

    caixa = caixa_aberto(db, usuario.usuario_id)
    if caixa is None:
        raise ErroDeNegocio("Abra o caixa antes de vender")

    venda = Venda(
        caixa_id=caixa.id,
        usuario_id=usuario.usuario_id,
        chave_idempotencia=dados.chave_idempotencia,
        cliente_cpf=dados.cliente_cpf,
        finalizada_em=_agora(),
    )

    subtotal = Decimal(0)
    descontos = dados.desconto
    for ordem, entrada in enumerate(dados.itens, start=1):
        produto = db.get(Produto, entrada.produto_id)
        if produto is None or not produto.ativo:
            raise NaoEncontrado("Produto não encontrado")
        bruto = (produto.preco_venda * entrada.quantidade).quantize(CENTAVO)
        if entrada.desconto > bruto:
            raise ErroDeNegocio(f"Desconto maior que o valor de {produto.nome}")
        venda.itens.append(
            VendaItem(
                ordem=ordem,
                produto_id=produto.id,
                descricao=produto.nome if not produto.apresentacao else f"{produto.nome} {produto.apresentacao}",
                quantidade=entrada.quantidade,
                preco_unitario=produto.preco_venda,
                desconto=entrada.desconto,
                total=bruto - entrada.desconto,
            )
        )
        subtotal += bruto
        descontos += entrada.desconto

    if descontos > subtotal:
        raise ErroDeNegocio("Desconto maior que o valor da venda")
    if usuario.papel == "caixa" and subtotal > 0 and descontos * 100 / subtotal > DESCONTO_MAXIMO_CAIXA:
        raise SemPermissao(f"Desconto acima de {DESCONTO_MAXIMO_CAIXA}% precisa de um gerente")

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
        baixar_fefo(db, produto, item.quantidade, usuario.usuario_id, Referencia("venda_item", item.id))

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
    for movimento in movimentos:
        devolver_movimento(db, movimento, usuario.usuario_id, motivo=f"Cancelamento da venda {venda.numero}")

    venda.status = "cancelada"
    venda.cancelada_em = _agora()
    venda.motivo_cancelamento = motivo
    db.commit()
    return venda
