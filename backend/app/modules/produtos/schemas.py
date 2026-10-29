from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Ean = Annotated[str, Field(pattern=r"^\d{8,14}$", description="Somente dígitos, 8 a 14")]
Preco = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
Quantidade = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=3)]
TipoProduto = Literal["medicamento", "perfumaria", "outros"]


class ProdutoBase(BaseModel):
    ean: Ean | None = None
    nome: Annotated[str, Field(min_length=1, max_length=200)]
    apresentacao: str | None = Field(default=None, max_length=200)
    fabricante: str | None = Field(default=None, max_length=120)
    ncm: str | None = Field(default=None, pattern=r"^\d{8}$")
    cest: str | None = Field(default=None, pattern=r"^\d{7}$")
    unidade: str = Field(default="UN", max_length=6)
    preco_venda: Preco
    preco_custo: Preco | None = None
    estoque_minimo: Quantidade = Decimal(0)
    controla_lote: bool = True
    tipo: TipoProduto = "outros"
    registro_ms: str | None = Field(default=None, max_length=20)


class ProdutoCriar(ProdutoBase):
    pass


class ProdutoAtualizar(BaseModel):
    """Todos os campos são opcionais: só o que vier é alterado."""

    ean: Ean | None = None
    nome: str | None = Field(default=None, min_length=1, max_length=200)
    apresentacao: str | None = Field(default=None, max_length=200)
    fabricante: str | None = Field(default=None, max_length=120)
    ncm: str | None = Field(default=None, pattern=r"^\d{8}$")
    cest: str | None = Field(default=None, pattern=r"^\d{7}$")
    unidade: str | None = Field(default=None, max_length=6)
    preco_venda: Preco | None = None
    preco_custo: Preco | None = None
    estoque_minimo: Quantidade | None = None
    controla_lote: bool | None = None
    tipo: TipoProduto | None = None
    registro_ms: str | None = Field(default=None, max_length=20)
    ativo: bool | None = None


class CodigoSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ean: str


class ProdutoSaida(ProdutoBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ativo: bool
    codigos: list[CodigoSaida]
    criado_em: datetime
    atualizado_em: datetime


class ProdutoPDV(ProdutoSaida):
    saldo: Decimal = Decimal(0)


class CodigoCriar(BaseModel):
    ean: Ean


class PaginaProdutos(BaseModel):
    itens: list[ProdutoSaida]
    total: int
    pagina: int
    por_pagina: int
