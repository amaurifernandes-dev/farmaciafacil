"""Impostos de uma NF-e de compra, lidos do XML guardado na entrada (para o SPED e o fechamento do mês)."""

from dataclasses import dataclass, field
from decimal import Decimal
from xml.etree.ElementTree import Element

from defusedxml import ElementTree

NS = {"n": "http://www.portalfiscal.inf.br/nfe"}
ZERO = Decimal(0)

# CSOSN do fornecedor do Simples não existe na escrituração de quem compra: vira o CST equivalente.
CSOSN_PARA_CST = {"500": "60", "201": "10", "202": "30", "203": "30", "900": "90"}
# Venda com substituição tributária (54xx) vira compra para revenda com ST (1403/2403).
CFOP_ST = {"401", "402", "403", "404", "405"}
CFOP_REVENDA = {"101", "102", "103", "104", "105", "106", "109", "110", "111", "113", "114", "115", "116", "117",
                "118", "119", "120", "122", "123", "124", "125"}


@dataclass
class ImpostoItem:
    numero: int
    codigo: str  # cProd: o código do fornecedor
    quantidade: Decimal
    cfop_emitente: str
    cst_icms: str  # origem + CST (3 dígitos), já convertido para quem compra
    aliquota_icms: Decimal
    valor_produto: Decimal
    desconto: Decimal
    outras: Decimal  # frete, seguro e outras despesas do item
    base_icms: Decimal
    icms: Decimal
    base_icms_st: Decimal
    icms_st: Decimal
    ipi: Decimal
    pis: Decimal
    cofins: Decimal

    @property
    def cfop_entrada(self) -> str:
        return cfop_de_entrada(self.cfop_emitente)

    @property
    def valor_operacao(self) -> Decimal:
        """O que a nota cobra pelo item: o valor com desconto, mais despesas, ST e IPI."""
        return self.valor_produto - self.desconto + self.outras + self.icms_st + self.ipi


@dataclass
class Participante:
    cnpj: str
    nome: str
    inscricao_estadual: str | None
    codigo_municipio: str | None
    endereco: str | None
    numero: str | None
    bairro: str | None


@dataclass
class ImpostosNota:
    emitente: Participante
    a_vista: bool
    valor_produtos: Decimal
    desconto: Decimal
    frete: Decimal
    seguro: Decimal
    outras: Decimal
    base_icms: Decimal
    icms: Decimal
    base_icms_st: Decimal
    icms_st: Decimal
    ipi: Decimal
    pis: Decimal
    cofins: Decimal
    total: Decimal
    itens: dict[int, ImpostoItem] = field(default_factory=dict)


def cfop_de_entrada(cfop: str) -> str:
    """5102 do fornecedor vira 1102 na entrada; 6405 vira 2403. O contador confere no PVA."""
    if len(cfop) != 4 or cfop[0] not in "567":
        return cfop
    primeiro = {"5": "1", "6": "2", "7": "3"}[cfop[0]]
    final = cfop[1:]
    if final in CFOP_ST:
        final = "403"
    elif final in CFOP_REVENDA:
        final = "102"
    return primeiro + final


def _texto(no: Element | None, caminho: str) -> str | None:
    if no is None:
        return None
    achado = no.find(caminho, NS)
    return achado.text.strip() if achado is not None and achado.text else None


def _valor(no: Element | None, caminho: str) -> Decimal:
    texto = _texto(no, caminho)
    return Decimal(texto) if texto else ZERO


def _item(det: Element) -> ImpostoItem:
    prod = det.find("n:prod", NS)
    imposto = det.find("n:imposto", NS)
    grupo_icms = imposto.find("n:ICMS", NS) if imposto is not None else None
    icms = grupo_icms[0] if grupo_icms is not None and len(grupo_icms) else None
    origem = _texto(icms, "n:orig") or "0"
    cst = _texto(icms, "n:CST")
    if cst is None:
        cst = CSOSN_PARA_CST.get(_texto(icms, "n:CSOSN") or "", "90")
    return ImpostoItem(
        numero=int(det.get("nItem") or 0),
        codigo=_texto(prod, "n:cProd") or "",
        quantidade=_valor(prod, "n:qCom"),
        cfop_emitente=_texto(prod, "n:CFOP") or "",
        cst_icms=origem + cst,
        aliquota_icms=_valor(icms, "n:pICMS"),
        valor_produto=_valor(prod, "n:vProd"),
        desconto=_valor(prod, "n:vDesc"),
        outras=_valor(prod, "n:vFrete") + _valor(prod, "n:vSeg") + _valor(prod, "n:vOutro"),
        base_icms=_valor(icms, "n:vBC"),
        icms=_valor(icms, "n:vICMS"),
        base_icms_st=_valor(icms, "n:vBCST"),
        icms_st=_valor(icms, "n:vICMSST"),
        ipi=_valor(imposto, "n:IPI/n:IPITrib/n:vIPI"),
        pis=_valor(imposto, "n:PIS/*/n:vPIS"),
        cofins=_valor(imposto, "n:COFINS/*/n:vCOFINS"),
    )


def ler_impostos(xml: str) -> ImpostosNota:
    raiz = ElementTree.fromstring(xml.strip().encode())
    inf = raiz.find(".//n:infNFe", NS)
    emit = inf.find("n:emit", NS)
    endereco = emit.find("n:enderEmit", NS)
    total = inf.find("n:total/n:ICMSTot", NS)
    # indPag (leiaute 4.0 fica no pagamento): 0 = à vista.
    indicador = _texto(inf, "n:pag/n:detPag/n:indPag") or _texto(inf, "n:ide/n:indPag")
    nota = ImpostosNota(
        emitente=Participante(
            cnpj=_texto(emit, "n:CNPJ") or "",
            nome=(_texto(emit, "n:xNome") or "")[:100],
            inscricao_estadual=_texto(emit, "n:IE"),
            codigo_municipio=_texto(endereco, "n:cMun"),
            endereco=(_texto(endereco, "n:xLgr") or "")[:60] or None,
            numero=(_texto(endereco, "n:nro") or "")[:10] or None,
            bairro=(_texto(endereco, "n:xBairro") or "")[:60] or None,
        ),
        a_vista=indicador == "0" if indicador else inf.find("n:cobr/n:dup", NS) is None,
        valor_produtos=_valor(total, "n:vProd"),
        desconto=_valor(total, "n:vDesc"),
        frete=_valor(total, "n:vFrete"),
        seguro=_valor(total, "n:vSeg"),
        outras=_valor(total, "n:vOutro"),
        base_icms=_valor(total, "n:vBC"),
        icms=_valor(total, "n:vICMS"),
        base_icms_st=_valor(total, "n:vBCST"),
        icms_st=_valor(total, "n:vST"),
        ipi=_valor(total, "n:vIPI"),
        pis=_valor(total, "n:vPIS"),
        cofins=_valor(total, "n:vCOFINS"),
        total=_valor(total, "n:vNF"),
    )
    for det in inf.findall("n:det", NS):
        item = _item(det)
        nota.itens[item.numero] = item
    return nota
