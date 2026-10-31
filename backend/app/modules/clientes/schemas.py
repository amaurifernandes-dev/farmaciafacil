from decimal import Decimal
from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.fidelidade.schemas import Pontos
from app.shared.campos import Cep, Cpf, Email, Telefone, UfOpcional, texto

Nome = Annotated[str, Field(min_length=1, max_length=120)]


class ClienteDados(BaseModel):
    cpf: Cpf
    data_nascimento: date | None = None
    telefone: Telefone
    email: Email
    cep: Cep
    endereco: texto(200)
    bairro: texto(100)
    cidade: texto(100)
    uf: UfOpcional
    aceita_ofertas: bool = False
    observacoes: texto(500)
    limite_credito: Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)] | None = None
    convenio_id: UUID | None = Field(default=None, description="Empresa conveniada em que o cliente trabalha")
    convenio_matricula: texto(30)
    convenio_limite: Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)] | None = Field(
        default=None, description="Limite no convênio. Vazio: o limite padrão da empresa"
    )

    @field_validator("limite_credito", "convenio_limite", mode="before")
    @classmethod
    def _aceita_virgula(cls, valor):
        """A tela manda "150,00"; o padrão da API é "150.00"."""
        if isinstance(valor, str):
            valor = valor.strip().replace(".", "").replace(",", ".") if "," in valor else valor.strip()
            return valor or None
        return valor


class ClienteCriar(ClienteDados):
    nome: Nome


class ClienteAtualizar(ClienteDados):
    """Só o que vier é alterado."""

    nome: Nome | None = None
    aceita_ofertas: bool | None = None
    ativo: bool | None = None


class ClienteSaida(ClienteDados):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    consentimento_em: datetime | None
    ativo: bool
    criado_em: datetime


class ClienteLista(ClienteSaida):
    pontos: int = 0
    ultima_compra: datetime | None = None


class PaginaClientes(BaseModel):
    itens: list[ClienteLista]
    total: int


class ResumoCompras(BaseModel):
    quantidade: int
    total: Decimal
    ticket_medio: Decimal
    primeira: datetime | None
    ultima: datetime | None
    dias_sem_comprar: int | None


class ProdutoFrequente(BaseModel):
    produto_id: UUID
    descricao: str
    vezes: int = Field(description="Em quantas compras o produto apareceu")
    quantidade: Decimal
    ultima: datetime


class CompraCliente(BaseModel):
    id: UUID
    numero: int
    finalizada_em: datetime
    status: str
    total: Decimal
    itens: int
    formas: list[str]
    pontos_ganhos: int
    pontos_resgatados: int


class FichaCliente(BaseModel):
    cliente: ClienteSaida
    compras: ResumoCompras
    pontos: Pontos
    fiado_em_aberto: Decimal
    fiado_vencido: Decimal
    produtos_frequentes: list[ProdutoFrequente]
    ultimas_compras: list[CompraCliente]
