from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.licenca.formato import Plano, Tipo
from app.licenca.situacao import Situacao
from app.shared.cnpj import cnpj_valido
from app.shared.modulos import Modulo

Tolerancia = Annotated[int, Field(ge=0, le=365)]
Limite = Annotated[int, Field(ge=1, le=10000)]


class Entrar(BaseModel):
    email: str
    senha: str


class Token(BaseModel):
    access_token: str
    nome: str


class LicencaCriar(BaseModel):
    cnpj: str
    nome: Annotated[str, Field(min_length=2, max_length=200)]
    contato: Annotated[str, Field(max_length=200)] | None = None
    tipo: Tipo
    plano: Plano
    inicio: date | None = Field(None, description="Vazio: hoje")
    tolerancia_dias: Tolerancia = 7
    max_usuarios: Limite | None = None
    max_caixas: Limite | None = None
    modulos: list[Modulo] | None = Field(None, description="Vazio: todos")
    observacao: str | None = None

    @field_validator("cnpj")
    @classmethod
    def _cnpj(cls, valor: str) -> str:
        numeros = "".join(c for c in valor if c.isdigit())
        if not cnpj_valido(numeros):
            raise ValueError("CNPJ inválido")
        return numeros


class LicencaAtualizar(BaseModel):
    nome: Annotated[str, Field(min_length=2, max_length=200)] | None = None
    contato: Annotated[str, Field(max_length=200)] | None = None
    plano: Plano | None = None
    vence: date | None = None
    tolerancia_dias: Tolerancia | None = None
    max_usuarios: Limite | None = None
    max_caixas: Limite | None = None
    modulos: list[Modulo] | None = None
    observacao: str | None = None


class LicencaSaida(BaseModel):
    id: int
    cnpj: str
    nome: str
    contato: str | None
    tipo: Tipo
    plano: Plano
    inicio: date
    vence: date | None
    tolerancia_dias: int
    max_usuarios: int | None
    max_caixas: int | None
    modulos: list[str] | None
    chave_ativacao: str
    maquina: str | None
    suspensa: bool
    observacao: str | None
    ultima_consulta_em: datetime | None
    situacao: Situacao


class PedirCodigo(BaseModel):
    maquina: str | None = Field(None, description="Código do servidor da farmácia (aparece na tela da licença dele)")


class CodigoSaida(BaseModel):
    codigo: str
    vence: date | None


class Ativar(BaseModel):
    """Pedido do servidor da farmácia (ou da nuvem) para buscar a licença atual."""

    chave_ativacao: str
    maquina: str | None = None


class Evento(BaseModel):
    quando: datetime
    quem: str
    o_que: str
