from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

Motivo = Literal["nunca_impressa", "preco_subiu", "preco_baixou", "promocao_comecou", "promocao_acabou",
                 "promocao_mudou"]


class Impressa(BaseModel):
    preco: Decimal
    preco_promocional: Decimal | None
    promocao: str | None
    impressa_em: datetime


class EtiquetaItem(BaseModel):
    produto_id: UUID
    nome: str
    apresentacao: str | None
    fabricante: str | None
    ean: str | None
    unidade: str
    preco: Decimal = Field(description="Preço normal de hoje")
    preco_promocional: Decimal | None = Field(description="Preço de 1 unidade na promoção de hoje")
    promocao: str | None = Field(description="O que vai na etiqueta: 'Por R$ 9,90', 'Leve 3, pague 2'...")
    promocao_fim: date | None
    saldo: Decimal
    impressa: Impressa | None = Field(description="O que está na gôndola agora")
    motivo: Motivo | None = Field(description="Por que trocar a etiqueta. Vazio: está certa")


class ListaEtiquetas(BaseModel):
    loja_id: UUID
    itens: list[EtiquetaItem]
    para_trocar: int
    nunca_impressas: int
    preco_mudou: int
    promocao: int


class MarcarImpressas(BaseModel):
    loja_id: UUID | None = Field(default=None, description="Vazio: a matriz")
    produto_ids: Annotated[list[UUID], Field(min_length=1, max_length=2000)]


Situacao = Literal["trocar", "todas"]
