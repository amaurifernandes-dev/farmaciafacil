from uuid import UUID

from fastapi import APIRouter, Response, status

from app.core.deps import DB, Estoquista, UsuarioAtual
from app.modules.inventario import service
from app.modules.inventario.schemas import (
    Contar,
    InventarioCriar,
    InventarioDetalhe,
    InventarioSaida,
    ItemSaida,
)

router = APIRouter(prefix="/inventarios", tags=["inventário"])


@router.get("", response_model=list[InventarioSaida], summary="Inventários, do mais novo ao mais antigo")
def listar(db: DB, _: UsuarioAtual) -> list[InventarioSaida]:
    return service.listar(db)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=InventarioSaida,
             summary="Abre uma contagem na loja (uma aberta por loja)")
def abrir(db: DB, usuario: Estoquista, dados: InventarioCriar) -> InventarioSaida:
    return service.abrir(db, usuario, dados)


@router.get("/{inventario_id}", response_model=InventarioDetalhe, summary="O que já foi contado e as diferenças")
def detalhe(db: DB, usuario: UsuarioAtual, inventario_id: UUID) -> InventarioDetalhe:
    return service.detalhe(db, usuario, inventario_id)


@router.post("/{inventario_id}/contar", response_model=ItemSaida, summary="Conta um produto (bipada ou digitado)")
def contar(db: DB, usuario: UsuarioAtual, inventario_id: UUID, dados: Contar) -> ItemSaida:
    return service.contar(db, usuario, inventario_id, dados)


@router.delete("/{inventario_id}/itens/{produto_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Apaga a contagem de um produto")
def remover_item(db: DB, _: UsuarioAtual, inventario_id: UUID, produto_id: UUID) -> Response:
    service.remover_item(db, inventario_id, produto_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{inventario_id}/finalizar", response_model=InventarioSaida,
             summary="Encerra e ajusta o estoque para o que foi contado")
def finalizar(db: DB, usuario: Estoquista, inventario_id: UUID) -> InventarioSaida:
    return service.finalizar(db, usuario, inventario_id)


@router.post("/{inventario_id}/cancelar", response_model=InventarioSaida, summary="Cancela sem mexer no estoque")
def cancelar(db: DB, _: Estoquista, inventario_id: UUID) -> InventarioSaida:
    return service.cancelar(db, inventario_id)


@router.get("/{inventario_id}/planilha", summary="Planilha (CSV) da contagem")
def planilha(db: DB, usuario: Estoquista, inventario_id: UUID) -> Response:
    nome, conteudo = service.planilha_csv(db, usuario, inventario_id)
    return Response(conteudo, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"'})
