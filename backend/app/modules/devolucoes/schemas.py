from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Destino = Literal["dinheiro", "vale"]
Quantidade = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=3)]


class ItemDevolver(BaseModel):
    venda_item_id: UUID
    quantidade: Quantidade
    volta_estoque: bool | None = Field(
        default=None, description="Vazio: volta para o estoque, menos remédio (que vira descarte)"
    )


class DevolucaoCriar(BaseModel):
    venda_id: UUID
    itens: Annotated[list[ItemDevolver], Field(min_length=1)]
    destino: Destino = Field(description="dinheiro sai do caixa aberto; vale gera um vale-troca para o cliente")
    motivo: Annotated[str, Field(min_length=3, max_length=200)]


class ValeSaida(BaseModel):
    id: UUID
    codigo: str
    valor: Decimal
    saldo: Decimal
    validade: date
    status: Literal["ativo", "usado", "cancelado", "vencido"]
    cliente_id: UUID | None
    cliente_nome: str | None
    criado_em: datetime


class ItemDevolucaoSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    venda_item_id: UUID
    produto_id: UUID
    descricao: str
    quantidade: Decimal
    valor: Decimal
    volta_estoque: bool


class DevolucaoSaida(BaseModel):
    id: UUID
    numero: int
    venda_id: UUID
    venda_numero: int
    loja_id: UUID
    loja: str
    usuario: str
    destino: Destino
    valor_total: Decimal
    motivo: str
    criado_em: datetime
    itens: list[ItemDevolucaoSaida]
    vale: ValeSaida | None


class ItemDevolvivel(BaseModel):
    venda_item_id: UUID
    produto_id: UUID
    descricao: str
    tipo_produto: str
    quantidade: Decimal = Field(description="Quanto foi vendido")
    devolvida: Decimal
    disponivel: Decimal
    valor_pago: Decimal = Field(description="O que o cliente pagou pela linha, já com os descontos da venda")
    valor_unitario: Decimal
    bloqueio: str | None = Field(description="Por que este item não pode ser devolvido aqui")
    volta_estoque_sugerido: bool


class VendaParaDevolver(BaseModel):
    venda_id: UUID
    numero: int
    finalizada_em: datetime
    status: str
    total: Decimal
    cliente_id: UUID | None
    cliente_nome: str | None
    formas: list[str]
    bloqueio: str | None = Field(description="Por que a venda inteira não aceita devolução")
    itens: list[ItemDevolvivel]
    devolucoes: list[DevolucaoSaida]


class ListaDevolucoes(BaseModel):
    itens: list[DevolucaoSaida]
    quantidade: int
    total: Decimal
    em_dinheiro: Decimal
    em_vale: Decimal
