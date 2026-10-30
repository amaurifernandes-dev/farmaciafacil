from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Tipo = Literal["percentual", "preco_fixo", "leve_pague"]
Situacao = Literal["vigente", "agendada", "encerrada", "pausada"]


class PromocaoDados(BaseModel):
    nome: Annotated[str, Field(min_length=2, max_length=120)]
    tipo: Tipo
    percentual: Annotated[Decimal, Field(gt=0, lt=100, max_digits=5, decimal_places=2)] | None = None
    preco: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)] | None = None
    leve: Annotated[int, Field(ge=2, le=100)] | None = None
    pague: Annotated[int, Field(ge=1, le=99)] | None = None
    inicio: date
    fim: date | None = None
    so_clientes: bool = False
    loja_id: UUID | None = Field(default=None, description="Vazio = todas as lojas")
    produto_ids: Annotated[list[UUID], Field(min_length=1, max_length=500)]

    @model_validator(mode="after")
    def _regra_do_tipo(self):
        if self.tipo == "percentual" and self.percentual is None:
            raise ValueError("Informe o percentual de desconto")
        if self.tipo == "preco_fixo" and self.preco is None:
            raise ValueError("Informe o preço da promoção")
        if self.tipo == "leve_pague" and (self.leve is None or self.pague is None or self.pague >= self.leve):
            raise ValueError("Em leve e pague, o 'pague' precisa ser menor que o 'leve' (ex.: leve 3, pague 2)")
        if self.fim is not None and self.fim < self.inicio:
            raise ValueError("O fim da promoção não pode ser antes do início")
        return self


class PromocaoCriar(PromocaoDados):
    pass


class PromocaoAtualizar(PromocaoDados):
    ativa: bool = True


class ProdutoDaPromocao(BaseModel):
    id: UUID
    nome: str
    preco_venda: Decimal
    preco_promocional: Decimal | None = Field(description="Preço da unidade na promoção; vazio no leve e pague")


class Resultado(BaseModel):
    vendas: int
    unidades: Decimal
    faturado: Decimal
    desconto: Decimal


class PromocaoSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    tipo: str
    percentual: Decimal | None
    preco: Decimal | None
    leve: int | None
    pague: int | None
    inicio: date
    fim: date | None
    so_clientes: bool
    loja_id: UUID | None
    ativa: bool
    situacao: Situacao
    resumo: str = Field(description="A regra em uma frase, ex.: 'Leve 3, pague 2'")
    produtos: list[ProdutoDaPromocao]
    resultado: Resultado
    criado_em: datetime


class PromocaoPDV(BaseModel):
    """O que o PDV precisa para calcular o desconto igual ao servidor."""

    id: UUID
    nome: str
    tipo: str
    percentual: Decimal | None
    preco: Decimal | None
    leve: int | None
    pague: int | None
    so_clientes: bool
    resumo: str
