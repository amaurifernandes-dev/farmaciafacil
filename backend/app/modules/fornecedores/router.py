from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.deps import DB, Estoquista
from app.modules.fornecedores import service
from app.modules.fornecedores.schemas import (
    FornecedorAtualizar,
    FornecedorCriar,
    FornecedorSaida,
    PaginaFornecedores,
)

router = APIRouter(prefix="/fornecedores", tags=["fornecedores"])


@router.get("")
def listar(
    db: DB,
    busca: str | None = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=100)] = 50,
    incluir_inativos: bool = False,
) -> PaginaFornecedores:
    itens, total = service.listar(db, busca, pagina, por_pagina, incluir_inativos)
    return PaginaFornecedores(itens=[FornecedorSaida.model_validate(f) for f in itens], total=total)


@router.get("/{fornecedor_id}")
def obter(db: DB, fornecedor_id: UUID) -> FornecedorSaida:
    return service.obter(db, fornecedor_id)


@router.post("", status_code=status.HTTP_201_CREATED)
def criar(db: DB, _: Estoquista, dados: FornecedorCriar) -> FornecedorSaida:
    return service.criar(db, dados)


@router.patch("/{fornecedor_id}")
def atualizar(db: DB, _: Estoquista, fornecedor_id: UUID, dados: FornecedorAtualizar) -> FornecedorSaida:
    return service.atualizar(db, fornecedor_id, dados)
