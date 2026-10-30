from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.fiscal.schemas import NotaFiscalSaida
from app.shared.campos import Cpf

Dinheiro = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
DinheiroPositivo = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
FormaPagamento = Literal["dinheiro", "debito", "credito", "pix", "prazo"]


# --- Caixa ---

class CaixaAbrir(BaseModel):
    valor_abertura: Dinheiro = Decimal(0)


class CaixaFechar(BaseModel):
    valor_fechamento_informado: Dinheiro


class CaixaSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    usuario_id: UUID
    terminal_id: UUID | None
    loja_id: UUID | None
    status: str
    valor_abertura: Decimal
    aberto_em: datetime
    fechado_em: datetime | None
    valor_fechamento_informado: Decimal | None


class ResumoCaixa(BaseModel):
    caixa: CaixaSaida
    operador: str
    terminal: str | None
    loja: str | None
    quantidade_vendas: int
    total_vendido: Decimal
    por_forma: dict[str, Decimal]
    recebimentos_dinheiro: Decimal = Decimal(0)  # contas a receber (fiado) pagas em dinheiro neste caixa
    dinheiro_esperado: Decimal  # abertura + dinheiro recebido - troco + recebimentos em dinheiro
    diferenca: Decimal | None  # informado - esperado (só depois de fechar)


# --- Venda ---

class ItemVendaCriar(BaseModel):
    produto_id: UUID
    quantidade: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=3)]
    desconto: Dinheiro = Decimal(0)


class PagamentoCriar(BaseModel):
    forma: FormaPagamento
    valor: DinheiroPositivo
    vencimento: date | None = Field(default=None, description="Só na venda a prazo. Vazio = prazo padrão da farmácia")


class VendaCriar(BaseModel):
    """A venda inteira numa chamada só, enviada quando o operador finaliza no PDV.

    O preço vem sempre do cadastro, nunca do navegador.
    """

    chave_idempotencia: UUID = Field(description="UUID gerado pelo PDV; reenviar a mesma chave não duplica a venda")
    itens: Annotated[list[ItemVendaCriar], Field(min_length=1)]
    pagamentos: Annotated[list[PagamentoCriar], Field(min_length=1)]
    desconto: Dinheiro = Decimal(0)
    cliente_cpf: Cpf
    cliente_id: UUID | None = Field(default=None, description="Obrigatório na venda a prazo e para usar pontos")
    pontos_resgatados: Annotated[int, Field(ge=0, le=10_000_000)] = Field(
        default=0, description="Pontos do cliente trocados por desconto nesta venda"
    )
    pre_venda_id: UUID | None = Field(default=None, description="Pré-venda que está sendo recebida")


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
    promocao_id: UUID | None = None
    desconto_promocao: Decimal = Decimal(0)


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
    cliente_id: UUID | None = None
    pontos_ganhos: int = 0
    pontos_resgatados: int = 0
    desconto_pontos: Decimal = Decimal(0)
    finalizada_em: datetime
    cancelada_em: datetime | None
    motivo_cancelamento: str | None
    itens: list[ItemVendaSaida]
    pagamentos: list[PagamentoSaida]
    nota: NotaFiscalSaida | None = None


# --- Pré-venda ---

class ItemPreVendaCriar(BaseModel):
    produto_id: UUID
    quantidade: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=3)]


class PreVendaCriar(BaseModel):
    itens: Annotated[list[ItemPreVendaCriar], Field(min_length=1)]
    cliente_cpf: Cpf
    loja_id: UUID | None = Field(default=None, description="Se vazio, usa a loja do PDV ou a matriz")


class ItemPreVendaSaida(BaseModel):
    produto_id: UUID
    ean: str | None
    descricao: str
    quantidade: Decimal
    preco_unitario: Decimal
    total: Decimal


class PreVendaSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    numero: int
    loja_id: UUID
    usuario_id: UUID
    vendedor: str
    status: Literal["aberta", "recebida", "cancelada"]
    itens: list[ItemPreVendaSaida]
    total: Decimal
    cliente_cpf: str | None
    venda_id: UUID | None
    criado_em: datetime
    finalizada_em: datetime | None
