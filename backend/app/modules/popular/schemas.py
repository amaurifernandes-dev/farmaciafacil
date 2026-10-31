from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from app.modules.financeiro.schemas import ContaSaida
from app.shared.campos import CpfObrigatorio, Uf


def _limpo(valor: object) -> object:
    if isinstance(valor, str):
        return "".join(valor.split()).upper()
    return valor


Mes = Annotated[str, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="Ano e mês, ex.: 2026-10")]


class PopularDados(BaseModel):
    """O que o balconista copia da receita e do sistema autorizador do governo."""

    paciente_cpf: CpfObrigatorio
    paciente_nome: Annotated[str, Field(min_length=3, max_length=120)]
    prescritor_crm: Annotated[str, BeforeValidator(_limpo), Field(min_length=1, max_length=20)]
    prescritor_uf: Uf
    receita_data: date
    autorizacao: Annotated[
        str, BeforeValidator(_limpo), Field(min_length=4, max_length=40, pattern=r"^[0-9A-Z./-]+$")
    ] = Field(description="Número que o autorizador da Farmácia Popular devolve")


class ItemPopular(BaseModel):
    produto_id: UUID
    descricao: str
    quantidade: Decimal
    total: Decimal
    governo: Decimal


class VendaPopularSaida(PopularDados):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    venda_id: UUID
    loja_id: UUID
    numero: int = 0
    data: date
    itens: list[ItemPopular]
    valor_governo: Decimal
    valor_paciente: Decimal
    status: str
    conta_id: UUID | None


class Lancar(BaseModel):
    mes: Mes


class MesPopular(BaseModel):
    mes: str
    vendas: list[VendaPopularSaida]
    quantidade: int
    pacientes: int
    total_governo: Decimal
    total_paciente: Decimal
    em_aberto: Decimal = Field(description="Parte do governo ainda não lançada no Financeiro")
    lancamentos: list[ContaSaida]
    pode_lancar: bool
