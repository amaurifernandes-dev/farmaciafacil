from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.deps import DB, UsuarioAtual
from app.modules.clientes import service
from app.modules.clientes.schemas import ClienteAtualizar, ClienteCriar, ClienteSaida, PaginaClientes

router = APIRouter(prefix="/clientes", tags=["clientes"])


@router.get("")
def listar(
    db: DB,
    _: UsuarioAtual,
    busca: str | None = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=100)] = 50,
    incluir_inativos: bool = False,
) -> PaginaClientes:
    itens, total = service.listar(db, busca, pagina, por_pagina, incluir_inativos)
    return PaginaClientes(itens=[ClienteSaida.model_validate(c) for c in itens], total=total)


@router.get("/{cliente_id}")
def obter(db: DB, cliente_id: UUID) -> ClienteSaida:
    return service.obter(db, cliente_id)


@router.post("", status_code=status.HTTP_201_CREATED)
def criar(db: DB, _: UsuarioAtual, dados: ClienteCriar) -> ClienteSaida:
    return service.criar(db, dados)


@router.patch("/{cliente_id}")
def atualizar(db: DB, _: UsuarioAtual, cliente_id: UUID, dados: ClienteAtualizar) -> ClienteSaida:
    return service.atualizar(db, cliente_id, dados)
