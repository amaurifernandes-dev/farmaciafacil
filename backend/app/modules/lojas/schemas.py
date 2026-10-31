from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.shared.campos import Cep, Cnpj, Email, Telefone, Uf, texto

ModoCaixa = Literal["mono", "multi"]
Nome = Annotated[str, Field(min_length=1, max_length=60)]
# Código IBGE da cidade (7 dígitos), usado no SPED.
CodigoMunicipio = Annotated[str, Field(pattern=r"^\d{7}$")] | None


class LojaDados(BaseModel):
    nome: Nome
    razao_social: Annotated[str, Field(min_length=1, max_length=200)]
    nome_fantasia: Annotated[str, Field(min_length=1, max_length=200)]
    cnpj: Cnpj
    inscricao_estadual: texto(20)
    telefone: Telefone
    email: Email
    cep: Cep
    endereco: texto(200)
    bairro: texto(100)
    cidade: texto(100)
    codigo_municipio: CodigoMunicipio = None
    uf: Uf
    responsavel_tecnico: texto(120)
    crf: texto(20)


class LojaCriar(LojaDados):
    modo_caixa: ModoCaixa = "mono"


class LojaAtualizar(BaseModel):
    """Só o que vier é alterado."""

    nome: Nome | None = None
    razao_social: str | None = Field(default=None, min_length=1, max_length=200)
    nome_fantasia: str | None = Field(default=None, min_length=1, max_length=200)
    cnpj: Cnpj | None = None
    inscricao_estadual: texto(20)
    telefone: Telefone
    email: Email
    cep: Cep
    endereco: texto(200)
    bairro: texto(100)
    cidade: texto(100)
    codigo_municipio: CodigoMunicipio = None
    uf: Uf | None = None
    responsavel_tecnico: texto(120)
    crf: texto(20)
    modo_caixa: ModoCaixa | None = None
    terminal_central_id: UUID | None = None
    ativo: bool | None = None


class LojaSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    matriz: bool
    razao_social: str
    nome_fantasia: str
    cnpj: str
    inscricao_estadual: str | None
    telefone: str | None
    email: str | None
    cep: str | None
    endereco: str | None
    bairro: str | None
    cidade: str | None
    codigo_municipio: str | None
    uf: str
    responsavel_tecnico: str | None
    crf: str | None
    modo_caixa: ModoCaixa
    terminal_central_id: UUID | None
    ativo: bool


# --- Terminais ---

class TerminalCriar(BaseModel):
    loja_id: UUID
    nome: Annotated[str, Field(min_length=1, max_length=40)]


class TerminalAtualizar(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=40)
    ativo: bool | None = None


class TerminalSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    loja_id: UUID
    nome: str
    ativo: bool
    vinculado: bool
    vinculado_em: datetime | None
    ultimo_uso_em: datetime | None
    pode_receber: bool
    central: bool
    caixa_aberto_id: UUID | None


class TerminalVinculado(BaseModel):
    """Resposta do registro de um computador. A chave só aparece aqui, uma vez."""

    terminal: TerminalSaida
    chave: str


class EsteTerminal(BaseModel):
    """O que o PDV precisa saber sobre o computador em que está aberto."""

    terminal: TerminalSaida
    loja: LojaSaida
    pode_receber: bool
    motivo: str | None  # por que não pode receber, em linguagem do usuário
