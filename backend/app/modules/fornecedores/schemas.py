from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.shared.campos import Cep, CnpjOpcional, Email, Telefone, UfOpcional, texto

RazaoSocial = Annotated[str, Field(min_length=1, max_length=200)]


class FornecedorDados(BaseModel):
    nome_fantasia: texto(200)
    cnpj: CnpjOpcional
    inscricao_estadual: texto(20)
    contato: texto(120)
    telefone: Telefone
    email: Email
    cep: Cep
    endereco: texto(200)
    bairro: texto(100)
    cidade: texto(100)
    uf: UfOpcional
    observacoes: texto(500)


class FornecedorCriar(FornecedorDados):
    razao_social: RazaoSocial


class FornecedorAtualizar(FornecedorDados):
    """Só o que vier é alterado."""

    razao_social: RazaoSocial | None = None
    ativo: bool | None = None


class FornecedorSaida(FornecedorDados):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    razao_social: str
    ativo: bool
    criado_em: datetime


class PaginaFornecedores(BaseModel):
    itens: list[FornecedorSaida]
    total: int
