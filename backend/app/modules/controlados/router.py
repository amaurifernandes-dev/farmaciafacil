from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.core.deps import DB, exigir_papel
from app.core.security import TokenDados
from app.modules.controlados import service
from app.modules.controlados.schemas import ResumoControlados

# O livro de controlados é do farmacêutico responsável (e de quem gerencia a loja).
Farmaceutico = Annotated[TokenDados, Depends(exigir_papel("admin", "gerente", "farmaceutico"))]

router = APIRouter(prefix="/controlados", tags=["controlados"])


def _download(nome: str, conteudo: bytes) -> Response:
    return Response(
        conteudo,
        media_type="application/xml; charset=iso-8859-1",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


@router.get("", response_model=ResumoControlados, summary="Livro de controlados, saldos e pendências do período")
def resumo(
    db: DB, _: Farmaceutico, loja_id: UUID | None = None, inicio: date | None = None, fim: date | None = None
) -> ResumoControlados:
    return service.resumo(db, loja_id, inicio, fim)


@router.get("/sngpc", summary="Arquivo XML de movimentação para o SNGPC da Anvisa")
def sngpc(db: DB, _: Farmaceutico, loja_id: UUID | None = None, inicio: date | None = None,
          fim: date | None = None) -> Response:
    return _download(*service.arquivo_movimentacao(db, loja_id, inicio, fim))


@router.get("/inventario", summary="Arquivo XML de inventário para o SNGPC (saldo de hoje)")
def inventario(db: DB, _: Farmaceutico, loja_id: UUID | None = None) -> Response:
    return _download(*service.arquivo_inventario(db, loja_id))
