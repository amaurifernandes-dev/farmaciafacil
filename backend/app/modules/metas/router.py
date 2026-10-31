from datetime import date

from fastapi import APIRouter

from app.core.deps import DB, Gerente, UsuarioAtual
from app.modules.metas import service
from app.modules.metas.schemas import Andamento, MetasDoMes, SalvarMetas
from app.shared.datas import hoje

router = APIRouter(prefix="/metas", tags=["metas"])


@router.get("", response_model=MetasDoMes, summary="Metas do mês e o andamento de cada loja e vendedor")
def do_mes(db: DB, _: Gerente, mes: date | None = None) -> MetasDoMes:
    return service.do_mes(db, mes or hoje())


@router.put("", response_model=MetasDoMes, summary="Define as metas do mês (valor nulo apaga)")
def salvar(db: DB, _: Gerente, dados: SalvarMetas) -> MetasDoMes:
    return service.salvar(db, dados)


@router.get("/minha", response_model=Andamento | None, summary="A meta do mês de quem está usando")
def minha(db: DB, usuario: UsuarioAtual) -> Andamento | None:
    return service.do_vendedor(db, usuario.usuario_id)
