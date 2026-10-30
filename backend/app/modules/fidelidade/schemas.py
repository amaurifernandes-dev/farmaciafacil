from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MovimentoSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tipo: str
    pontos: int
    venda_id: UUID | None
    venda_numero: int | None = None
    observacao: str | None
    criado_em: datetime


class Pontos(BaseModel):
    """O que o PDV e a ficha precisam saber dos pontos do cliente."""

    ativo: bool = Field(description="A farmácia usa o programa de fidelidade")
    saldo: int
    valor: Decimal = Field(description="Quanto o saldo vale de desconto, em reais")
    valor_ponto: Decimal
    minimo_resgate: int
    pode_resgatar: bool
    expiram_em: date | None = Field(description="Se o cliente não comprar até essa data, os pontos expiram")
    movimentos: list[MovimentoSaida] = []


class AjustePontos(BaseModel):
    pontos: Annotated[int, Field(ge=-1_000_000, le=1_000_000)]
    observacao: Annotated[str, Field(min_length=3, max_length=200)]
