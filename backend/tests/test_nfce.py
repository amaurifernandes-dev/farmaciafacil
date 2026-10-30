import base64
import json
import uuid
from datetime import timedelta
from decimal import Decimal

import httpx
import pytest

from app.main import app
from app.modules.fiscal.provedores import FocusNFe, ProvedorFalso, ResultadoNota, get_provedor
from app.shared.datas import hoje
from tests.test_vendas import _abrir_caixa

API = "/api/v1"


@pytest.fixture
def sefaz():
    provedor = ProvedorFalso()
    app.dependency_overrides[get_provedor] = lambda: provedor
    yield provedor
    app.dependency_overrides.pop(get_provedor, None)


def _configurar(client, farmacia, **dados):
    resposta = client.put(f"{API}/fiscal/configuracao", json=dados, headers=farmacia["headers"])
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def _produto(client, farmacia, nome="Dipirona 500mg", preco="10.00", loja_id=None, **fiscal) -> dict:
    dados = {"nome": nome, "preco_venda": preco, "ncm": "30049099", "ean": "7891234567895", **fiscal}
    produto = client.post(f"{API}/produtos", json=dados, headers=farmacia["headers"]).json()
    entrada = {
        "loja_id": loja_id,
        "itens": [{
            "produto_id": produto["id"],
            "numero_lote": "L1",
            "validade": (hoje() + timedelta(days=90)).isoformat(),
            "quantidade": "50",
        }]
    }
    assert client.post(f"{API}/estoque/entradas", json=entrada, headers=farmacia["headers"]).status_code == 201
    return produto


def _vender(client, farmacia, itens, pagamentos, **extra) -> dict:
    corpo = {"chave_idempotencia": str(uuid.uuid4()), "itens": itens, "pagamentos": pagamentos, **extra}
    resposta = client.post(f"{API}/vendas", json=corpo, headers=farmacia["headers"])
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


@pytest.fixture
def caixa_aberto(client, farmacia_a):
    _abrir_caixa(client, farmacia_a)


def test_venda_emite_nfce_autorizada(client, farmacia_a, sefaz, caixa_aberto):
    _configurar(client, farmacia_a)
    produto = _produto(client, farmacia_a)

    venda = _vender(
        client, farmacia_a,
        [{"produto_id": produto["id"], "quantidade": "2"}],
        [{"forma": "dinheiro", "valor": "50.00"}],
        cliente_cpf="529.982.247-25",
    )

    nota = venda["nota"]
    assert nota["status"] == "autorizada"
    assert nota["numero"] == "1"
    assert nota["ambiente"] == "homologacao"
    assert nota["url_danfe"]
    enviada = sefaz.enviadas[venda["id"]]
    assert enviada["cnpj_emitente"] == "11111111000111"
    assert enviada["cpf_destinatario"] == "52998224725"
    assert enviada["items"][0]["codigo_ncm"] == "30049099"
    assert enviada["items"][0]["cfop"] == "5102"
    assert enviada["items"][0]["icms_situacao_tributaria"] == "102"
    assert enviada["items"][0]["valor_bruto"] == "20.00"
    # O troco (30,00) sai do dinheiro: a nota recebe só o que ficou.
    assert enviada["formas_pagamento"] == [{"forma_pagamento": "01", "valor_pagamento": "20.00"}]


def test_desconto_da_venda_e_rateado_e_tributacao_do_produto_prevalece(client, farmacia_a, sefaz, caixa_aberto):
    _configurar(client, farmacia_a)
    remedio = _produto(client, farmacia_a, cfop="5405", icms_situacao_tributaria="500",
                       pis_cofins_situacao_tributaria="04", cest="1300100")
    sabonete = _produto(client, farmacia_a, nome="Sabonete", preco="5.00", ean="7890000000017")

    venda = _vender(
        client, farmacia_a,
        [{"produto_id": remedio["id"], "quantidade": "1"},
         {"produto_id": sabonete["id"], "quantidade": "1", "desconto": "0.50"}],
        [{"forma": "pix", "valor": "13.50"}],
        desconto="1.00",
    )

    itens = sefaz.enviadas[venda["id"]]["items"]
    descontos = [Decimal(i.get("valor_desconto", "0")) for i in itens]
    assert sum(descontos) == Decimal("1.50")
    assert descontos == [Decimal("0.68"), Decimal("0.82")]  # 1,00 rateado sobre 10,00 e 4,50 (sobra no último)
    assert itens[0]["cfop"] == "5405"
    assert itens[0]["icms_situacao_tributaria"] == "500"
    assert itens[0]["pis_situacao_tributaria"] == "04"
    assert itens[0]["cest"] == "1300100"
    assert itens[1]["pis_situacao_tributaria"] == "49"
    assert sefaz.enviadas[venda["id"]]["formas_pagamento"] == [
        {"forma_pagamento": "17", "valor_pagamento": "13.50", "tipo_integracao": "2"}
    ]


