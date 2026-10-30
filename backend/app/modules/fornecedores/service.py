from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.fornecedores.models import Fornecedor
from app.modules.fornecedores.schemas import FornecedorAtualizar, FornecedorCriar
from app.shared.erros import Conflito, NaoEncontrado


def listar(db: Session, busca: str | None, pagina: int, por_pagina: int, incluir_inativos: bool):
    filtro = select(Fornecedor)
    if not incluir_inativos:
        filtro = filtro.where(Fornecedor.ativo.is_(True))
    if busca and busca.strip():
        termo = busca.strip()
        digitos = "".join(c for c in termo if c.isdigit())
        condicoes = [Fornecedor.razao_social.ilike(f"%{termo}%"), Fornecedor.nome_fantasia.ilike(f"%{termo}%")]
        if digitos:
            condicoes.append(Fornecedor.cnpj.like(f"{digitos}%"))
        filtro = filtro.where(or_(*condicoes))
    total = db.scalar(select(func.count()).select_from(filtro.subquery()))
    itens = db.scalars(
        filtro.order_by(Fornecedor.razao_social).offset((pagina - 1) * por_pagina).limit(por_pagina)
    ).all()
    return itens, total


def obter(db: Session, fornecedor_id: UUID) -> Fornecedor:
    fornecedor = db.get(Fornecedor, fornecedor_id)
    if fornecedor is None:
        raise NaoEncontrado("Fornecedor não encontrado")
    return fornecedor


def _salvar(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflito("Já existe fornecedor com este CNPJ")


def criar(db: Session, dados: FornecedorCriar) -> Fornecedor:
    fornecedor = Fornecedor(**dados.model_dump())
    db.add(fornecedor)
    _salvar(db)
    return fornecedor


def atualizar(db: Session, fornecedor_id: UUID, dados: FornecedorAtualizar) -> Fornecedor:
    fornecedor = obter(db, fornecedor_id)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        if campo in ("razao_social", "ativo") and valor is None:
            continue
        setattr(fornecedor, campo, valor)
    _salvar(db)
    db.refresh(fornecedor)
    return fornecedor
