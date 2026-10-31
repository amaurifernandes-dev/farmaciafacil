from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.financeiro.models import FORMAS_BAIXA

Tipo = Literal["pagar", "receber"]
FormaBaixa = Literal[FORMAS_BAIXA]
Valor = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
Situacao = Literal["abertas", "vencidas", "pagas", "canceladas", "todas"]


class ContaCriar(BaseModel):
    """Conta lançada à mão. Com mais de uma parcela, o valor é dividido e vence mês a mês."""

    tipo: Tipo
    descricao: Annotated[str, Field(min_length=2, max_length=200)]
    categoria: Annotated[str, Field(max_length=30)]
    valor_total: Valor
    primeiro_vencimento: date
    parcelas: Annotated[int, Field(ge=1, le=60)] = 1
    loja_id: UUID | None = Field(default=None, description="Vazio = matriz")
    fornecedor_id: UUID | None = None
    cliente_id: UUID | None = None
    documento: str | None = Field(default=None, max_length=60)
    observacao: str | None = Field(default=None, max_length=300)


class ContaAtualizar(BaseModel):
    """Só para contas em aberto. Só o que vier é alterado."""

    descricao: Annotated[str, Field(min_length=2, max_length=200)] | None = None
    categoria: Annotated[str, Field(max_length=30)] | None = None
    valor: Valor | None = None
    vencimento: date | None = None
    documento: str | None = Field(default=None, max_length=60)
    observacao: str | None = Field(default=None, max_length=300)


class ContaBaixar(BaseModel):
    """Registra o pagamento (ou recebimento). O valor pode ter juros ou desconto."""

    pago_em: date | None = Field(default=None, description="Vazio = hoje")
    valor_pago: Valor | None = Field(default=None, description="Vazio = o valor da conta")
    forma_pagamento: FormaBaixa
    observacao: str | None = Field(default=None, max_length=300)


class ContaSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tipo: str
    loja_id: UUID
    descricao: str
    categoria: str
    fornecedor_id: UUID | None
    cliente_id: UUID | None
    pessoa: str | None = Field(default=None, description="Nome do fornecedor ou do cliente")
    documento: str | None
    parcela: int
    parcelas: int
    valor: Decimal
    vencimento: date
    status: str
    vencida: bool = False
    pago_em: date | None
    valor_pago: Decimal | None
    forma_pagamento: str | None
    nota_entrada_id: UUID | None
    venda_id: UUID | None
    convenio_id: UUID | None = None
    observacao: str | None
    criado_em: datetime


class Totais(BaseModel):
    vencidas: Decimal
    quantidade_vencidas: int
    vence_hoje: Decimal
    proximos_7_dias: Decimal
    em_aberto: Decimal
    pago_no_mes: Decimal


class PaginaContas(BaseModel):
    itens: list[ContaSaida]
    total: int
    soma: Decimal = Field(description="Soma do valor das contas do filtro (todas as páginas)")
    totais: Totais


class CreditoCliente(BaseModel):
    cliente_id: UUID
    nome: str
    limite: Decimal
    em_aberto: Decimal
    disponivel: Decimal
    vencido: Decimal
    contas: list[ContaSaida]


class DiaFluxo(BaseModel):
    data: date
    vendas: Decimal = Field(description="Recebido no caixa (sem a parte a prazo)")
    recebimentos: Decimal = Field(description="Contas a receber baixadas")
    pagamentos: Decimal = Field(description="Contas a pagar baixadas")
    previsto_receber: Decimal = Field(description="Contas a receber em aberto que vencem no dia")
    previsto_pagar: Decimal = Field(description="Contas a pagar em aberto que vencem no dia")
    saldo: Decimal = Field(description="Entradas menos saídas do dia (realizado + previsto)")
    acumulado: Decimal


class FluxoCaixa(BaseModel):
    inicio: date
    fim: date
    dias: list[DiaFluxo]
    entradas: Decimal
    saidas: Decimal
    resultado: Decimal
    vencido_receber: Decimal = Field(description="A receber em aberto com vencimento antes do início")
    vencido_pagar: Decimal = Field(description="A pagar em aberto com vencimento antes do início")


class Categoria(BaseModel):
    id: str
    nome: str


class Categorias(BaseModel):
    pagar: list[Categoria]
    receber: list[Categoria]
