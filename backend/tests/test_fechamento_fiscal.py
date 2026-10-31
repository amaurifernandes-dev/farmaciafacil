import io
import zipfile
from decimal import Decimal

from app.modules.fiscal.nfe_impostos import cfop_de_entrada, ler_impostos
from app.shared.datas import hoje
from tests.test_compras import CNPJ_DISTRIBUIDORA, _importar, _validade
from tests.test_estoque_lojas import _matriz
from tests.test_nfce import _configurar, _produto, _vender, caixa_aberto, sefaz  # noqa: F401

API = "/api/v1"
CHAVE = "35261012345678000195550010000045671000045678"


def _xml_com_impostos() -> str:
    """Nota com um remédio com ST (CSOSN 500 do fornecedor) e um protetor tributado com 18% de ICMS."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe><infNFe Id="NFe{CHAVE}" versao="4.00">
    <ide><cUF>35</cUF><mod>55</mod><serie>1</serie><nNF>4567</nNF><dhEmi>2026-10-02T09:00:00-03:00</dhEmi></ide>
    <emit><CNPJ>{CNPJ_DISTRIBUIDORA}</CNPJ><xNome>Distribuidora Saúde LTDA</xNome>
      <enderEmit><xLgr>Rua das Flores</xLgr><nro>100</nro><xBairro>Centro</xBairro><cMun>3509502</cMun>
      <xMun>Campinas</xMun><UF>SP</UF></enderEmit><IE>123456789012</IE></emit>
    <dest><CNPJ>11111111000111</CNPJ><xNome>Farmácia</xNome></dest>
    <det nItem="1"><prod><cProd>A1</cProd><cEAN>17891234567892</cEAN><xProd>DIPIRONA</xProd><NCM>30049099</NCM>
      <CFOP>5405</CFOP><uCom>CX</uCom><qCom>2</qCom><vUnCom>25.00</vUnCom><vProd>50.00</vProd>
      <cEANTrib>7891234567895</cEANTrib><uTrib>UN</uTrib><qTrib>20</qTrib>
      <rastro><nLote>C1</nLote><qLote>1</qLote><dFab>2026-01-01</dFab><dVal>{_validade(200)}</dVal></rastro>
      <rastro><nLote>C2</nLote><qLote>1</qLote><dFab>2026-01-01</dFab><dVal>{_validade(300)}</dVal></rastro></prod>
      <imposto><ICMS><ICMSSN500><orig>0</orig><CSOSN>500</CSOSN></ICMSSN500></ICMS>
      <PIS><PISNT><CST>04</CST></PISNT></PIS></imposto></det>
    <det nItem="2"><prod><cProd>P9</cProd><cEAN>7890000000017</cEAN><xProd>PROTETOR SOLAR</xProd><NCM>33049910</NCM>
      <CFOP>5102</CFOP><uCom>UN</uCom><qCom>5</qCom><vUnCom>10.00</vUnCom><vProd>50.00</vProd>
      <cEANTrib>7890000000017</cEANTrib><uTrib>UN</uTrib><qTrib>5</qTrib>
      <rastro><nLote>P1</nLote><qLote>5</qLote><dFab>2026-01-01</dFab><dVal>{_validade(400)}</dVal></rastro></prod>
      <imposto><ICMS><ICMS00><orig>0</orig><CST>00</CST><modBC>3</modBC><vBC>50.00</vBC><pICMS>18.00</pICMS>
      <vICMS>9.00</vICMS></ICMS00></ICMS>
      <IPI><cEnq>999</cEnq><IPITrib><CST>50</CST><vBC>50.00</vBC><pIPI>5.00</pIPI><vIPI>2.50</vIPI></IPITrib></IPI>
      </imposto></det>
    <total><ICMSTot><vBC>50.00</vBC><vICMS>9.00</vICMS><vBCST>0</vBCST><vST>0</vST><vProd>100.00</vProd>
      <vFrete>0</vFrete><vSeg>0</vSeg><vDesc>0</vDesc><vIPI>2.50</vIPI><vPIS>0</vPIS><vCOFINS>0</vCOFINS>
      <vOutro>0</vOutro><vNF>102.50</vNF></ICMSTot></total>
    <pag><detPag><indPag>1</indPag><tPag>15</tPag><vPag>102.50</vPag></detPag></pag>
  </infNFe></NFe>
  <protNFe versao="4.00"><infProt><chNFe>{CHAVE}</chNFe><cStat>100</cStat></infProt></protNFe>
</nfeProc>"""


