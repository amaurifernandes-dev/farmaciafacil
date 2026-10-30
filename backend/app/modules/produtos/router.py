from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.deps import DB, Estoquista
from app.modules.estoque.service import saldo_vendavel
from app.modules.lojas.deps import TerminalAtual
from app.modules.produtos import service
from app.modules.promocoes.service import para_pdv, vigentes_por_produto
from app.modules.produtos.schemas import (
    CodigoCriar,
    PaginaProdutos,
    ProdutoAtualizar,
    ProdutoCriar,
    ProdutoPDV,
    ProdutoSaida,
)

router = APIRouter(prefix="/produtos", tags=["produtos"])


@router.get("")
def listar(
    db: DB,
    busca: str | None = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=100)] = 50,
    incluir_inativos: bool = False,
) -> PaginaProdutos:
    itens, total = service.listar(db, busca, pagina, por_pagina, incluir_inativos)
    return PaginaProdutos(
        itens=[ProdutoSaida.model_validate(p) for p in itens],
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
    )


@router.get("/ean/{ean}")
def obter_por_ean(db: DB, terminal: TerminalAtual, ean: str, loja_id: UUID | None = None) -> ProdutoPDV:
    """Usado pelo PDV a cada bipada: devolve o produto com o saldo vendável.

    O saldo é o da loja informada; se nenhuma vier, o da loja deste PDV; fora de um PDV, o de todas.
    """
    produto = service.obter_por_ean(db, ean)
    if loja_id is None and terminal is not None:
        loja_id = terminal.loja_id
    promocoes = vigentes_por_produto(db, [produto.id], loja_id).get(produto.id, [])
    return ProdutoPDV.model_validate(produto).model_copy(
        update={"saldo": saldo_vendavel(db, produto.id, loja_id), "promocoes": para_pdv(promocoes)}
    )


@router.get("/{produto_id}")
def obter(db: DB, produto_id: UUID) -> ProdutoSaida:
    return service.obter(db, produto_id)


@router.post("", status_code=status.HTTP_201_CREATED)
def criar(db: DB, _: Estoquista, dados: ProdutoCriar) -> ProdutoSaida:
    return service.criar(db, dados)


@router.patch("/{produto_id}")
def atualizar(db: DB, _: Estoquista, produto_id: UUID, dados: ProdutoAtualizar) -> ProdutoSaida:
    return service.atualizar(db, produto_id, dados)


@router.post("/{produto_id}/codigos", status_code=status.HTTP_201_CREATED)
def adicionar_codigo(db: DB, _: Estoquista, produto_id: UUID, dados: CodigoCriar) -> ProdutoSaida:
    return service.adicionar_codigo(db, produto_id, dados.ean)


@router.delete("/{produto_id}/codigos/{codigo_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_codigo(db: DB, _: Estoquista, produto_id: UUID, codigo_id: UUID) -> None:
    service.remover_codigo(db, produto_id, codigo_id)
