import uuid
from datetime import timedelta
from decimal import Decimal

from app.modules.compras.nfe_xml import ler_nfe
from app.shared.datas import hoje
from tests.test_estoque_lojas import _filial, _lotes, _matriz, _produto
from tests.test_vendas import _abrir_caixa

API = "/api/v1"
CHAVE = "35261012345678000195550010000012341000012345"
CNPJ_DISTRIBUIDORA = "12345678000195"


def _det(n, codigo, ean, descricao, quantidade, unitario, lotes=(), unidade="CX", qtrib=None, utrib=None, desconto=None, ean_trib=None):
    rastros = "".join(
        f"<rastro><nLote>{lote}</nLote><qLote>{qtd}</qLote><dFab>2026-01-01</dFab><dVal>{validade}</dVal></rastro>"
        for lote, qtd, validade in lotes
    )
    total = Decimal(quantidade) * Decimal(unitario)
    return f"""
    <det nItem="{n}"><prod>
      <cProd>{codigo}</cProd><cEAN>{ean}</cEAN><xProd>{descricao}</xProd><NCM>30049099</NCM><CEST>1300100</CEST>
      <CFOP>5405</CFOP><uCom>{unidade}</uCom><qCom>{quantidade}</qCom><vUnCom>{unitario}</vUnCom><vProd>{total:.2f}</vProd>
      <cEANTrib>{ean_trib or ean}</cEANTrib><uTrib>{utrib or unidade}</uTrib><qTrib>{qtrib or quantidade}</qTrib>
      {f"<vDesc>{desconto}</vDesc>" if desconto else ""}
      {rastros}<med><cProdANVISA>1234567890123</cProdANVISA><vPMC>20.00</vPMC></med>
    </prod></det>"""


def _xml(itens: str, destinatario="11111111000111", chave=CHAVE, cstat="100") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe><infNFe Id="NFe{chave}" versao="4.00">
    <ide><cUF>35</cUF><mod>55</mod><serie>1</serie><nNF>1234</nNF><dhEmi>2026-10-28T10:15:00-03:00</dhEmi><tpNF>1</tpNF></ide>
    <emit><CNPJ>{CNPJ_DISTRIBUIDORA}</CNPJ><xNome>Distribuidora Saúde LTDA</xNome><xFant>DistriSaúde</xFant>
      <enderEmit><xLgr>Rua das Flores</xLgr><nro>100</nro><xBairro>Centro</xBairro><xMun>Campinas</xMun><UF>SP</UF>
      <CEP>13010000</CEP><fone>1932223333</fone></enderEmit><IE>123456789012</IE></emit>
    <dest><CNPJ>{destinatario}</CNPJ><xNome>Farmácia</xNome></dest>
    {itens}
    <total><ICMSTot><vProd>100.00</vProd><vNF>100.00</vNF></ICMSTot></total>
  </infNFe></NFe>
  <protNFe versao="4.00"><infProt><chNFe>{chave}</chNFe><cStat>{cstat}</cStat></infProt></protNFe>
