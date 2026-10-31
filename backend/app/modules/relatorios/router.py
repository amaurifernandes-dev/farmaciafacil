from datetime import date, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.core.deps import DB, Gerente
from app.modules.relatorios import service
from app.modules.relatorios.schemas import (
    RelatorioParados,
    RelatorioProdutos,
    RelatorioVendas,
)
from app.shared.datas import hoje
from app.shared.erros import ErroDeNegocio

router = APIRouter(prefix="/relatorios", tags=["relatórios"])


def _periodo(inicio: date | None, fim: date | None) -> tuple[date, date]:
    """Padrão: os últimos 30 dias, contando hoje."""
    fim = fim or hoje()
    inicio = inicio or fim - timedelta(days=29)
    if inicio > fim:
        raise ErroDeNegocio("O início do período não pode ser depois do fim")
    if (fim - inicio).days > 366:
        raise ErroDeNegocio("Escolha um período de até um ano")
    return inicio, fim


@router.get("/vendas")
def vendas(
    db: DB, _: Gerente, inicio: date | None = None, fim: date | None = None, loja_id: UUID | None = None
) -> RelatorioVendas:
    return service.vendas(db, *_periodo(inicio, fim), loja_id)


@router.get("/produtos")
def produtos(
    db: DB, _: Gerente, inicio: date | None = None, fim: date | None = None, loja_id: UUID | None = None
) -> RelatorioProdutos:
    return service.produtos(db, *_periodo(inicio, fim), loja_id)


@router.get("/parados")
def parados(
    db: DB, _: Gerente, dias: Annotated[int, Query(ge=7, le=730)] = 60, loja_id: UUID | None = None
) -> RelatorioParados:
    return service.parados(db, dias, loja_id)
