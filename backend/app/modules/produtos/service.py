from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.produtos.models import Produto, ProdutoCodigo
from app.modules.produtos.schemas import ProdutoAtualizar, ProdutoCriar
from app.shared.erros import Conflito, NaoEncontrado


def _ean_em_uso(db: Session, ean: str, ignorar_produto_id: UUID | None = None) -> bool:
    """O mesmo EAN não pode estar em dois produtos, nem como principal nem como extra."""
    no_principal = select(Produto.id).where(Produto.ean == ean)
    no_extra = select(ProdutoCodigo.produto_id).where(ProdutoCodigo.ean == ean)
    if ignorar_produto_id is not None:
        no_principal = no_principal.where(Produto.id != ignorar_produto_id)
        no_extra = no_extra.where(ProdutoCodigo.produto_id != ignorar_produto_id)
    return db.scalar(select(no_principal.union(no_extra).exists())) or False


def listar(db: Session, busca: str | None, pagina: int, por_pagina: int, incluir_inativos: bool):
    filtro = select(Produto)
    if not incluir_inativos:
        filtro = filtro.where(Produto.ativo.is_(True))
    if busca:
        termo = busca.strip()
        if termo.isdigit():
            filtro = filtro.where(
                or_(
                    Produto.ean == termo,
                    Produto.id.in_(select(ProdutoCodigo.produto_id).where(ProdutoCodigo.ean == termo)),
                )
            )
        else:
            filtro = filtro.where(Produto.nome.ilike(f"%{termo}%"))

    total = db.scalar(select(func.count()).select_from(filtro.subquery()))
    itens = db.scalars(
        filtro.order_by(Produto.nome).offset((pagina - 1) * por_pagina).limit(por_pagina)
    ).all()
    return itens, total


def obter(db: Session, produto_id: UUID) -> Produto:
    produto = db.get(Produto, produto_id)
    if produto is None:
        raise NaoEncontrado("Produto não encontrado")
    return produto


def obter_por_ean(db: Session, ean: str) -> Produto:
    """Busca usada pelo PDV a cada bipada: procura no EAN principal e nos extras."""
    produto = db.scalar(
        select(Produto).where(
            Produto.ativo.is_(True),
            or_(
                Produto.ean == ean,
                Produto.id.in_(select(ProdutoCodigo.produto_id).where(ProdutoCodigo.ean == ean)),
            ),
        )
    )
    if produto is None:
        raise NaoEncontrado("Produto não encontrado para este código")
    return produto


def criar(db: Session, dados: ProdutoCriar) -> Produto:
    if dados.ean and _ean_em_uso(db, dados.ean):
        raise Conflito("Já existe produto com este código de barras")
    valores = dados.model_dump()
    if valores["vende_online"] is None:
        valores["vende_online"] = dados.tipo != "medicamento"  # remédio só vai para o site se a farmácia marcar
    produto = Produto(**valores)
    db.add(produto)
    db.commit()
    return produto


def atualizar(db: Session, produto_id: UUID, dados: ProdutoAtualizar) -> Produto:
    produto = obter(db, produto_id)
    alteracoes = dados.model_dump(exclude_unset=True)
    if alteracoes.get("ean") and _ean_em_uso(db, alteracoes["ean"], ignorar_produto_id=produto.id):
        raise Conflito("Já existe produto com este código de barras")
    for campo, valor in alteracoes.items():
        setattr(produto, campo, valor)
    db.commit()
    db.refresh(produto)
    return produto


def adicionar_codigo(db: Session, produto_id: UUID, ean: str) -> Produto:
    produto = obter(db, produto_id)
    if _ean_em_uso(db, ean):
        raise Conflito("Já existe produto com este código de barras")
    produto.codigos.append(ProdutoCodigo(ean=ean))
    db.commit()
    db.refresh(produto)
    return produto


def remover_codigo(db: Session, produto_id: UUID, codigo_id: UUID) -> None:
    codigo = db.get(ProdutoCodigo, codigo_id)
    if codigo is None or codigo.produto_id != produto_id:
        raise NaoEncontrado("Código não encontrado")
    db.delete(codigo)
    db.commit()
