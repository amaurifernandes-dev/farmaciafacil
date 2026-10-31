"""Pix "copia e cola" (BR Code estático com valor), feito com a chave da própria farmácia.

Segue o Manual de Padrões para Iniciação do Pix do Banco Central: campos EMV (id + tamanho + valor)
e CRC16-CCITT no fim. Não passa por banco intermediário: o dinheiro cai direto na conta da chave,
e a farmácia confere no extrato pelo identificador (txid) do pedido.
"""

import re
import unicodedata
from decimal import Decimal

from app.shared.erros import ErroDeNegocio


def _campo(identificador: str, valor: str) -> str:
    return f"{identificador}{len(valor):02d}{valor}"


def _crc16(dados: str) -> str:
    crc = 0xFFFF
    for byte in dados.encode():
        crc ^= byte << 8
        for _ in range(8):
            crc = (crc << 1) ^ 0x1021 if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return f"{crc:04X}"


def _ascii(texto: str, tamanho: int) -> str:
    """Nome e cidade vão sem acento e em maiúsculas (o leitor do banco nem sempre aceita UTF-8)."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9 .-]", "", sem_acento).strip().upper()[:tamanho]


def normalizar_chave(chave: str) -> str:
    """Aceita CPF, CNPJ, e-mail, celular ou chave aleatória, do jeito que a pessoa digitar."""
    chave = chave.strip()
    if "@" in chave:
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", chave) or len(chave) > 77:
            raise ErroDeNegocio("Chave Pix: e-mail inválido")
        return chave.lower()
    if re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", chave):
        return chave.lower()
    digitos = re.sub(r"\D", "", chave)
    if chave.startswith("+") or (len(digitos) in (12, 13) and digitos.startswith("55")):
        if len(digitos) not in (12, 13):
            raise ErroDeNegocio("Chave Pix: celular inválido. Use +55, DDD e número")
        return f"+{digitos}"
    if len(digitos) in (11, 14):  # CPF ou CNPJ (celular sem +55 é ambíguo com CPF: vale o CPF)
        return digitos
    raise ErroDeNegocio("Chave Pix inválida. Use CPF, CNPJ, e-mail, celular com +55 ou a chave aleatória")


def copia_e_cola(chave: str, nome: str, cidade: str, valor: Decimal, txid: str) -> str:
    conta = _campo("00", "br.gov.bcb.pix") + _campo("01", chave)
    payload = (
        _campo("00", "01")
        + _campo("26", conta)
        + _campo("52", "0000")
        + _campo("53", "986")  # real
        + _campo("54", f"{valor:.2f}")
        + _campo("58", "BR")
        + _campo("59", _ascii(nome, 25) or "FARMACIA")
        + _campo("60", _ascii(cidade, 15) or "BRASIL")
        + _campo("62", _campo("05", re.sub(r"[^A-Za-z0-9]", "", txid)[:25] or "***"))
        + "6304"
    )
    return payload + _crc16(payload)
