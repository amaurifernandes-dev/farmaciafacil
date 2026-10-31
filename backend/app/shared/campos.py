"""Tipos de campo reutilizados nos cadastros. Documentos aceitam pontuação e são salvos só com dígitos."""

from typing import Annotated

from pydantic import AfterValidator, BeforeValidator, Field

from app.shared.cnpj import cnpj_valido
from app.shared.cpf import cpf_valido


def _digitos(valor: object) -> object:
    if isinstance(valor, str):
        return "".join(c for c in valor if c.isdigit()) or None
    return valor


def _vazio_vira_nulo(valor: object) -> object:
    if isinstance(valor, str):
        return valor.strip() or None
    return valor


def _cpf(valor: str) -> str:
    if not cpf_valido(valor):
        raise ValueError("CPF inválido")
    return valor


def _cnpj(valor: str) -> str:
    if not cnpj_valido(valor):
        raise ValueError("CNPJ inválido")
    return valor


def _opcional(tipo, *antes):
    """Campo opcional: string vazia (ou só pontuação, nos documentos) vira nulo."""
    return Annotated[tipo | None, BeforeValidator(_vazio_vira_nulo), *(BeforeValidator(f) for f in antes), Field(default=None)]


def _maiusculas(valor: object) -> object:
    return valor.upper() if isinstance(valor, str) else valor


Cpf = _opcional(Annotated[str, AfterValidator(_cpf)], _digitos)
CpfObrigatorio = Annotated[str, BeforeValidator(_digitos), AfterValidator(_cpf)]
Cnpj = Annotated[str, BeforeValidator(_digitos), AfterValidator(_cnpj)]
CnpjOpcional = _opcional(Annotated[str, AfterValidator(_cnpj)], _digitos)
Cep = _opcional(Annotated[str, Field(pattern=r"^\d{8}$")], _digitos)
Telefone = _opcional(Annotated[str, Field(pattern=r"^\d{10,11}$")], _digitos)
Uf = Annotated[str, BeforeValidator(lambda v: _maiusculas(_vazio_vira_nulo(v))), Field(pattern=r"^[A-Z]{2}$")]
UfOpcional = _opcional(Annotated[str, Field(pattern=r"^[A-Z]{2}$")], _maiusculas)
Email = _opcional(Annotated[str, Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")])


def texto(maximo: int):
    """Texto opcional: string vazia vira nulo."""
    return _opcional(Annotated[str, Field(max_length=maximo)])
