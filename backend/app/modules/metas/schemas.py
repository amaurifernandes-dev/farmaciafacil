from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

# batida: já vendeu a meta; no_ritmo: no passo de hoje, bate até o fim do mês;
# abaixo: no passo de hoje, não bate; nao_batida: o mês acabou sem bater;
# nao_comecou: mês que ainda vem; sem_meta: ninguém definiu a meta.
Situacao = Literal["batida", "no_ritmo", "abaixo", "nao_batida", "nao_comecou", "sem_meta"]


class Andamento(BaseModel):
    id: UUID | None  # a loja ou o vendedor; nulo no total da farmácia
    nome: str
    detalhe: str | None = None
    meta: Decimal | None
    vendido: Decimal
    vendas: int
    vendido_hoje: Decimal
    percentual: Decimal | None  # vendido / meta
    esperado_ate_hoje: Decimal | None  # quanto já devia ter vendido, no passo certo
    projecao: Decimal | None  # quanto vai vender no mês se continuar no passo de hoje
    falta: Decimal | None
    por_dia: Decimal | None  # quanto vender por dia (contando hoje) para bater
    situacao: Situacao
    vendido_mes_passado: Decimal


class MetasDoMes(BaseModel):
    mes: date
    dias_no_mes: int
    dias_passados: int  # contando hoje
    dias_restantes: int  # contando hoje
    total: Andamento
    lojas: list[Andamento]
    vendedores: list[Andamento]


class ValorDaMeta(BaseModel):
    id: UUID
    valor: Decimal | None = Field(None, gt=0, max_digits=12, decimal_places=2)  # nulo apaga a meta


class SalvarMetas(BaseModel):
    mes: date
    lojas: list[ValorDaMeta] = Field(default_factory=list, max_length=200)
    vendedores: list[ValorDaMeta] = Field(default_factory=list, max_length=500)