def _mes() -> str:
    return hoje().strftime("%Y-%m")


def _preparar(client, farmacia):
    """Duas vendas com NFC-e (uma com ST e monofásico, outra normal) e a compra confirmada no mês."""
    _configurar(client, farmacia)
    dipirona = _produto(client, farmacia, cfop="5405", icms_situacao_tributaria="500",
                        pis_cofins_situacao_tributaria="04")
    protetor = _produto(client, farmacia, nome="Protetor solar", preco="30.00", ean="7890000000017")
    _vender(client, farmacia, [{"produto_id": dipirona["id"], "quantidade": "2"}],
            [{"forma": "dinheiro", "valor": "20.00"}])
    _vender(client, farmacia, [{"produto_id": protetor["id"], "quantidade": "1"}],
            [{"forma": "pix", "valor": "30.00"}])

    nota = _importar(client, farmacia, _xml_com_impostos())
    assert nota.status_code == 201, nota.text
    nota = nota.json()
    # O display de dipirona tem 10 caixinhas (o EAN da caixinha vem no campo tributável).
    assert [i["fator"] for i in nota["itens"]] == [10, 10, 1]
    confirmar = client.post(f"{API}/compras/notas/{nota['id']}/confirmar", headers=farmacia["headers"])
    assert confirmar.status_code == 200, confirmar.text
    return dipirona, protetor


def test_leitura_dos_impostos_da_nota():
    nota = ler_impostos(_xml_com_impostos())
    assert nota.emitente.codigo_municipio == "3509502"
    assert not nota.a_vista
    assert (nota.icms, nota.ipi, nota.total) == (Decimal("9.00"), Decimal("2.50"), Decimal("102.50"))
    remedio, protetor = nota.itens[1], nota.itens[2]
    assert (remedio.cst_icms, remedio.cfop_entrada) == ("060", "1403")  # CSOSN 500 vira CST 60
    assert (protetor.cst_icms, protetor.cfop_entrada, protetor.aliquota_icms) == ("000", "1102", Decimal("18.00"))
    assert protetor.valor_operacao == Decimal("52.50")  # com o IPI
    assert cfop_de_entrada("6405") == "2403"


def test_fechamento_do_simples(client, farmacia_a, sefaz, caixa_aberto):
    _preparar(client, farmacia_a)
    resposta = client.get(f"{API}/fiscal/fechamento", params={"mes": _mes()}, headers=farmacia_a["headers"])
    assert resposta.status_code == 200, resposta.text
    resumo = resposta.json()

    assert resumo["regime"] == "simples" and not resumo["sped_disponivel"]
    assert resumo["saidas"]["vendas"] == 2
    assert resumo["saidas"]["nfce_autorizadas"] == 2
    assert Decimal(resumo["saidas"]["valor_nfce"]) == Decimal("50.00")
    # A dipirona já teve ICMS-ST e PIS/COFINS monofásico: paga menos no PGDAS.
    pgdas = {k: Decimal(v) for k, v in resumo["pgdas"].items()}
    assert pgdas == {"normal": Decimal("30.00"), "icms_st": 0, "monofasico": 0,
                     "st_e_monofasico": Decimal("20.00"), "total": Decimal("50.00")}

    entradas = resumo["entradas"]
    assert entradas["notas"] == 1
    assert Decimal(entradas["icms"]) == Decimal("9.00")
    assert [(l["cfop"], l["cst"]) for l in entradas["por_cfop"]] == [("1102", "000"), ("1403", "060")]
    assert resumo["pendencias"] == []

    # O SPED não existe para o Simples, mas o pacote para o contador sim.
    sped = client.get(f"{API}/fiscal/sped", params={"mes": _mes()}, headers=farmacia_a["headers"])
    assert sped.status_code == 400
    pacote = client.get(f"{API}/fiscal/pacote", params={"mes": _mes()}, headers=farmacia_a["headers"])
    assert pacote.status_code == 200
    arquivos = zipfile.ZipFile(io.BytesIO(pacote.content)).namelist()
    assert sorted(arquivos) == ["nfce-do-mes.csv", "receita-pgdas.csv", "resumo-por-cfop.csv",
                                f"xml-compras/{CHAVE}.xml"]


