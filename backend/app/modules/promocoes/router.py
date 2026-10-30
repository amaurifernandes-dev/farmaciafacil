from uuid import UUID

from fastapi import APIRouter, status

from app.core.deps import DB, Gerente, UsuarioAtual
from app.modules.promocoes import service
from app.modules.promocoes.schemas import PromocaoAtualizar, PromocaoCriar, PromocaoSaida, Situacao

router = APIRouter(prefix="/promocoes", tags=["promoções"])


@router.get("")
def listar(db: DB, _: UsuarioAtual, situacao: Situacao | None = None) -> list[PromocaoSaida]:
    return service.listar(db, situacao)


@router.get("/{promocao_id}")
def obter(db: DB, _: UsuarioAtual, promocao_id: UUID) -> PromocaoSaida:
    return service.saidas(db, [service.obter(db, promocao_id)])[0]


@router.post("", status_code=status.HTTP_201_CREATED)
def criar(db: DB, usuario: Gerente, dados: PromocaoCriar) -> PromocaoSaida:
    return service.criar(db, usuario, dados)


@router.put("/{promocao_id}")
def atualizar(db: DB, _: Gerente, promocao_id: UUID, dados: PromocaoAtualizar) -> PromocaoSaida:
    return service.atualizar(db, promocao_id, dados)


@router.post("/{promocao_id}/encerrar")
def encerrar(db: DB, _: Gerente, promocao_id: UUID) -> PromocaoSaida:
    return service.encerrar(db, promocao_id)
