"""Leitura do XML da NF-e de compra (o arquivo que a distribuidora manda junto com a mercadoria)."""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from xml.etree.ElementTree import Element

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from app.shared.datas import FUSO
from app.shared.erros import ErroDeNegocio

NS = {"n": "http://www.portalfiscal.inf.br/nfe"}
CENTAVO = Decimal("0.01")


class XmlInvalido(ErroDeNegocio):
    pass


@dataclass
class LoteNota:
    numero: str
    quantidade: Decimal
    validade: date | None


@dataclass
class ItemNota:
    codigo: str
    ean: str | None
    ean_tributavel: str | None
    descricao: str
    ncm: str | None
    cest: str | None
    registro_ms: str | None
    unidade: str
    quantidade: Decimal
    valor_unitario: Decimal  # já com o desconto do item
    valor_total: Decimal
    fator_sugerido: int
    lotes: list[LoteNota] = field(default_factory=list)


@dataclass
class Emitente:
    cnpj: str
    razao_social: str
    nome_fantasia: str | None
    inscricao_estadual: str | None
    telefone: str | None
    cep: str | None
    endereco: str | None
    bairro: str | None
    cidade: str | None
    uf: str | None


@dataclass
class NotaLida:
    chave: str
    numero: int
    serie: int
    emitida_em: datetime
    emitente: Emitente
    cnpj_destinatario: str | None
    valor_produtos: Decimal
    valor_total: Decimal
    itens: list[ItemNota]


def _texto(no: Element | None, caminho: str) -> str | None:
    if no is None:
        return None
    achado = no.find(caminho, NS)
    if achado is None or achado.text is None:
        return None
    return achado.text.strip() or None


def _decimal(no: Element, caminho: str, padrao: str | None = None) -> Decimal:
    valor = _texto(no, caminho) or padrao
    if valor is None:
        raise XmlInvalido(f"O XML não tem o campo {caminho.replace('n:', '')}")
    try:
        return Decimal(valor)
    except InvalidOperation:
        raise XmlInvalido(f"Valor inválido no campo {caminho.replace('n:', '')}: {valor}")


def _ean(valor: str | None) -> str | None:
    """A nota usa "SEM GTIN" quando o produto não tem código de barras."""
    if valor and re.fullmatch(r"\d{8,14}", valor):
        return valor
    return None


def _data(valor: str | None) -> date | None:
    if not valor:
        return None
    try:
        return date.fromisoformat(valor[:10])
    except ValueError:
        return None


def _emissao(ide: Element) -> datetime:
    valor = _texto(ide, "n:dhEmi")
    if valor:
        try:
            momento = datetime.fromisoformat(valor)
        except ValueError:
            raise XmlInvalido(f"Data de emissão inválida: {valor}")
        return momento if momento.tzinfo else momento.replace(tzinfo=FUSO)
    dia = _data(_texto(ide, "n:dEmi"))  # leiaute antigo, só a data
    if dia is None:
        raise XmlInvalido("O XML não tem a data de emissão")
    return datetime.combine(dia, time(), tzinfo=FUSO)


def _so_digitos(valor: str | None) -> str | None:
    return re.sub(r"\D", "", valor) or None if valor else None


def _item(det: Element) -> ItemNota:
    prod = det.find("n:prod", NS)
    if prod is None:
        raise XmlInvalido("Item da nota sem os dados do produto")
    quantidade = _decimal(prod, "n:qCom")
    if quantidade <= 0:
        raise XmlInvalido(f"Quantidade inválida no item {_texto(prod, 'n:xProd')}")
    bruto = _decimal(prod, "n:vProd")
    desconto = _decimal(prod, "n:vDesc", "0")
    liquido = bruto - desconto

    # Se a nota vende em caixas e tributa em unidades (ex.: 2 CX = 20 UN), sugere o fator 10.
    fator = 1
    quantidade_tributavel = _texto(prod, "n:qTrib")
    if quantidade_tributavel and _texto(prod, "n:uTrib") != _texto(prod, "n:uCom"):
        try:
            razao = Decimal(quantidade_tributavel) / quantidade
        except InvalidOperation:
            razao = Decimal(1)
        if razao > 1 and razao == razao.to_integral_value():
            fator = int(razao)

    lotes = []
    for rastro in prod.findall("n:rastro", NS):
        numero = _texto(rastro, "n:nLote")
        if numero:
            lotes.append(LoteNota(numero[:40], _decimal(rastro, "n:qLote", str(quantidade)), _data(_texto(rastro, "n:dVal"))))

    return ItemNota(
        codigo=(_texto(prod, "n:cProd") or "")[:60],
        ean=_ean(_texto(prod, "n:cEAN")),
        ean_tributavel=_ean(_texto(prod, "n:cEANTrib")),
        descricao=(_texto(prod, "n:xProd") or "Produto sem descrição")[:200],
        ncm=_texto(prod, "n:NCM") if re.fullmatch(r"\d{8}", _texto(prod, "n:NCM") or "") else None,
        cest=_texto(prod, "n:CEST") if re.fullmatch(r"\d{7}", _texto(prod, "n:CEST") or "") else None,
        registro_ms=(_texto(prod, "n:med/n:cProdANVISA") or "")[:20] or None,
        unidade=(_texto(prod, "n:uCom") or "UN")[:6].upper(),
        quantidade=quantidade,
        valor_unitario=(liquido / quantidade).quantize(Decimal("0.0001"), ROUND_HALF_UP),
        valor_total=liquido.quantize(CENTAVO, ROUND_HALF_UP),
        fator_sugerido=fator,
        lotes=lotes,
    )


