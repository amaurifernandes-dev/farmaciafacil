from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.deps import DB, Estoquista
from app.modules.estoque import service
from app.modules.estoque.schemas import (
    AjusteCriar,
    Alertas,
    EntradaCriar,
    LoteSaida,
    MovimentoSaida,
    PerdaCriar,
)

router = APIRouter(prefix="/estoque", tags=["estoque"])


@router.get("/lotes")
def listar_lotes(db: DB, produto_id: UUID | None = None, incluir_zerados: bool = False) -> list[LoteSaida]:
    return service.listar_lotes(db, produto_id, incluir_zerados)


@router.get("/movimentos")
def listar_movimentos(
    db: DB,
    produto_id: UUID | None = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[MovimentoSaida]:
    return service.listar_movimentos(db, produto_id, pagina, por_pagina)


@router.get("/alertas")
def alertas(db: DB, dias: Annotated[int, Query(ge=1, le=365)] = 90) -> Alertas:
    return service.alertas(db, dias)


@router.post("/entradas", status_code=status.HTTP_201_CREATED)
def registrar_entrada(db: DB, usuario: Estoquista, entrada: EntradaCriar) -> list[MovimentoSaida]:
    return service.registrar_entrada(db, usuario.usuario_id, entrada)


@router.post("/ajustes", status_code=status.HTTP_201_CREATED)
def ajustar(db: DB, usuario: Estoquista, ajuste: AjusteCriar) -> MovimentoSaida:
    return service.ajustar(db, usuario.usuario_id, ajuste)


@router.post("/perdas", status_code=status.HTTP_201_CREATED)
def registrar_perda(db: DB, usuario: Estoquista, perda: PerdaCriar) -> MovimentoSaida:
    return service.registrar_perda(db, usuario.usuario_id, perda)