def test_sem_configuracao_fiscal_a_venda_nao_emite(client, farmacia_a, sefaz, caixa_aberto):
    produto = _produto(client, farmacia_a)
    venda = _vender(client, farmacia_a, [{"produto_id": produto["id"], "quantidade": "1"}],
                    [{"forma": "pix", "valor": "10.00"}])
    assert venda["nota"] is None
    assert sefaz.enviadas == {}

    resposta = client.post(f"{API}/vendas/{venda['id']}/nfce", headers=farmacia_a["headers"])
    assert resposta.status_code == 400
    assert "Configure" in resposta.json()["detail"]


def test_produto_sem_ncm_nao_envia_e_pode_reenviar_depois(client, farmacia_a, sefaz, caixa_aberto):
    _configurar(client, farmacia_a)
    produto = _produto(client, farmacia_a, ncm=None)
    venda = _vender(client, farmacia_a, [{"produto_id": produto["id"], "quantidade": "1"}],
                    [{"forma": "pix", "valor": "10.00"}])
    assert venda["nota"]["status"] == "erro"
    assert "NCM" in venda["nota"]["mensagem"]
    assert sefaz.enviadas == {}

    client.patch(f"{API}/produtos/{produto['id']}", json={"ncm": "30049099"}, headers=farmacia_a["headers"])
    nota = client.post(f"{API}/vendas/{venda['id']}/nfce", headers=farmacia_a["headers"]).json()
    assert nota["status"] == "autorizada"
    assert nota["tentativas"] == 1


def test_rejeicao_fica_registrada_e_reenvio_autoriza(client, farmacia_a, sefaz, caixa_aberto):
    _configurar(client, farmacia_a)
    produto = _produto(client, farmacia_a)
    sefaz.proxima_resposta = ResultadoNota(status="rejeitada", status_sefaz="704", mensagem="Rejeição: data atrasada")
    venda = _vender(client, farmacia_a, [{"produto_id": produto["id"], "quantidade": "1"}],
                    [{"forma": "pix", "valor": "10.00"}])
    assert venda["nota"]["status"] == "rejeitada"
    assert venda["nota"]["status_sefaz"] == "704"

    nota = client.post(f"{API}/vendas/{venda['id']}/nfce", headers=farmacia_a["headers"]).json()
    assert nota["status"] == "autorizada"
    assert nota["tentativas"] == 2
    # Já autorizada: chamar de novo não reenvia.
    client.post(f"{API}/vendas/{venda['id']}/nfce", headers=farmacia_a["headers"])
    assert client.get(f"{API}/vendas/{venda['id']}/nfce", headers=farmacia_a["headers"]).json()["tentativas"] == 2


def test_processando_consulta_antes_de_reenviar(client, farmacia_a, sefaz, caixa_aberto):
    _configurar(client, farmacia_a)
    produto = _produto(client, farmacia_a)
    sefaz.proxima_resposta = ResultadoNota(status="processando", mensagem="Sem resposta")
    venda = _vender(client, farmacia_a, [{"produto_id": produto["id"], "quantidade": "1"}],
                    [{"forma": "pix", "valor": "10.00"}])
    assert venda["nota"]["status"] == "processando"

    # Enquanto isso o provedor autorizou.
    sefaz.notas[venda["id"]] = ResultadoNota(status="autorizada", numero="7", serie="1", chave="3" * 44)
    nota = client.get(f"{API}/vendas/{venda['id']}/nfce", params={"atualizar": True},
                      headers=farmacia_a["headers"]).json()
    assert nota["status"] == "autorizada"
    assert nota["numero"] == "7"
    assert nota["tentativas"] == 1


