from fastapi import APIRouter

from app.core.deps import DB, UsuarioAtual
from app.modules.painel import service
from app.modules.painel.schemas import Painel

router = APIRouter(prefix="/painel", tags=["painel"])


@router.get("")
def painel(db: DB, usuario: UsuarioAtual) -> Painel:
    return service.painel(db, usuario)
