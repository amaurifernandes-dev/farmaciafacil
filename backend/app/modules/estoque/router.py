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
    PaginaSaldos,
    PerdaCriar,
    TransferenciaCriar,
)

router = APIRouter(prefix="/estoque", tags=["estoque"])


@router.get("/lotes")
def listar_lotes(
    db: DB, produto_id: UUID | None = None, loja_id: UUID | None = None, incluir_zerados: bool = False
) -> list[LoteSaida]:
    return service.listar_lotes(db, produto_id, incluir_zerados, loja_id)


@router.get("/saldos")
def saldos(
    db: DB,
    busca: str | None = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PaginaSaldos:
    """Quanto cada produto tem em cada loja."""
    itens, total = service.saldos(db, busca, pagina, por_pagina)
    return PaginaSaldos(itens=itens, total=total, pagina=pagina, por_pagina=por_pagina)


@router.get("/movimentos")
def listar_movimentos(
    db: DB,
    produto_id: UUID | None = None,
    loja_id: UUID | None = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[MovimentoSaida]:
    return service.listar_movimentos(db, produto_id, pagina, por_pagina, loja_id)


@router.get("/alertas")
def alertas(db: DB, dias: Annotated[int, Query(ge=1, le=365)] = 90, loja_id: UUID | None = None) -> Alertas:
    return service.alertas(db, dias, loja_id)


@router.post("/entradas", status_code=status.HTTP_201_CREATED)
def registrar_entrada(db: DB, usuario: Estoquista, entrada: EntradaCriar) -> list[MovimentoSaida]:
    return service.registrar_entrada(db, usuario.usuario_id, entrada)


@router.post("/ajustes", status_code=status.HTTP_201_CREATED)
def ajustar(db: DB, usuario: Estoquista, ajuste: AjusteCriar) -> MovimentoSaida:
    return service.ajustar(db, usuario.usuario_id, ajuste)


@router.post("/perdas", status_code=status.HTTP_201_CREATED)
def registrar_perda(db: DB, usuario: Estoquista, perda: PerdaCriar) -> MovimentoSaida:
    return service.registrar_perda(db, usuario.usuario_id, perda)


@router.post("/transferencias", status_code=status.HTTP_201_CREATED)
def transferir(db: DB, usuario: Estoquista, dados: TransferenciaCriar) -> list[MovimentoSaida]:
    return service.transferir(db, usuario.usuario_id, dados)
