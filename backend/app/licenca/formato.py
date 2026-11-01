"""Código da licença: os dados do contrato com uma assinatura digital (Ed25519).

Só a central de licenças tem a chave privada e consegue gerar um código. O sistema das farmácias tem
apenas a chave pública: confere a assinatura sem internet e recusa qualquer código inventado ou alterado.

Formato: ``FF1-`` + base32 dos dados compactados + ``-`` + base32 da assinatura, em grupos de 5 letras.
"""

import base64
import json
import zlib
from datetime import date, datetime
from typing import Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from pydantic import BaseModel, Field

PREFIXO = "FF1"

Plano = Literal["mensal", "anual", "vitalicio"]
Tipo = Literal["nuvem", "farmacia"]

DIAS_DO_PLANO: dict[str, int | None] = {"mensal": 31, "anual": 365, "vitalicio": None}


class LicencaInvalida(ValueError):
    pass


class Licenca(BaseModel):
    """O que vai dentro do código. Mudar um campo invalida a assinatura."""

    id: str = Field(description="Número da licença na central")
    cnpj: str
    nome: str
    tipo: Tipo
    plano: Plano
    inicio: date
    vence: date | None = Field(description="Último dia normal. Vazio: vitalícia")
    tolerancia_dias: int = 7
    max_usuarios: int | None = None
    max_caixas: int | None = None
    # Vazio: todos os módulos. Senão, só estes podem ser ligados.
    modulos: list[str] | None = None
    # Código do servidor onde vale (instalação na farmácia). Vazio: qualquer um (nuvem).
    maquina: str | None = None
    emitida_em: datetime


def _b32(dados: bytes) -> str:
    return base64.b32encode(dados).decode().rstrip("=")


def _de_b32(texto: str) -> bytes:
    return base64.b32decode(texto + "=" * (-len(texto) % 8))


def _agrupar(texto: str) -> str:
    return "".join(texto[i : i + 5] + (" " if (i // 5) % 6 == 5 else "") for i in range(0, len(texto), 5)).strip()


def chave_privada(texto: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(texto))


def chave_publica(texto: str) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(base64.b64decode(texto))


def gerar_par() -> tuple[str, str]:
    """(privada, pública) em base64, para configurar a central e as instalações."""
    privada = Ed25519PrivateKey.generate()
    bruta = privada.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    publica = privada.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return base64.b64encode(bruta).decode(), base64.b64encode(publica).decode()


def assinar(licenca: Licenca, privada: Ed25519PrivateKey) -> str:
    dados = zlib.compress(json.dumps(licenca.model_dump(mode="json"), separators=(",", ":")).encode(), 9)
    assinatura = privada.sign(dados)
    return f"{PREFIXO}-{_agrupar(_b32(dados))}-{_agrupar(_b32(assinatura))}"


def limpar(codigo: str) -> str:
    """Aceita o código colado com espaços, quebras de linha ou letras minúsculas."""
    return "".join(codigo.split()).upper()


def ler(codigo: str, publica: Ed25519PublicKey) -> Licenca:
    partes = limpar(codigo).split("-")
    if len(partes) != 3 or partes[0] != PREFIXO:
        raise LicencaInvalida("Este não é um código de licença do FarmáciaFácil")
    try:
        dados, assinatura = _de_b32(partes[1]), _de_b32(partes[2])
    except ValueError:
        raise LicencaInvalida("O código da licença está incompleto. Copie de novo, inteiro")
    try:
        publica.verify(assinatura, dados)
    except InvalidSignature:
        raise LicencaInvalida("O código da licença não confere. Copie de novo, inteiro, ou peça um novo")
    return Licenca.model_validate(json.loads(zlib.decompress(dados)))
