from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.cpf import cpf_valido

Dinheiro = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
DinheiroPositivo = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
FormaPagamento = Literal["dinheiro", "debito", "credito", "pix"]


# --- Caixa ---

class CaixaAbrir(BaseModel):
    valor_abertura: Dinheiro = Decimal(0)


class CaixaFechar(BaseModel):
    valor_fechamento_informado: Dinheiro


class CaixaSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    usuario_id: UUID
    status: str
    valor_abertura: Decimal
    aberto_em: datetime
    fechado_em: datetime | None
    valor_fechamento_informado: Decimal | None


class ResumoCaixa(BaseModel):
    caixa: CaixaSaida
    quantidade_vendas: int
    total_vendido: Decimal
    por_forma: dict[str, Decimal]
    dinheiro_esperado: Decimal  # abertura + dinheiro recebido - troco
    diferenca: Decimal | None  # informado - esperado (só depois de fechar)


# --- Venda ---

class ItemVendaCriar(BaseModel):
    produto_id: UUID
    quantidade: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=3)]
    desconto: Dinheiro = Decimal(0)


class PagamentoCriar(BaseModel):
    forma: FormaPagamento
    valor: DinheiroPositivo


class VendaCriar(BaseModel):
    """A venda inteira numa chamada só, enviada quando o operador finaliza no PDV.

    O preço vem sempre do cadastro, nunca do navegador.
    """

    chave_idempotencia: UUID = Field(description="UUID gerado pelo PDV; reenviar a mesma chave não duplica a venda")
    itens: Annotated[list[ItemVendaCriar], Field(min_length=1)]
    pagamentos: Annotated[list[PagamentoCriar], Field(min_length=1)]
    desconto: Dinheiro = Decimal(0)
    cliente_cpf: str | None = None

    @field_validator("cliente_cpf")
    @classmethod
    def _cpf(cls, valor: str | None) -> str | None:
        if valor is None or valor == "":
            return None
        digitos = "".join(c for c in valor if c.isdigit())
        if not cpf_valido(digitos):
            raise ValueError("CPF inválido")
        return digitos


class VendaCancelar(BaseModel):
    motivo: Annotated[str, Field(min_length=3, max_length=200)]


class ItemVendaSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    produto_id: UUID
    descricao: str
    quantidade: Decimal
    preco_unitario: Decimal
    desconto: Decimal
    total: Decimal


class PagamentoSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    forma: str
    valor: Decimal


class VendaSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    numero: int
    caixa_id: UUID
    usuario_id: UUID
    status: str
    subtotal: Decimal
    desconto: Decimal
    total: Decimal
    troco: Decimal
    cliente_cpf: str | None
    finalizada_em: datetime
    cancelada_em: datetime | None
    motivo_cancelamento: str | None
    itens: list[ItemVendaSaida]
    pagamentos: list[PagamentoSaida]
