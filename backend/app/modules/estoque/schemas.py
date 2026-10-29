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


class LoteSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    produto_id: UUID
    numero_lote: str
    validade: date | None
    quantidade: Decimal


class LoteComProduto(LoteSaida):
    produto_nome: str
    dias_para_vencer: int | None


class MovimentoSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    produto_id: UUID
    lote_id: UUID
    tipo: str
    quantidade: Decimal
    custo_unitario: Decimal | None
    referencia_tipo: str | None
    referencia_id: UUID | None
    usuario_id: UUID
    motivo: str | None
    criado_em: datetime


class ProdutoAbaixoMinimo(BaseModel):
    produto_id: UUID
    nome: str
    saldo: Decimal
    estoque_minimo: Decimal


class Alertas(BaseModel):
    vencidos: list[LoteComProduto]
    vencendo: list[LoteComProduto]
    abaixo_do_minimo: list[ProdutoAbaixoMinimo]
