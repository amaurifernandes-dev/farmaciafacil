"""Regras de estoque. Toda mudança de saldo passa por `_movimentar`."""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.estoque.models import LOTE_PADRAO, Lote, MovimentoEstoque
from app.modules.estoque.schemas import (
    AjusteCriar,
    Alertas,
    EntradaCriar,
    LoteComProduto,
    PerdaCriar,
    ProdutoAbaixoMinimo,
)
from app.modules.produtos.models import Produto
from app.modules.produtos.service import obter as obter_produto
from app.shared.datas import hoje
from app.shared.erros import ErroDeNegocio, NaoEncontrado


class EstoqueInsuficiente(ErroDeNegocio):
    status_code = 409


@dataclass
class Referencia:
    """De onde veio o movimento (ex.: tipo "venda_item" e o id do item)."""

    tipo: str
    id: UUID | None = None


def _movimentar(
    db: Session,
    lote: Lote,
    quantidade: Decimal,
    tipo: str,
    usuario_id: UUID,
    *,
    custo_unitario: Decimal | None = None,
    referencia: Referencia | None = None,
    motivo: str | None = None,
) -> MovimentoEstoque:
    """Altera o saldo do lote e grava o movimento. O lote deve estar travado (FOR UPDATE)."""
    novo_saldo = lote.quantidade + quantidade
    if novo_saldo < 0:
        raise EstoqueInsuficiente(f"Saldo insuficiente no lote {lote.numero_lote}")
    lote.quantidade = novo_saldo
    movimento = MovimentoEstoque(
        produto_id=lote.produto_id,
        lote_id=lote.id,
        tipo=tipo,
        quantidade=quantidade,
        custo_unitario=custo_unitario,
        referencia_tipo=referencia.tipo if referencia else None,
        referencia_id=referencia.id if referencia else None,
        usuario_id=usuario_id,
        motivo=motivo,
    )
    db.add(movimento)
    return movimento


def _lote_travado(db: Session, lote_id: UUID) -> Lote:
    lote = db.scalar(select(Lote).where(Lote.id == lote_id).with_for_update(of=Lote))
    if lote is None:
        raise NaoEncontrado("Lote não encontrado")
    return lote


def _obter_ou_criar_lote(db: Session, produto: Produto, numero_lote: str, validade) -> Lote:
    """Cria o lote se ainda não existe (seguro com dois usuários ao mesmo tempo) e o trava."""
    db.execute(
        insert(Lote)
        .values(produto_id=produto.id, numero_lote=numero_lote, validade=validade, quantidade=0)
        .on_conflict_do_nothing(index_elements=["farmacia_id", "produto_id", "numero_lote"])
    )
    lote = db.scalar(
        select(Lote)
        .where(Lote.produto_id == produto.id, Lote.numero_lote == numero_lote)
        .with_for_update(of=Lote)
    )
    if validade is not None and lote.validade != validade:
        raise ErroDeNegocio(
            f"O lote {numero_lote} já existe com validade {lote.validade:%d/%m/%Y}. Confira a nota."
        )
    return lote


def registrar_entrada(db: Session, usuario_id: UUID, entrada: EntradaCriar) -> list[MovimentoEstoque]:
    movimentos = []
    for item in entrada.itens:
        produto = obter_produto(db, item.produto_id)
        if produto.controla_lote:
            if not item.numero_lote or item.validade is None:
                raise ErroDeNegocio(f"Informe lote e validade de {produto.nome}")
            if item.validade < hoje():
                raise ErroDeNegocio(f"O lote {item.numero_lote} de {produto.nome} já está vencido")
            lote = _obter_ou_criar_lote(db, produto, item.numero_lote.strip().upper(), item.validade)
        else:
            lote = _obter_ou_criar_lote(db, produto, LOTE_PADRAO, None)

        movimentos.append(
            _movimentar(
                db,
                lote,
                item.quantidade,
                "entrada",
                usuario_id,
                custo_unitario=item.custo_unitario,
                motivo=entrada.observacao,
            )
        )
        if item.custo_unitario is not None:
            produto.preco_custo = item.custo_unitario
    db.commit()
    return movimentos


def ajustar(db: Session, usuario_id: UUID, ajuste: AjusteCriar) -> MovimentoEstoque:
    lote = _lote_travado(db, ajuste.lote_id)
    diferenca = ajuste.nova_quantidade - lote.quantidade
    if diferenca == 0:
        raise ErroDeNegocio("A quantidade informada é igual ao saldo atual")
    movimento = _movimentar(db, lote, diferenca, "ajuste", usuario_id, motivo=ajuste.motivo)
    db.commit()
    return movimento