def test_cancelar_venda_cancela_a_nfce(client, farmacia_a, sefaz, caixa_aberto):
    _configurar(client, farmacia_a)
    produto = _produto(client, farmacia_a)
    venda = _vender(client, farmacia_a, [{"produto_id": produto["id"], "quantidade": "1"}],
                    [{"forma": "pix", "valor": "10.00"}])

    curto = client.post(f"{API}/vendas/{venda['id']}/cancelar", json={"motivo": "erro"}, headers=farmacia_a["headers"])
    assert curto.status_code == 400
    assert "15 caracteres" in curto.json()["detail"]

    resposta = client.post(f"{API}/vendas/{venda['id']}/cancelar",
                           json={"motivo": "Cliente desistiu da compra"}, headers=farmacia_a["headers"])
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["status"] == "cancelada"
    assert resposta.json()["nota"]["status"] == "cancelada"
    assert resposta.json()["nota"]["url_xml_cancelamento"]


def test_sefaz_recusa_cancelamento_e_venda_continua(client, farmacia_a, sefaz, caixa_aberto):
    _configurar(client, farmacia_a)
    produto = _produto(client, farmacia_a)
    venda = _vender(client, farmacia_a, [{"produto_id": produto["id"], "quantidade": "1"}],
                    [{"forma": "pix", "valor": "10.00"}])
    sefaz.cancelar = lambda *_: ResultadoNota(status="erro", mensagem="Prazo de cancelamento superado")

    resposta = client.post(f"{API}/vendas/{venda['id']}/cancelar",
                           json={"motivo": "Cliente desistiu da compra"}, headers=farmacia_a["headers"])
    assert resposta.status_code == 400
    assert "Prazo" in resposta.json()["detail"]
    assert client.get(f"{API}/vendas/{venda['id']}", headers=farmacia_a["headers"]).json()["status"] == "finalizada"


def test_nota_de_outra_farmacia_nao_aparece(client, farmacia_a, farmacia_b, sefaz, caixa_aberto):
    _configurar(client, farmacia_a)
    produto = _produto(client, farmacia_a)
    venda = _vender(client, farmacia_a, [{"produto_id": produto["id"], "quantidade": "1"}],
                    [{"forma": "pix", "valor": "10.00"}])
    assert client.get(f"{API}/vendas/{venda['id']}/nfce", headers=farmacia_b["headers"]).status_code == 404
    assert client.post(f"{API}/vendas/{venda['id']}/nfce", headers=farmacia_b["headers"]).status_code == 404
    assert client.get(f"{API}/fiscal/configuracao", headers=farmacia_b["headers"]).status_code == 404


# --- Cliente da Focus NFe, com o HTTP simulado ---

