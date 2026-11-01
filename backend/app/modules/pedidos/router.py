from collections.abc import Iterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.deps import DB, Atendimento, UsuarioAtual
from app.modules.farmacias.models import Farmacia
from app.modules.pedidos import service
from app.modules.pedidos.schemas import (
    Catalogo,
    ListaPedidos,
    LojaPublica,
    PedidoBalcaoCriar,
    PedidoCancelar,
    PedidoCriar,
    PedidoPublico,
    PedidoSaida,
    Situacao,
)
from app.shared.erros import NaoEncontrado

pedidos = APIRouter(prefix="/pedidos", tags=["pedidos"])


@pedidos.get("")
def listar(db: DB, _: UsuarioAtual, situacao: Situacao = "abertos", loja_id: UUID | None = None) -> ListaPedidos:
    return service.listar(db, situacao, loja_id)


@pedidos.get("/{pedido_id}")
def obter(db: DB, _: UsuarioAtual, pedido_id: UUID) -> PedidoSaida:
    return service.saidas(db, [service.obter(db, pedido_id)])[0]


@pedidos.post("", status_code=status.HTTP_201_CREATED)
def criar(db: DB, usuario: Atendimento, dados: PedidoBalcaoCriar) -> PedidoSaida:
    """Anota um pedido que chegou pelo WhatsApp ou pelo telefone."""
    return service.criar_no_balcao(db, usuario, dados)


@pedidos.post("/{pedido_id}/confirmar")
def confirmar(db: DB, usuario: Atendimento, pedido_id: UUID) -> PedidoSaida:
    return service.confirmar(db, usuario, pedido_id)


@pedidos.post("/{pedido_id}/pronto")
def pronto(db: DB, _: Atendimento, pedido_id: UUID) -> PedidoSaida:
    return service.pronto(db, pedido_id)


@pedidos.post("/{pedido_id}/saiu")
def saiu(db: DB, _: Atendimento, pedido_id: UUID) -> PedidoSaida:
    return service.saiu(db, pedido_id)


@pedidos.post("/{pedido_id}/entregue")
def entregue(db: DB, _: Atendimento, pedido_id: UUID) -> PedidoSaida:
    return service.entregue(db, pedido_id)


@pedidos.post("/{pedido_id}/pix-recebido")
def pix_recebido(db: DB, usuario: Atendimento, pedido_id: UUID) -> PedidoSaida:
    """Marca o Pix do pedido como recebido (a equipe conferiu no extrato do banco)."""
    return service.pix_recebido(db, usuario, pedido_id)


@pedidos.post("/{pedido_id}/cancelar")
def cancelar(db: DB, _: Atendimento, pedido_id: UUID, dados: PedidoCancelar) -> PedidoSaida:
    return service.cancelar(db, pedido_id, dados.motivo)


# --- Loja online: sem login ---

def _db_da_loja(endereco: str) -> Iterator[Session]:
    """Acha a farmácia pelo endereço da loja e prende a sessão a ela, como no login."""
    with SessionLocal() as busca:
        farmacia_id = busca.scalar(text("SELECT loja_online_farmacia(:endereco)"), {"endereco": endereco})
    if farmacia_id is None:
        raise NaoEncontrado("Loja não encontrada")
    db = SessionLocal(info={"farmacia_id": farmacia_id})
    try:
        yield db
    finally:
        db.close()


DBLoja = Annotated[Session, Depends(_db_da_loja)]


def _farmacia(db: Session) -> Farmacia:
    return db.get(Farmacia, db.info["farmacia_id"])


def _loja_online_disponivel() -> None:
    """Instalado na farmácia, o sistema não fica na internet: a loja online não existe."""
    if not get_settings().loja_online_disponivel:
        raise NaoEncontrado("Loja não encontrada")


loja = APIRouter(
    prefix="/loja/{endereco}", tags=["loja online"], dependencies=[Depends(_loja_online_disponivel)]
)


@loja.get("")
def dados_da_loja(db: DBLoja) -> LojaPublica:
    return service.loja_publica(db, _farmacia(db))


@loja.get("/produtos")
def produtos(
    db: DBLoja,
    busca: Annotated[str | None, Query(max_length=100)] = None,
    pagina: Annotated[int, Query(ge=1, le=500)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=60)] = 24,
) -> Catalogo:
    return service.catalogo(db, _farmacia(db), busca, pagina, por_pagina)


@loja.post("/pedidos", status_code=status.HTTP_201_CREATED)
def fazer_pedido(db: DBLoja, dados: PedidoCriar) -> PedidoPublico:
    return service.criar_pelo_site(db, _farmacia(db), dados)


@loja.get("/pedidos/{codigo}")
def acompanhar(db: DBLoja, codigo: Annotated[str, Path(max_length=16)]) -> PedidoPublico:
    return service.acompanhar(db, _farmacia(db), codigo)
