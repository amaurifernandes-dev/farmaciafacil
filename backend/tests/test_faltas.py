from datetime import timedelta
from decimal import Decimal

from app.shared.datas import hoje
from tests.test_financeiro import _cliente
from tests.test_promocoes_relatorios import _produto, _vender
from tests.test_vendas import _abrir_caixa

API = "/api/v1"


def _falta(client, farmacia, esperado=201, **dados):
    resposta = client.post(f"{API}/faltas", json=dados, headers=farmacia["headers"])
    assert resposta.status_code == esperado, resposta.text
    return resposta.json()


def _lista(client, farmacia, situacao="encomendas", **params):
    resposta = client.get(f"{API}/faltas", params={"situacao": situacao, **params}, headers=farmacia["headers"])
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def _entrada(client, farmacia, produto, quantidade):
    item = {"produto_id": produto["id"], "numero_lote": "L2", "quantidade": str(quantidade),
            "validade": (hoje() + timedelta(days=200)).isoformat()}
    resposta = client.post(f"{API}/estoque/entradas", json={"itens": [item]}, headers=farmacia["headers"])
    assert resposta.status_code == 201, resposta.text


def test_falta_sem_contato_e_encomenda_com_contato(client, farmacia_a):
    losartana = _produto(client, farmacia_a, "Losartana", "12.00")
    _falta(client, farmacia_a, esperado=422)  # nem produto nem descrição

    falta = _falta(client, farmacia_a, produto_id=losartana["id"], quantidade="2")
    assert (falta["status"], falta["encomenda"], falta["descricao"]) == ("registrada", False, "Losartana")

    encomenda = _falta(client, farmacia_a, descricao="  Pomada manipulada  ", contato_nome="Ana",
                       contato_telefone="(11) 98888-7777")
    assert (encomenda["status"], encomenda["descricao"], encomenda["saldo"]) == ("aberta", "Pomada manipulada", None)

    # Faltas só anotadas não aparecem nas encomendas.
    assert [i["id"] for i in _lista(client, farmacia_a)["itens"]] == [encomenda["id"]]
    assert [i["id"] for i in _lista(client, farmacia_a, "faltas")["itens"]] == [falta["id"]]
    assert _lista(client, farmacia_a, busca="pomada")["itens"][0]["nome"] == "Ana"

    # Não tem ninguém para avisar numa falta sem contato.
    assert client.post(f"{API}/faltas/{falta['id']}/avisar", headers=farmacia_a["headers"]).status_code == 400


def test_mostra_quando_chegou_e_quem_avisar(client, farmacia_a):
    dipirona = _produto(client, farmacia_a, "Dipirona", "8.00", quantidade=1)
    maria = _cliente(client, farmacia_a, "Maria Souza")
    encomenda = _falta(client, farmacia_a, produto_id=dipirona["id"], quantidade="3", cliente_id=maria["id"])
    assert (encomenda["nome"], encomenda["chegou"], Decimal(encomenda["saldo"])) == ("Maria Souza", False, 1)

    resumo = _lista(client, farmacia_a)["resumo"]
    assert (resumo["encomendas"], resumo["chegaram"]) == (1, 0)

    _entrada(client, farmacia_a, dipirona, 5)
    lista = _lista(client, farmacia_a, "chegaram")
    assert [i["id"] for i in lista["itens"]] == [encomenda["id"]]
    assert lista["resumo"]["chegaram"] == 1

    avisado = client.post(f"{API}/faltas/{encomenda['id']}/avisar", headers=farmacia_a["headers"]).json()
    assert (avisado["status"], avisado["chegou"], avisado["avisado_em"] is not None) == ("avisado", False, True)
    assert _lista(client, farmacia_a)["resumo"]["avisados"] == 1

    entregue = client.post(f"{API}/faltas/{encomenda['id']}/entregar", headers=farmacia_a["headers"]).json()
    assert entregue["status"] == "entregue"
    assert client.post(f"{API}/faltas/{encomenda['id']}/cancelar", headers=farmacia_a["headers"]).status_code == 400
    assert [i["id"] for i in _lista(client, farmacia_a, "encerradas")["itens"]] == [encomenda["id"]]


