from decimal import Decimal
from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

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

    @field_validator("limite_credito", mode="before")
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


class PaginaClientes(BaseModel):
    itens: list[ClienteSaida]
    total: int
