from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.deps import DB, Estoquista
from app.modules.compras import pedidos, service
from app.modules.compras.schemas import (
    ItemAtualizar,
    NotaImportar,
    NotaPedido,
    NotaResumo,
    NotaSaida,
    PedidoCompraCriar,
    PedidoCompraResumo,
    PedidoCompraSaida,
    SugestaoCompras,
)

router = APIRouter(prefix="/compras", tags=["compras"])


@router.get("/notas")
def listar_notas(
    db: DB,
    _: Estoquista,
    status_nota: Annotated[Literal["pendente", "confirmada", "cancelada"] | None, Query(alias="status")] = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=100)] = 30,
) -> list[NotaResumo]:
    return service.listar(db, status_nota, pagina, por_pagina)


@router.post("/notas", status_code=status.HTTP_201_CREATED)
def importar_nota(db: DB, usuario: Estoquista, dados: NotaImportar) -> NotaSaida:
    """Lê o XML da NF-e de compra. A nota fica pendente até alguém conferir e confirmar."""
    return service.saida(db, service.importar(db, usuario, dados))


@router.get("/notas/{nota_id}")
def obter_nota(db: DB, _: Estoquista, nota_id: UUID) -> NotaSaida:
    return service.saida(db, service.obter(db, nota_id))


@router.patch("/notas/{nota_id}/itens/{item_id}")
def atualizar_item(db: DB, _: Estoquista, nota_id: UUID, item_id: UUID, dados: ItemAtualizar) -> NotaSaida:
    return service.saida(db, service.atualizar_item(db, nota_id, item_id, dados))


@router.post("/notas/{nota_id}/confirmar")
def confirmar_nota(db: DB, usuario: Estoquista, nota_id: UUID) -> NotaSaida:
    """Dá entrada de todos os itens no estoque da loja da nota."""
    return service.saida(db, service.confirmar(db, usuario, nota_id))


@router.post("/notas/{nota_id}/cancelar")
def cancelar_nota(db: DB, _: Estoquista, nota_id: UUID) -> NotaSaida:
    return service.saida(db, service.cancelar(db, nota_id))


@router.patch("/notas/{nota_id}/pedido")
def ligar_pedido(db: DB, _: Estoquista, nota_id: UUID, dados: NotaPedido) -> NotaSaida:
    """Escolhe com qual pedido de compra a nota é conferida (ou nenhum)."""
    return service.saida(db, service.ligar_pedido(db, nota_id, dados.pedido_id))


@router.post("/pedidos", status_code=status.HTTP_201_CREATED)
def criar_pedido(db: DB, usuario: Estoquista, dados: PedidoCompraCriar) -> PedidoCompraSaida:
    """Guarda o pedido feito a um fornecedor, para conferir quando a nota chegar."""
    return pedidos.saida(db, pedidos.criar(db, usuario, dados))


@router.get("/pedidos")
def listar_pedidos(
    db: DB,
    _: Estoquista,
    status_pedido: Annotated[
        Literal["abertos", "aberto", "enviado", "parcial", "recebido", "cancelado"] | None, Query(alias="status")
    ] = None,
    fornecedor_id: UUID | None = None,
) -> list[PedidoCompraResumo]:
    return pedidos.listar(db, status_pedido, fornecedor_id)


@router.get("/pedidos/{pedido_id}")
def obter_pedido(db: DB, _: Estoquista, pedido_id: UUID) -> PedidoCompraSaida:
    return pedidos.saida(db, pedidos.obter(db, pedido_id))


@router.post("/pedidos/{pedido_id}/enviado")
def marcar_enviado(db: DB, _: Estoquista, pedido_id: UUID) -> PedidoCompraSaida:
    return pedidos.saida(db, pedidos.marcar_enviado(db, pedido_id))


@router.post("/pedidos/{pedido_id}/cancelar")
def cancelar_pedido(db: DB, _: Estoquista, pedido_id: UUID) -> PedidoCompraSaida:
    return pedidos.saida(db, pedidos.cancelar(db, pedido_id))


@router.get("/sugestao")
def sugestao(
    db: DB,
    _: Estoquista,
    loja_id: UUID | None = None,
    dias_historico: Annotated[int, Query(ge=7, le=365)] = 30,
    dias_cobertura: Annotated[int, Query(ge=1, le=180)] = 15,
) -> SugestaoCompras:
    """O que comprar, com base nas vendas recentes da loja e no estoque mínimo."""
    return service.sugestao(db, loja_id, dias_historico, dias_cobertura)