def test_venda_para_o_cliente_entrega_a_encomenda(client, farmacia_a):
    fralda = _produto(client, farmacia_a, "Fralda", "30.00")
    joao = _cliente(client, farmacia_a, "João Pereira")
    _abrir_caixa(client, farmacia_a)
    encomenda = _falta(client, farmacia_a, produto_id=fralda["id"], cliente_id=joao["id"])
    # No caixa, a falta é anotada na loja do caixa.
    assert encomenda["loja_id"] == client.get(f"{API}/lojas", headers=farmacia_a["headers"]).json()[0]["id"]

    venda = _vender(client, farmacia_a, [(fralda, 1)], [{"forma": "pix", "valor": "30.00"}], cliente_id=joao["id"])
    assert _lista(client, farmacia_a)["itens"] == []
    assert _lista(client, farmacia_a, "encerradas")["itens"][0]["status"] == "entregue"

    # Venda cancelada: a encomenda volta para a lista.
    resposta = client.post(f"{API}/vendas/{venda['id']}/cancelar", json={"motivo": "Cliente desistiu"},
                           headers=farmacia_a["headers"])
    assert resposta.status_code == 200, resposta.text
    assert _lista(client, farmacia_a)["itens"][0]["status"] == "aberta"


def test_faltas_entram_na_sugestao_de_compras(client, farmacia_a):
    losartana = _produto(client, farmacia_a, "Losartana", "12.00", quantidade=2)
    for _ in range(3):
        _falta(client, farmacia_a, produto_id=losartana["id"], quantidade="10")
    _falta(client, farmacia_a, produto_id=losartana["id"], quantidade="4", contato_nome="Ana")
    cancelada = _falta(client, farmacia_a, produto_id=losartana["id"], quantidade="50", contato_nome="Bia")
    client.post(f"{API}/faltas/{cancelada['id']}/cancelar", headers=farmacia_a["headers"])

    sugestao = client.get(f"{API}/compras/sugestao", params={"dias_historico": 30, "dias_cobertura": 15},
                          headers=farmacia_a["headers"]).json()
    item = next(i for i in sugestao["itens"] if i["nome"] == "Losartana")
    # 30 que faltaram em 30 dias = 1 por dia, para 15 dias, mais as 4 encomendadas, menos as 2 que tem.
    assert (Decimal(item["faltas_no_periodo"]), Decimal(item["encomendas_abertas"])) == (30, 4)
    assert Decimal(item["sugerido"]) == 17

    resumo = _lista(client, farmacia_a)["resumo"]
    assert resumo["faltas_30_dias"] == 4
    assert (resumo["mais_pedidos"][0]["descricao"], resumo["mais_pedidos"][0]["vezes"]) == ("Losartana", 4)


def test_faltas_isoladas_por_farmacia(client, farmacia_a, farmacia_b):
    falta = _falta(client, farmacia_a, descricao="Xarope")
    assert _lista(client, farmacia_b, "todas")["itens"] == []
    assert client.post(f"{API}/faltas/{falta['id']}/cancelar", headers=farmacia_b["headers"]).status_code == 404


def test_painel_avisa_encomendas_que_chegaram(client, farmacia_a):
    dipirona = _produto(client, farmacia_a, "Dipirona", "8.00", quantidade=5)
    _falta(client, farmacia_a, produto_id=dipirona["id"], contato_telefone="11999990000")
    _falta(client, farmacia_a, produto_id=dipirona["id"], quantidade="9", contato_telefone="11999990001")
    assert client.get(f"{API}/painel", headers=farmacia_a["headers"]).json()["encomendas_chegaram"] == 1