def test_sped_do_regime_normal(client, farmacia_a, sefaz, caixa_aberto):
    dipirona, protetor = _preparar(client, farmacia_a)
    _configurar(client, farmacia_a, regime="presumido", icms_situacao_tributaria_padrao="00",
                contador_nome="Maria Contadora", contador_cpf="529.982.247-25", contador_crc="SP123456")

    # Sem IE e código do município da loja, o fechamento avisa. A dipirona ainda tem o CSOSN 500 do Simples.
    resumo = client.get(f"{API}/fiscal/fechamento", params={"mes": _mes()}, headers=farmacia_a["headers"]).json()
    assert {p["tipo"] for p in resumo["pendencias"]} == {"loja_incompleta", "icms_sem_aliquota",
                                                         "csosn_no_regime_normal"}
    assert [(l["cfop"], l["cst"]) for l in resumo["saidas"]["por_cfop"]] == [("5102", "000"), ("5405", "060")]

    matriz = _matriz(client, farmacia_a)
    resposta = client.patch(f"{API}/lojas/{matriz['id']}", json={"inscricao_estadual": "111222333444",
                                                                  "codigo_municipio": "3550308"},
                            headers=farmacia_a["headers"])
    assert resposta.status_code == 200, resposta.text

    sped = client.get(f"{API}/fiscal/sped", params={"mes": _mes()}, headers=farmacia_a["headers"])
    assert sped.status_code == 200, sped.text
    assert "SPED-EFD-11111111000111" in sped.headers["content-disposition"]
    texto = sped.content.decode("latin-1")
    assert texto.endswith("\r\n")
    linhas = [l.split("|")[1:-1] for l in texto.strip().split("\r\n")]
    registros = [l[0] for l in linhas]

    abertura = linhas[0]
    assert abertura[:3] == ["0000", "020" if hoje().year == 2026 else abertura[1], "0"]
    assert abertura[6] == "11111111000111" and abertura[10] == "3550308"
    contador = next(l for l in linhas if l[0] == "0100")
    assert contador[1:4] == ["Maria Contadora", "52998224725", "SP123456"]
    assert next(l for l in linhas if l[0] == "0150")[1] == f"F{CNPJ_DISTRIBUIDORA}"

    # A compra: um C170 por item do XML (os dois lotes da dipirona viram um só, em unidades).
    compra = next(l for l in linhas if l[0] == "C100" and l[1] == "0")
    assert compra[8] == CHAVE and compra[12] == "1"  # a prazo
    c170 = [l for l in linhas if l[0] == "C170"]
    assert [(l[2], l[4], l[5], l[9], l[10]) for l in c170] == [
        (dipirona["id"].replace("-", ""), "20,00000", "UN", "060", "1403"),
        (protetor["id"].replace("-", ""), "5,00000", "UN", "000", "1102"),
    ]
    # As duas NFC-e entram como modelo 65, sem participante.
    nfce = [l for l in linhas if l[0] == "C100" and l[1] == "1"]
    assert [(l[4], l[5], l[11]) for l in nfce] == [("65", "00", "20,00"), ("65", "00", "30,00")]
    # A apuração usa o ICMS da compra como crédito.
    e110 = next(l for l in linhas if l[0] == "E110")
    assert (e110[5], e110[13]) == ("9,00", "9,00")  # créditos e saldo credor para o mês seguinte

    # Os totais do bloco 9 batem com o arquivo.
    contagem = {l[1]: int(l[2]) for l in linhas if l[0] == "9900"}
    for registro in set(registros):
        assert contagem[registro] == registros.count(registro), registro
    assert linhas[-1] == ["9999", str(len(linhas))]
    assert next(l for l in linhas if l[0] == "C990")[1] == str(registros.count("C100") + registros.count("C170")
                                                                + registros.count("C190") + 2)

    pacote = client.get(f"{API}/fiscal/pacote", params={"mes": _mes()}, headers=farmacia_a["headers"])
    nomes = zipfile.ZipFile(io.BytesIO(pacote.content)).namelist()
    assert any(n.startswith("SPED-EFD-") for n in nomes)
    assert "pendencias.txt" in nomes  # o ICMS das vendas com CST 00 vai zerado


def test_mes_invalido_e_permissao(client, farmacia_a):
    assert client.get(f"{API}/fiscal/fechamento", params={"mes": "2026-13"},
                      headers=farmacia_a["headers"]).status_code == 400