def _focus(responder) -> tuple[FocusNFe, list[httpx.Request]]:
    pedidos: list[httpx.Request] = []

    def handler(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        return responder(pedido)

    return FocusNFe({"homologacao": "tok-h", "producao": "tok-p"}, transport=httpx.MockTransport(handler)), pedidos


def test_focus_emitir_autorizado():
    focus, pedidos = _focus(lambda _: httpx.Response(201, json={
        "status": "autorizado", "status_sefaz": "100", "mensagem_sefaz": "Autorizado o uso da NF-e",
        "chave_nfe": "NFe" + "1" * 44, "numero": "12", "serie": "1",
        "caminho_danfe": "/notas_fiscais_consumidor/NFe111.html", "qrcode_url": "https://sefaz/qr",
    }))
    resultado = focus.emitir("homologacao", "ref-1", {"items": []})

    assert resultado.status == "autorizada"
    assert resultado.chave == "1" * 44
    assert resultado.url_danfe == "https://homologacao.focusnfe.com.br/notas_fiscais_consumidor/NFe111.html"
    pedido = pedidos[0]
    assert pedido.method == "POST"
    assert str(pedido.url) == "https://homologacao.focusnfe.com.br/v2/nfce?ref=ref-1"
    assert pedido.headers["authorization"] == "Basic " + base64.b64encode(b"tok-h:").decode()


def test_focus_ja_processada_consulta():
    def responder(pedido):
        if pedido.method == "POST":
            return httpx.Response(422, json={"codigo": "already_processed", "mensagem": "A nota fiscal já foi autorizada"})
        return httpx.Response(200, json={"status": "autorizado", "numero": "3"})

    focus, pedidos = _focus(responder)
    resultado = focus.emitir("producao", "ref-2", {})
    assert resultado.status == "autorizada"
    assert [p.method for p in pedidos] == ["POST", "GET"]
    assert str(pedidos[1].url) == "https://api.focusnfe.com.br/v2/nfce/ref-2"


def test_focus_erros():
    def timeout(pedido):
        raise httpx.ReadTimeout("lento", request=pedido)

    assert _focus(timeout)[0].emitir("homologacao", "r", {}).status == "processando"

    validacao = _focus(lambda _: httpx.Response(422, json={
        "codigo": "erro_validacao_schema", "mensagem": "Erro de validação",
        "erros": [{"campo": "data_emissao", "mensagem": "data_emissao não pode ser vazio"}],
    }))[0].emitir("homologacao", "r", {})
    assert validacao.status == "erro"
    assert validacao.mensagem == "Erro de validação: data_emissao não pode ser vazio"

    rejeitada = _focus(lambda _: httpx.Response(201, json={
        "status": "erro_autorizacao", "status_sefaz": "704", "mensagem_sefaz": "Rejeição: atrasada",
    }))[0].emitir("homologacao", "r", {})
    assert (rejeitada.status, rejeitada.status_sefaz) == ("rejeitada", "704")

    assert _focus(lambda _: httpx.Response(404, json={}))[0].consultar("homologacao", "r").status == "nao_encontrada"


def test_focus_cancelar():
    focus, pedidos = _focus(lambda _: httpx.Response(200, json={
        "status": "cancelado", "status_sefaz": "135", "caminho_xml_cancelamento": "/arquivos/can.xml",
    }))
    resultado = focus.cancelar("homologacao", "ref-3", "Cliente desistiu da compra")
    assert resultado.status == "cancelada"
    assert resultado.url_xml_cancelamento == "https://homologacao.focusnfe.com.br/arquivos/can.xml"
    assert pedidos[0].method == "DELETE"
    assert json.loads(pedidos[0].content) == {"justificativa": "Cliente desistiu da compra"}

    recusado = _focus(lambda _: httpx.Response(200, json={"status": "erro_cancelamento", "mensagem_sefaz": "Prazo"}))
    assert recusado[0].cancelar("homologacao", "r", "x" * 15).status == "erro"


def test_focus_sem_token():
    focus = FocusNFe({"homologacao": "", "producao": ""})
    with pytest.raises(Exception, match="Token"):
        focus.emitir("homologacao", "r", {})


def test_nfce_da_filial_sai_com_o_cnpj_da_filial(client, farmacia_a, sefaz):
    filial = {"nome": "Filial Centro", "razao_social": "Farmácia Exemplo LTDA",
              "nome_fantasia": "Farmácia Exemplo Centro", "cnpj": "11.222.333/0001-81", "uf": "sp"}
    loja = client.post(f"{API}/lojas", json=filial, headers=farmacia_a["headers"])
    assert loja.status_code == 201, loja.text
    terminal = client.post(f"{API}/terminais", json={"loja_id": loja.json()["id"], "nome": "PDV Centro"},
                           headers=farmacia_a["headers"]).json()
    chave = client.post(f"{API}/terminais/{terminal['id']}/vincular", headers=farmacia_a["headers"]).json()["chave"]
    farmacia_a["headers"]["X-Terminal"] = chave
    _abrir_caixa(client, farmacia_a)
    _configurar(client, farmacia_a)
    # A filial vende do próprio estoque.
    produto = _produto(client, farmacia_a, loja_id=loja.json()["id"])

    venda = _vender(client, farmacia_a, [{"produto_id": produto["id"], "quantidade": "1"}],
                    [{"forma": "pix", "valor": "10.00"}])
    assert venda["nota"]["status"] == "autorizada"
    assert sefaz.enviadas[venda["id"]]["cnpj_emitente"] == "11222333000181"
