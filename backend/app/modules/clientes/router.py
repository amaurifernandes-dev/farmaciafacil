from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.deps import DB, Gerente, Operador, UsuarioAtual
from app.modules.clientes import service
from app.modules.clientes.schemas import ClienteAtualizar, ClienteCriar, ClienteSaida, FichaCliente, PaginaClientes
from app.modules.farmacias.models import Farmacia
from app.modules.fidelidade import service as fidelidade
from app.modules.fidelidade.schemas import AjustePontos, Pontos

router = APIRouter(prefix="/clientes", tags=["clientes"])


@router.get("")
def listar(
    db: DB,
    _: UsuarioAtual,
    busca: str | None = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=100)] = 50,
    incluir_inativos: bool = False,
    filtro: Literal["aniversariantes", "sumidos"] | None = None,
) -> PaginaClientes:
    itens, total = service.listar(db, busca, pagina, por_pagina, incluir_inativos, filtro)
    return PaginaClientes(itens=itens, total=total)


@router.get("/{cliente_id}")
def obter(db: DB, cliente_id: UUID) -> ClienteSaida:
    return service.obter(db, cliente_id)


@router.get("/{cliente_id}/ficha")
def ficha(db: DB, usuario: Operador, cliente_id: UUID) -> FichaCliente:
    """Tudo sobre o cliente numa tela: compras, produtos que leva sempre, pontos e fiado."""
    return service.ficha(db, usuario.farmacia_id, cliente_id)


@router.get("/{cliente_id}/pontos")
def pontos(db: DB, usuario: Operador, cliente_id: UUID, movimentos: Annotated[int, Query(ge=0, le=200)] = 0) -> Pontos:
    return fidelidade.pontos(db, db.get(Farmacia, usuario.farmacia_id), cliente_id, movimentos)


@router.post("/{cliente_id}/pontos/ajuste")
def ajustar_pontos(db: DB, usuario: Gerente, cliente_id: UUID, dados: AjustePontos) -> Pontos:
    farmacia = db.get(Farmacia, usuario.farmacia_id)
    return fidelidade.ajustar(db, usuario, farmacia, cliente_id, dados.pontos, dados.observacao)


@router.post("", status_code=status.HTTP_201_CREATED)
def criar(db: DB, _: UsuarioAtual, dados: ClienteCriar) -> ClienteSaida:
    return service.criar(db, dados)


@router.patch("/{cliente_id}")
def atualizar(db: DB, _: UsuarioAtual, cliente_id: UUID, dados: ClienteAtualizar) -> ClienteSaida:
    return service.atualizar(db, cliente_id, dados)