def ler_nfe(conteudo: str) -> NotaLida:
    try:
        raiz = ElementTree.fromstring(conteudo.strip().encode())
    except (ElementTree.ParseError, DefusedXmlException):
        raise XmlInvalido("O arquivo não é um XML válido. Use o XML da nota que veio do fornecedor.")

    inf = raiz.find(".//n:infNFe", NS)
    if inf is None:
        raise XmlInvalido("Este XML não é de uma NF-e. Use o XML da nota que veio do fornecedor.")

    protocolo = raiz.find(".//n:protNFe/n:infProt/n:cStat", NS)
    if protocolo is not None and protocolo.text not in ("100", "150"):
        raise XmlInvalido("Esta nota não está autorizada pela SEFAZ")

    chave = (inf.get("Id") or "").removeprefix("NFe")
    if not re.fullmatch(r"\d{44}", chave):
        raise XmlInvalido("Não foi possível ler a chave de acesso da nota")

    ide = inf.find("n:ide", NS)
    emit = inf.find("n:emit", NS)
    if ide is None or emit is None:
        raise XmlInvalido("O XML não tem os dados da nota ou do fornecedor")
    if _texto(ide, "n:mod") not in (None, "55"):
        raise XmlInvalido("Este XML não é de uma NF-e de compra (modelo 55)")

    cnpj = _texto(emit, "n:CNPJ")
    if not cnpj:
        raise XmlInvalido("A nota não tem o CNPJ do fornecedor")
    endereco = emit.find("n:enderEmit", NS)
    logradouro = ", ".join(p for p in (_texto(endereco, "n:xLgr"), _texto(endereco, "n:nro")) if p)
    emitente = Emitente(
        cnpj=cnpj,
        razao_social=(_texto(emit, "n:xNome") or cnpj)[:200],
        nome_fantasia=(_texto(emit, "n:xFant") or "")[:200] or None,
        inscricao_estadual=(_texto(emit, "n:IE") or "")[:20] or None,
        telefone=(_so_digitos(_texto(endereco, "n:fone")) or "")[:20] or None,
        cep=_so_digitos(_texto(endereco, "n:CEP")) if len(_so_digitos(_texto(endereco, "n:CEP")) or "") == 8 else None,
        endereco=logradouro[:200] or None,
        bairro=(_texto(endereco, "n:xBairro") or "")[:100] or None,
        cidade=(_texto(endereco, "n:xMun") or "")[:100] or None,
        uf=_texto(endereco, "n:UF"),
    )

    itens = [_item(det) for det in inf.findall("n:det", NS)]
    if not itens:
        raise XmlInvalido("A nota não tem itens")

    totais = inf.find("n:total/n:ICMSTot", NS)
    soma = sum((i.valor_total for i in itens), Decimal(0))
    return NotaLida(
        chave=chave,
        numero=int(_texto(ide, "n:nNF") or 0),
        serie=int(_texto(ide, "n:serie") or 0),
        emitida_em=_emissao(ide),
        emitente=emitente,
        cnpj_destinatario=_texto(inf, "n:dest/n:CNPJ"),
        valor_produtos=_decimal(totais, "n:vProd") if totais is not None else soma,
        valor_total=_decimal(totais, "n:vNF") if totais is not None else soma,
        itens=itens,
    )
