from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

QuantidadePositiva = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=3)]
QuantidadeNaoNegativa = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=3)]
Motivo = Annotated[str, Field(min_length=3, max_length=200)]


class ItemEntrada(BaseModel):
    produto_id: UUID
    numero_lote: str | None = Field(default=None, max_length=40)
    validade: date | None = None
    quantidade: QuantidadePositiva
    custo_unitario: Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=4)] | None = None


class EntradaCriar(BaseModel):
    """Entrada de mercadoria, normalmente uma nota de compra com vários itens."""

    loja_id: UUID | None = Field(default=None, description="Loja que recebe a mercadoria. Vazio = matriz")
    itens: Annotated[list[ItemEntrada], Field(min_length=1)]
    observacao: str | None = Field(default=None, max_length=200)


class AjusteCriar(BaseModel):
    """Correção de inventário: informa quanto foi contado no lote."""

    lote_id: UUID
    nova_quantidade: QuantidadeNaoNegativa
    motivo: Motivo


class PerdaCriar(BaseModel):
    """Saída por vencimento, avaria ou extravio."""

    lote_id: UUID
    quantidade: QuantidadePositiva
    motivo: Motivo
    motivo_sngpc: Annotated[int, Field(ge=1, le=10)] | None = Field(
        default=None,
        description="Obrigatório no controlado. 1 furto/roubo, 2 avaria, 3 vencimento, 4 apreensão pela Visa, "
        "5 perda no processo, 6 controle de qualidade, 7 saiu da Portaria 344, 8 desvio de qualidade, "
        "9 recolhimento do fabricante, 10 devolução ao fornecedor",
    )


class ItemTransferencia(BaseModel):
    lote_id: UUID
    quantidade: QuantidadePositiva


class TransferenciaCriar(BaseModel):
    """Leva lotes de uma loja para outra. A loja de origem é a de cada lote."""

    loja_destino_id: UUID
    itens: Annotated[list[ItemTransferencia], Field(min_length=1)]
    observacao: str | None = Field(default=None, max_length=200)


class LoteSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    loja_id: UUID
    produto_id: UUID
    numero_lote: str
    validade: date | None
    quantidade: Decimal


class LoteComProduto(LoteSaida):
    produto_nome: str
    loja_nome: str
    dias_para_vencer: int | None


class MovimentoSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    loja_id: UUID
    produto_id: UUID
    lote_id: UUID
    tipo: str
    quantidade: Decimal
    custo_unitario: Decimal | None
    referencia_tipo: str | None
    referencia_id: UUID | None
    usuario_id: UUID
    motivo: str | None
    motivo_sngpc: int | None = None
    criado_em: datetime


class ProdutoAbaixoMinimo(BaseModel):
    produto_id: UUID
    nome: str
    loja_id: UUID
    loja_nome: str
    saldo: Decimal
    estoque_minimo: Decimal


class Alertas(BaseModel):
    vencidos: list[LoteComProduto]
    vencendo: list[LoteComProduto]
    abaixo_do_minimo: list[ProdutoAbaixoMinimo]


class SaldoProduto(BaseModel):
    produto_id: UUID
    nome: str
    apresentacao: str | None
    ean: str | None
    estoque_minimo: Decimal
    total: Decimal
    por_loja: dict[str, Decimal] = Field(description="Saldo vendável por id da loja")
    vencido: Decimal = Field(description="Quantidade vencida ainda no estoque, em todas as lojas")


class PaginaSaldos(BaseModel):
    itens: list[SaldoProduto]
    total: int
    pagina: int
    por_pagina: int
