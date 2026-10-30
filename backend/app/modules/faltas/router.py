from uuid import UUID

from fastapi import APIRouter, status

from app.core.deps import DB, UsuarioAtual
from app.modules.faltas import service
from app.modules.faltas.schemas import FaltaCriar, FaltaSaida, ListaFaltas, Situacao
from app.modules.lojas.deps import TerminalAtual

router = APIRouter(prefix="/faltas", tags=["faltas e encomendas"])


@router.get("")
def listar(
    db: DB, _: UsuarioAtual, situacao: Situacao = "encomendas", loja_id: UUID | None = None, busca: str | None = None
) -> ListaFaltas:
    return service.listar(db, situacao, loja_id, busca)


@router.post("", status_code=status.HTTP_201_CREATED)
def criar(db: DB, usuario: UsuarioAtual, terminal: TerminalAtual, dados: FaltaCriar) -> FaltaSaida:
    """Anota o que o cliente pediu e não tinha. Com nome ou telefone, vira encomenda."""
    return service.criar(db, usuario, terminal, dados)


@router.post("/{falta_id}/avisar")
def avisar(db: DB, _: UsuarioAtual, falta_id: UUID) -> FaltaSaida:
    return service.avisar(db, falta_id)


@router.post("/{falta_id}/entregar")
def entregar(db: DB, _: UsuarioAtual, falta_id: UUID) -> FaltaSaida:
    return service.entregar(db, falta_id)


@router.post("/{falta_id}/cancelar")
def cancelar(db: DB, _: UsuarioAtual, falta_id: UUID) -> FaltaSaida:
    return service.cancelar(db, falta_id)
