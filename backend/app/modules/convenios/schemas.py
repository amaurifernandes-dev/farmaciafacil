from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.campos import CnpjOpcional, Email, Telefone, texto

Dinheiro = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
Percentual = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]


def _virgula(valor):
    """A tela manda "150,00"; o padrão da API é "150.00"."""
    if isinstance(valor, str):
        valor = valor.strip().replace(".", "").replace(",", ".") if "," in valor else valor.strip()
        return valor or None
    return valor


class ConvenioDados(BaseModel):
    cnpj: CnpjOpcional
    contato: texto(120)
    telefone: Telefone
    email: Email
    observacao: texto(300)

    _numeros = field_validator("desconto", "limite_padrao", mode="before", check_fields=False)(_virgula)


class ConvenioCriar(ConvenioDados):
    nome: Annotated[str, Field(min_length=2, max_length=120)]
    desconto: Percentual = Decimal(0)
    limite_padrao: Dinheiro = Field(description="Quanto cada funcionário pode comprar até o fechamento")
    dia_fechamento: Annotated[int, Field(ge=1, le=28)] = 25
    dias_para_pagar: Annotated[int, Field(ge=0, le=90)] = 10


class ConvenioAtualizar(ConvenioDados):
    """Só o que vier é alterado."""

    nome: Annotated[str, Field(min_length=2, max_length=120)] | None = None
    desconto: Percentual | None = None
    limite_padrao: Dinheiro | None = None
    dia_fechamento: Annotated[int, Field(ge=1, le=28)] | None = None
    dias_para_pagar: Annotated[int, Field(ge=0, le=90)] | None = None
    ativo: bool | None = None


class ConvenioSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    cnpj: str | None
    contato: str | None
    telefone: str | None
    email: str | None
    desconto: Decimal
    limite_padrao: Decimal
    dia_fechamento: int
    dias_para_pagar: int
    observacao: str | None
    ativo: bool
    criado_em: datetime


class ConvenioResumo(ConvenioSaida):
    funcionarios: int = 0
    em_aberto: Decimal = Decimal(0)  # compras ainda não faturadas
    a_receber: Decimal = Decimal(0)  # faturas abertas
    fechamento: date = Field(description="Data do último fechamento previsto (as compras até ela vão para a fatura)")
    pronto_para_fechar: bool = False


class Funcionario(BaseModel):
    cliente_id: UUID
    nome: str
    cpf: str | None
    matricula: str | None
    limite: Decimal
    usado: Decimal
    disponivel: Decimal
    ativo: bool


class CompraSaida(BaseModel):
    id: UUID
    venda_id: UUID
    venda_numero: int
    cliente_id: UUID
    nome: str
    matricula: str | None
    data: date
    valor: Decimal
    status: str
    conta_id: UUID | None


class FaturaSaida(BaseModel):
    conta_id: UUID
    descricao: str
    valor: Decimal
    vencimento: date
    status: str  # aberta, paga
    vencida: bool
    pago_em: date | None
    compras: int


class ConvenioDetalhe(BaseModel):
    convenio: ConvenioResumo
    funcionarios: list[Funcionario]
    compras_abertas: list[CompraSaida]
    faturas: list[FaturaSaida]


class Fechar(BaseModel):
    ate: date | None = Field(default=None, description="Compras até esta data entram na fatura. Vazio: o fechamento previsto")


class ConvenioDoCliente(BaseModel):
    """O que o PDV precisa para vender no convênio."""

    convenio_id: UUID
    nome: str
    desconto: Decimal
    limite: Decimal
    usado: Decimal
    disponivel: Decimal