def registrar_perda(db: Session, usuario_id: UUID, perda: PerdaCriar) -> MovimentoEstoque:
    lote = _lote_travado(db, perda.lote_id)
    movimento = _movimentar(db, lote, -perda.quantidade, "perda", usuario_id, motivo=perda.motivo)
    db.commit()
    return movimento


def _lotes_vendaveis():
    """Lotes com saldo e não vencidos, na ordem FEFO (vence primeiro, sai primeiro)."""
    return (
        select(Lote)
        .where(Lote.quantidade > 0, or_(Lote.validade.is_(None), Lote.validade >= hoje()))
        .order_by(Lote.validade.asc().nulls_last(), Lote.criado_em)
    )


def saldo_vendavel(db: Session, produto_id: UUID) -> Decimal:
    vendaveis = _lotes_vendaveis().where(Lote.produto_id == produto_id).subquery()
    return db.scalar(select(func.coalesce(func.sum(vendaveis.c.quantidade), 0)))


def baixar_fefo(
    db: Session,
    produto: Produto,
    quantidade: Decimal,
    usuario_id: UUID,
    referencia: Referencia,
    tipo: str = "venda",
) -> list[MovimentoEstoque]:
    """Tira `quantidade` do estoque, começando pelo lote que vence antes.

    Não faz commit: quem chama (a venda) decide, para tudo entrar numa transação só.
    """
    lotes = db.scalars(
        _lotes_vendaveis().where(Lote.produto_id == produto.id).with_for_update(of=Lote)
    ).all()
    disponivel = sum((lote.quantidade for lote in lotes), Decimal(0))
    if disponivel < quantidade:
        raise EstoqueInsuficiente(
            f"Estoque insuficiente de {produto.nome}: disponível {disponivel.normalize()}"
        )

    movimentos = []
    restante = quantidade
    for lote in lotes:
        if restante == 0:
            break
        tirar = min(lote.quantidade, restante)
        movimentos.append(_movimentar(db, lote, -tirar, tipo, usuario_id, referencia=referencia))
        restante -= tirar
    return movimentos


def listar_lotes(db: Session, produto_id: UUID | None, incluir_zerados: bool) -> list[Lote]:
    filtro = select(Lote)
    if produto_id is not None:
        filtro = filtro.where(Lote.produto_id == produto_id)
    if not incluir_zerados:
        filtro = filtro.where(Lote.quantidade > 0)
    return db.scalars(filtro.order_by(Lote.validade.asc().nulls_last())).all()


def listar_movimentos(db: Session, produto_id: UUID | None, pagina: int, por_pagina: int):
    filtro = select(MovimentoEstoque)
    if produto_id is not None:
        filtro = filtro.where(MovimentoEstoque.produto_id == produto_id)
    return db.scalars(
        filtro.order_by(MovimentoEstoque.criado_em.desc(), MovimentoEstoque.id.desc())
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    ).all()


def _com_produto(lote: Lote) -> LoteComProduto:
    dias = (lote.validade - hoje()).days if lote.validade else None
    return LoteComProduto(
        id=lote.id,
        produto_id=lote.produto_id,
        numero_lote=lote.numero_lote,
        validade=lote.validade,
        quantidade=lote.quantidade,
        produto_nome=lote.produto.nome,
        dias_para_vencer=dias,
    )


def alertas(db: Session, dias: int) -> Alertas:
    com_saldo = select(Lote).where(Lote.quantidade > 0, Lote.validade.is_not(None))
    vencidos = db.scalars(com_saldo.where(Lote.validade < hoje()).order_by(Lote.validade)).all()
    vencendo = db.scalars(
        com_saldo.where(Lote.validade >= hoje(), Lote.validade <= hoje() + timedelta(days=dias))
        .order_by(Lote.validade)
    ).all()

    vendaveis = _lotes_vendaveis().subquery()
    saldo = func.coalesce(func.sum(vendaveis.c.quantidade), 0)
    abaixo = db.execute(
        select(Produto.id, Produto.nome, saldo.label("saldo"), Produto.estoque_minimo)
        .outerjoin(vendaveis, vendaveis.c.produto_id == Produto.id)
        .where(Produto.ativo.is_(True), Produto.estoque_minimo > 0)
        .group_by(Produto.id)
        .having(saldo < Produto.estoque_minimo)
        .order_by(Produto.nome)
    ).all()

    return Alertas(
        vencidos=[_com_produto(lote) for lote in vencidos],
        vencendo=[_com_produto(lote) for lote in vencendo],
        abaixo_do_minimo=[
            ProdutoAbaixoMinimo(produto_id=l.id, nome=l.nome, saldo=l.saldo, estoque_minimo=l.estoque_minimo)
            for l in abaixo
        ],
    )