</nfeProc>"""


def _validade(dias=300) -> str:
    return (hoje() + timedelta(days=dias)).isoformat()


def _importar(client, farmacia, xml, **extra):
    return client.post(f"{API}/compras/notas", json={"xml": xml, **extra}, headers=farmacia["headers"])


def test_leitura_do_xml():
    nota = ler_nfe(_xml(
        _det(1, "A1", "7891234567895", "DIPIRONA 500MG C/10", "2", "25.00",
             lotes=[("ab12", 1, "2027-05-31"), ("CD34", 1, "2027-08-31")], qtrib="20", utrib="UN", desconto="5.00")
        + _det(2, "B2", "SEM GTIN", "SACOLA", "100", "0.10", unidade="UN")
    ))
    assert nota.chave == CHAVE
    assert (nota.numero, nota.serie) == (1234, 1)
    assert nota.emitente.cnpj == CNPJ_DISTRIBUIDORA
    assert nota.emitente.endereco == "Rua das Flores, 100"
    assert nota.cnpj_destinatario == "11111111000111"

    dipirona, sacola = nota.itens
    assert dipirona.valor_unitario == Decimal("22.5")  # (50 - 5 de desconto) / 2
    assert dipirona.fator_sugerido == 10  # 2 CX = 20 UN
    assert dipirona.registro_ms == "1234567890123"
    assert [(l.numero, l.quantidade) for l in dipirona.lotes] == [("ab12", 1), ("CD34", 1)]
    assert sacola.ean is None and sacola.fator_sugerido == 1


def test_xml_invalido(client, farmacia_a):
    assert _importar(client, farmacia_a, "isto não é um xml de jeito nenhum, é só um texto qualquer").status_code == 400
    sem_autorizacao = _xml(_det(1, "A1", "7891234567895", "DIPIRONA", "1", "10.00"), cstat="110")
    assert _importar(client, farmacia_a, sem_autorizacao).status_code == 400


def test_xml_com_entidade_externa_e_recusado(client, farmacia_a):
    malicioso = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x>&e; ' + "a" * 60 + "</x>"
    assert _importar(client, farmacia_a, malicioso).status_code == 400


def test_importar_conferir_e_confirmar(client, farmacia_a):
    matriz = _matriz(client, farmacia_a)
    dipirona = _produto(client, farmacia_a)  # EAN 7891234567895
    # A nota vem em displays com 10 caixinhas: o código de barras da caixinha está no campo tributável.
    xml = _xml(
        _det(1, "A1", "17891234567892", "DIPIRONA 500MG DISPLAY C/10", "2", "25.00", ean_trib="7891234567895",
             lotes=[("ab12", 1, _validade(200)), ("CD34", 1, _validade(300))], qtrib="20", utrib="UN")
        + _det(2, "B2", "SEM GTIN", "SACOLA PLASTICA", "100", "0.10", unidade="UN")
    )
    resposta = _importar(client, farmacia_a, xml)
    assert resposta.status_code == 201, resposta.text
    nota = resposta.json()
    assert nota["status"] == "pendente"
    assert nota["loja_id"] == matriz["id"]  # pelo CNPJ de destino
    assert nota["fornecedor_nome"] == "DistriSaúde"
    assert nota["itens_sem_produto"] == 1
    lote1, lote2, sacola = nota["itens"]
    assert (lote1["produto_id"], lote1["numero_lote"], lote1["fator"]) == (dipirona["id"], "AB12", 10)
    assert lote2["numero_lote"] == "CD34"
    assert sacola["produto_id"] is None

    # O fornecedor foi cadastrado com os dados da nota.
    fornecedores = client.get(f"{API}/fornecedores", headers=farmacia_a["headers"]).json()["itens"]
    assert [(f["cnpj"], f["cidade"]) for f in fornecedores] == [(CNPJ_DISTRIBUIDORA, "Campinas")]

    # Não confirma com item sem produto.
    confirmar = f"{API}/compras/notas/{nota['id']}/confirmar"
    assert client.post(confirmar, headers=farmacia_a["headers"]).status_code == 400

    # A sacola vira um produto novo, sem controle de lote.
    sacola_produto = _produto(client, farmacia_a, nome="Sacola", ean=None, controla_lote=False, preco_venda="0.00")
    item = f"{API}/compras/notas/{nota['id']}/itens/{sacola['id']}"
    resposta = client.patch(item, json={"produto_id": sacola_produto["id"]}, headers=farmacia_a["headers"])
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["itens_sem_produto"] == 0

    resposta = client.post(confirmar, headers=farmacia_a["headers"])
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["status"] == "confirmada"

    # Cada display tem 10 unidades: 2 displays viram 20 unidades, 10 em cada lote.
    assert _lotes(client, farmacia_a, dipirona, matriz["id"]) == {"AB12": 10, "CD34": 10}
    produto = client.get(f"{API}/produtos/{dipirona['id']}", headers=farmacia_a["headers"]).json()
    assert produto["preco_custo"] == "2.50"
    assert _lotes(client, farmacia_a, sacola_produto, matriz["id"]) == {"SEM-LOTE": 100}

    # Não confirma duas vezes nem importa de novo.
    assert client.post(confirmar, headers=farmacia_a["headers"]).status_code == 409
    assert _importar(client, farmacia_a, xml).status_code == 409


def test_codigo_do_fornecedor_e_lembrado(client, farmacia_a):
    dipirona = _produto(client, farmacia_a, ean="7890000000017")
    # A nota vem com um código de barras que o sistema não conhece.
    primeira = _importar(client, farmacia_a, _xml(_det(1, "XYZ-9", "SEM GTIN", "DIPIRONA", "3", "9.00",
                                                     lotes=[("Q1", 3, _validade())]))).json()
    item = primeira["itens"][0]
    assert item["produto_id"] is None
    client.patch(f"{API}/compras/notas/{primeira['id']}/itens/{item['id']}",
                 json={"produto_id": dipirona["id"], "fator": 2}, headers=farmacia_a["headers"])
    assert client.post(f"{API}/compras/notas/{primeira['id']}/confirmar", headers=farmacia_a["headers"]).status_code == 200

    outra_chave = "35261012345678000195550010000056781000056789"
    segunda = _importar(client, farmacia_a, _xml(_det(1, "XYZ-9", "SEM GTIN", "DIPIRONA", "1", "9.00",
                                                    lotes=[("Q2", 1, _validade())]), chave=outra_chave)).json()
    assert (segunda["itens"][0]["produto_id"], segunda["itens"][0]["fator"]) == (dipirona["id"], 2)


def test_nota_vai_para_a_loja_do_destinatario(client, farmacia_a):
    filial = _filial(client, farmacia_a)
    dipirona = _produto(client, farmacia_a)
    xml = _xml(_det(1, "A1", "7891234567895", "DIPIRONA", "5", "2.00", unidade="UN",
                    lotes=[("F1", 5, _validade())]), destinatario=filial["cnpj"])
    nota = _importar(client, farmacia_a, xml).json()
    assert nota["loja_id"] == filial["id"]
    client.post(f"{API}/compras/notas/{nota['id']}/confirmar", headers=farmacia_a["headers"])
    assert _lotes(client, farmacia_a, dipirona, filial["id"]) == {"F1": 5}

    # CNPJ de destino que não é de nenhuma loja: precisa escolher a loja.
    outra = _xml(_det(1, "A1", "7891234567895", "DIPIRONA", "1", "2.00"), destinatario="99999999000199",
                 chave="35261012345678000195550010000099991000099990")
    assert _importar(client, farmacia_a, outra).status_code == 400
    assert _importar(client, farmacia_a, outra, loja_id=filial["id"]).status_code == 201


def test_cancelar_nota_permite_importar_de_novo(client, farmacia_a):
    xml = _xml(_det(1, "A1", "7891234567895", "DIPIRONA", "1", "2.00"))
    nota = _importar(client, farmacia_a, xml).json()
    resposta = client.post(f"{API}/compras/notas/{nota['id']}/cancelar", headers=farmacia_a["headers"])
    assert resposta.json()["status"] == "cancelada"
    assert _importar(client, farmacia_a, xml).status_code == 201
    pendentes = client.get(f"{API}/compras/notas", params={"status": "pendente"}, headers=farmacia_a["headers"]).json()
    assert len(pendentes) == 1


def test_notas_de_outra_farmacia_nao_aparecem(client, farmacia_a, farmacia_b):
    nota = _importar(client, farmacia_a, _xml(_det(1, "A1", "7891234567895", "DIPIRONA", "1", "2.00"))).json()
    assert client.get(f"{API}/compras/notas/{nota['id']}", headers=farmacia_b["headers"]).status_code == 404
    assert client.get(f"{API}/compras/notas", headers=farmacia_b["headers"]).json() == []


def _vender(client, farmacia, produto_id, quantidade, valor):
    corpo = {
        "chave_idempotencia": str(uuid.uuid4()),
        "itens": [{"produto_id": produto_id, "quantidade": str(quantidade)}],
        "pagamentos": [{"forma": "pix", "valor": valor}],
    }
    resposta = client.post(f"{API}/vendas", json=corpo, headers=farmacia["headers"])
    assert resposta.status_code == 201, resposta.text


def test_sugestao_de_compras(client, farmacia_a):
    dipirona = _produto(client, farmacia_a, preco_venda="1.00")
    parado = _produto(client, farmacia_a, nome="Parado", ean="7890000000017", estoque_minimo="4")
    _produto(client, farmacia_a, nome="Sem movimento", ean="7890000000024")

    # Compra em dois fornecedores: o segundo cobra menos.
    nota = _importar(client, farmacia_a, _xml(_det(1, "A1", "7891234567895", "DIPIRONA", "40", "3.00", unidade="UN",
                                                 lotes=[("S1", 40, _validade())]))).json()
    client.post(f"{API}/compras/notas/{nota['id']}/confirmar", headers=farmacia_a["headers"])

    _abrir_caixa(client, farmacia_a)
    _vender(client, farmacia_a, dipirona["id"], 30, "30.00")

    sugestao = client.get(f"{API}/compras/sugestao", params={"dias_historico": 30, "dias_cobertura": 15},
                          headers=farmacia_a["headers"])
    assert sugestao.status_code == 200, sugestao.text
    itens = {i["nome"]: i for i in sugestao.json()["itens"]}
    assert set(itens) == {"Dipirona 500mg", "Parado"}

    # Vendeu 30 em 30 dias = 1 por dia; para 15 dias precisa de 15, tem 10: comprar 5.
    d = itens["Dipirona 500mg"]
    assert (Decimal(d["saldo"]), Decimal(d["media_diaria"]), Decimal(d["sugerido"])) == (10, 1, 5)
    assert Decimal(d["dias_de_estoque"]) == 10
    assert [(f["fornecedor_nome"], f["custo_unitario"]) for f in d["fornecedores"]] == [("DistriSaúde", "3.00")]

    # Sem venda, mas abaixo do mínimo: completa o mínimo.
    assert Decimal(itens["Parado"]["sugerido"]) == 4
    assert itens["Parado"]["dias_de_estoque"] is None

    # O que acaba primeiro vem antes. Total estimado pelo melhor preço.
    assert [i["nome"] for i in sugestao.json()["itens"]] == ["Dipirona 500mg", "Parado"]
    assert Decimal(sugestao.json()["total_estimado"]) == 15
