"""Leitura de boletos pela linha digitável ou pelo código de barras (padrão FEBRABAN).

- Boleto bancário: código de barras com 44 números ou linha digitável com 47.
- Conta de consumo e tributo (arrecadação, começa com 8): 44 números ou linha com 48.

Confere os dígitos verificadores e tira o banco, o valor e o vencimento (quando o boleto informa).
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.shared.datas import hoje

BANCOS = {
    "001": "Banco do Brasil",
    "004": "Banco do Nordeste",
    "021": "Banestes",
    "033": "Santander",
    "041": "Banrisul",
    "070": "BRB",
    "077": "Inter",
    "085": "Ailos",
    "104": "Caixa",
    "136": "Unicred",
    "208": "BTG Pactual",
    "212": "Original",
    "237": "Bradesco",
    "260": "Nubank",
    "290": "PagBank",
    "323": "Mercado Pago",
    "336": "C6 Bank",
    "341": "Itaú",
    "380": "PicPay",
    "389": "Mercantil",
    "422": "Safra",
    "655": "Votorantim",
    "748": "Sicredi",
    "756": "Sicoob",
}

SEGMENTOS = {
    "1": "Prefeitura",
    "2": "Água e esgoto",
    "3": "Energia elétrica e gás",
    "4": "Telefone e internet",
    "5": "Órgão do governo",
    "6": "Carnê",
    "7": "Multa de trânsito",
    "9": "Uso do banco",
}

# O fator de vencimento conta dias desde 07/10/1997; em 22/02/2025 chegou a 9999 e recomeçou em 1000.
BASE_ANTIGA = date(1997, 10, 7)
BASE_NOVA = date(2025, 2, 22)


class BoletoInvalido(ValueError):
    pass


@dataclass
class Boleto:
    tipo: str  # "bancario" ou "arrecadacao"
    codigo_barras: str  # sempre os 44 números
    linha_digitavel: str  # formatada, como vem impressa
    valor: Decimal | None
    vencimento: date | None
    banco: str | None = None
    banco_nome: str | None = None
    segmento: str | None = None


def _mod10(numeros: str) -> int:
    soma = 0
    for i, n in enumerate(reversed(numeros)):
        produto = int(n) * (2 if i % 2 == 0 else 1)
        soma += produto // 10 + produto % 10
    return (10 - soma % 10) % 10


def _mod11_bancario(numeros: str) -> int:
    soma = sum(int(n) * (2 + i % 8) for i, n in enumerate(reversed(numeros)))
    dv = 11 - soma % 11
    return 1 if dv in (0, 10, 11) else dv


def _mod11_arrecadacao(numeros: str) -> int:
    resto = sum(int(n) * (2 + i % 8) for i, n in enumerate(reversed(numeros))) % 11
    return 0 if resto in (0, 1) else 11 - resto


def _reais(centavos: str) -> Decimal:
    return (Decimal(int(centavos)) / 100).quantize(Decimal("0.01"))


def _vencimento(fator: int) -> date | None:
    if fator == 0:
        return None
    candidatas = [BASE_ANTIGA + timedelta(days=fator)]
    if fator >= 1000:
        candidatas.append(BASE_NOVA + timedelta(days=fator - 1000))
    # A data certa é a mais perto de hoje (o mesmo fator volta a cada ~25 anos).
    return min(candidatas, key=lambda d: abs((d - hoje()).days))


def _bancario(barras: str) -> Boleto:
    if _mod11_bancario(barras[:4] + barras[5:]) != int(barras[4]):
        raise BoletoInvalido("O código não confere (dígito verificador geral). Confira os números")
    valor = _reais(barras[9:19])
    campos = [barras[0:4] + barras[19:24], barras[24:34], barras[34:44]]
    campos = [c + str(_mod10(c)) for c in campos]
    linha = (
        f"{campos[0][:5]}.{campos[0][5:]} {campos[1][:5]}.{campos[1][5:]} "
        f"{campos[2][:5]}.{campos[2][5:]} {barras[4]} {barras[5:19]}"
    )
    banco = barras[:3]
    return Boleto(
        tipo="bancario",
        codigo_barras=barras,
        linha_digitavel=linha,
        valor=valor or None,
        vencimento=_vencimento(int(barras[5:9])),
        banco=banco,
        banco_nome=BANCOS.get(banco),
    )


def _dv_arrecadacao(identificador: str):
    if identificador in "67":
        return _mod10
    if identificador in "89":
        return _mod11_arrecadacao
    raise BoletoInvalido("Código de conta de consumo com identificador de valor desconhecido")


def _arrecadacao(barras: str) -> Boleto:
    dv = _dv_arrecadacao(barras[2])
    if dv(barras[:3] + barras[4:]) != int(barras[3]):
        raise BoletoInvalido("O código não confere (dígito verificador geral). Confira os números")
    blocos = [barras[i : i + 11] for i in range(0, 44, 11)]
    linha = " ".join(f"{b}-{dv(b)}" for b in blocos)
    # Identificador 6 ou 8: o valor está no código. 7 ou 9: é uma referência, sem valor.
    valor = _reais(barras[4:15]) if barras[2] in "68" else None
    return Boleto(
        tipo="arrecadacao",
        codigo_barras=barras,
        linha_digitavel=linha,
        valor=valor or None,
        vencimento=None,
        segmento=SEGMENTOS.get(barras[1]),
    )


def _barras_da_linha_bancaria(linha: str) -> str:
    campos = [linha[0:10], linha[10:21], linha[21:32]]
    for numero, campo in enumerate(campos, start=1):
        if _mod10(campo[:-1]) != int(campo[-1]):
            raise BoletoInvalido(f"O {numero}º bloco da linha digitável não confere. Confira os números")
    return linha[0:4] + linha[32] + linha[33:47] + linha[4:9] + linha[10:20] + linha[21:31]


def _barras_da_linha_arrecadacao(linha: str) -> str:
    dv = _dv_arrecadacao(linha[2])
    blocos = [linha[i : i + 12] for i in range(0, 48, 12)]
    for numero, bloco in enumerate(blocos, start=1):
        if dv(bloco[:11]) != int(bloco[11]):
            raise BoletoInvalido(f"O {numero}º bloco da linha digitável não confere. Confira os números")
    return "".join(b[:11] for b in blocos)


def so_numeros(codigo: str) -> str:
    return "".join(c for c in codigo if c.isdigit())


def ler(codigo: str) -> Boleto:
    """Aceita a linha digitável (com ou sem pontos e espaços) ou o código de barras lido pelo leitor."""
    numeros = so_numeros(codigo)
    if len(numeros) == 47:
        return _bancario(_barras_da_linha_bancaria(numeros))
    if len(numeros) == 48:
        if numeros[0] != "8":
            raise BoletoInvalido("Linha com 48 números deve ser de conta de consumo ou tributo (começa com 8)")
        return _arrecadacao(_barras_da_linha_arrecadacao(numeros))
    if len(numeros) == 44:
        return _arrecadacao(numeros) if numeros[0] == "8" else _bancario(numeros)
    raise BoletoInvalido(
        f"O código tem {len(numeros)} números. A linha digitável tem 47 (boleto) ou 48 (conta de consumo); "
        "o código de barras tem 44"
    )
