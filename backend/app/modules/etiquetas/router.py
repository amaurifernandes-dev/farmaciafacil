from uuid import UUID

from fastapi import APIRouter

from app.core.deps import DB, UsuarioAtual
from app.modules.etiquetas import service
from app.modules.etiquetas.schemas import ListaEtiquetas, MarcarImpressas, Situacao

router = APIRouter(prefix="/etiquetas", tags=["etiquetas"])


@router.get("", response_model=ListaEtiquetas, summary="Etiquetas de gôndola: as que precisam trocar, ou todas")
def listar(
    db: DB,
    _: UsuarioAtual,
    loja_id: UUID | None = None,
    situacao: Situacao = "trocar",
    busca: str | None = None,
    so_com_estoque: bool = True,
) -> ListaEtiquetas:
    return service.listar(db, loja_id, situacao, busca, so_com_estoque)


@router.post("/impressas", summary="Marca as etiquetas como impressas com o preço e a promoção de agora")
def marcar_impressas(db: DB, usuario: UsuarioAtual, dados: MarcarImpressas) -> dict[str, int]:
    return {"marcadas": service.marcar_impressas(db, usuario, dados)}
