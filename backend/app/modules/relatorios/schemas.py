from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ResumoVendas(BaseModel):
    quantidade: int
    faturamento: Decimal = Field(description="Total das vendas finalizadas, já com descontos e sem as devoluções")
    devolucoes: int = 0
    valor_devolvido: Decimal = Field(default=Decimal(0), description="Já tirado do faturamento")
    descontos: Decimal
    descontos_promocao: Decimal
    ticket_medio: Decimal
    custo: Decimal = Field(description="Custo das mercadorias vendidas (pelo custo do produto na hora da venda)")
    lucro_bruto: Decimal
    margem: Decimal = Field(description="Lucro bruto sobre o faturamento, em %")
    itens_sem_custo: int = Field(description="Itens vendidos sem custo cadastrado: ficam fora do lucro")
    canceladas: int
    valor_cancelado: Decimal


class DiaVendas(BaseModel):
    data: date
    quantidade: int
    total: Decimal


class FormaVendas(BaseModel):
    forma: str
    valor: Decimal


class OperadorVendas(BaseModel):
    nome: str
    quantidade: int
    total: Decimal


class RelatorioVendas(BaseModel):
    inicio: date
    fim: date
    resumo: ResumoVendas
    anterior: ResumoVendas = Field(description="O mesmo número de dias logo antes, para comparar")
    por_dia: list[DiaVendas]
    por_forma: list[FormaVendas]
    por_operador: list[OperadorVendas]


class ProdutoVendido(BaseModel):
    produto_id: UUID
    nome: str
    quantidade: Decimal
    faturamento: Decimal
    custo: Decimal | None
    lucro: Decimal | None
    margem: Decimal | None
    participacao: Decimal = Field(description="% do faturamento do período")
    curva: Literal["A", "B", "C"]


class RelatorioProdutos(BaseModel):
    inicio: date
    fim: date
    faturamento: Decimal
    produtos: list[ProdutoVendido]
    curva_a: int
    curva_b: int
    curva_c: int


class ProdutoParado(BaseModel):
    produto_id: UUID
    nome: str
    saldo: Decimal
    custo_unitario: Decimal | None
    valor_parado: Decimal | None
    ultima_venda: datetime | None
    dias_parado: int | None = Field(description="Dias desde a última venda; vazio se nunca vendeu")
    validade_mais_proxima: date | None


class RelatorioParados(BaseModel):
    dias: int
    produtos: list[ProdutoParado]
    valor_total: Decimal
