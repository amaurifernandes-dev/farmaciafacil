from fastapi import APIRouter

from app.core.deps import DB, Admin, UsuarioAtual
from app.modules.farmacias.models import Farmacia
from app.modules.farmacias.schemas import Configuracoes, ConfiguracoesAtualizar

router = APIRouter(prefix="/configuracoes", tags=["configurações"])


@router.get("")
def obter(db: DB, usuario: UsuarioAtual) -> Configuracoes:
    return db.get(Farmacia, usuario.farmacia_id)


@router.patch("")
def atualizar(db: DB, usuario: Admin, dados: ConfiguracoesAtualizar) -> Configuracoes:
    farmacia = db.get(Farmacia, usuario.farmacia_id)
    for campo, valor in dados.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(farmacia, campo, valor)
    db.commit()
    db.refresh(farmacia)
    return farmacia
