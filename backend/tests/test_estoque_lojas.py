from datetime import timedelta
from decimal import Decimal

from app.shared.datas import hoje
from tests.test_vendas import _abrir_caixa, _venda

API = "/api/v1"


def _filial(client, farmacia, nome="Filial Centro", cnpj="11222333000181") -> dict:
    dados = {"nome": nome, "razao_social": "Farmácia Exemplo LTDA", "nome_fantasia": nome, "cnpj": cnpj, "uf": "SP"}
    resposta = client.post(f"{API}/lojas", json=dados, headers=farmacia["headers"])
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _matriz(client, farmacia) -> dict:
    return next(l for l in client.get(f"{API}/lojas", headers=farmacia["headers"]).json() if l["matriz"])


def _produto(client, farmacia, nome="Dipirona 500mg", **campos) -> dict:
    dados = {"nome": nome, "preco_venda": "8.90", "ean": "7891234567895", **campos}
    resposta = client.post(f"{API}/produtos", json=dados, headers=farmacia["headers"])
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _entrada(client, farmacia, produto, loja_id, quantidade, lote="L1", dias=200):
    corpo = {
        "loja_id": loja_id,
        "itens": [{
            "produto_id": produto["id"],
            "numero_lote": lote,
            "validade": (hoje() + timedelta(days=dias)).isoformat(),
            "quantidade": str(quantidade),
        }],
    }
    resposta = client.post(f"{API}/estoque/entradas", json=corpo, headers=farmacia["headers"])
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _lotes(client, farmacia, produto, loja_id) -> dict:
    lotes = client.get(
        f"{API}/estoque/lotes",
        params={"produto_id": produto["id"], "loja_id": loja_id, "incluir_zerados": True},
        headers=farmacia["headers"],
    ).json()
    return {l["numero_lote"]: Decimal(l["quantidade"]) for l in lotes}


def test_entrada_sem_loja_vai_para_a_matriz(client, farmacia_a):
    matriz = _matriz(client, farmacia_a)
    produto = _produto(client, farmacia_a)
    movimentos = _entrada(client, farmacia_a, produto, None, 5)
    assert movimentos[0]["loja_id"] == matriz["id"]
    assert _lotes(client, farmacia_a, produto, matriz["id"]) == {"L1": 5}


def test_cada_loja_tem_o_seu_estoque(client, farmacia_a):
    matriz = _matriz(client, farmacia_a)
    filial = _filial(client, farmacia_a)
    produto = _produto(client, farmacia_a)
    _entrada(client, farmacia_a, produto, matriz["id"], 10)
    _entrada(client, farmacia_a, produto, filial["id"], 3)

    # O mesmo número de lote existe nas duas lojas, cada um com o seu saldo.
    assert _lotes(client, farmacia_a, produto, matriz["id"]) == {"L1": 10}
    assert _lotes(client, farmacia_a, produto, filial["id"]) == {"L1": 3}

    saldos = client.get(f"{API}/estoque/saldos", headers=farmacia_a["headers"]).json()
    item = saldos["itens"][0]
    assert Decimal(item["total"]) == 13
    assert {k: Decimal(v) for k, v in item["por_loja"].items()} == {matriz["id"]: 10, filial["id"]: 3}

    # Fora de um PDV, a bipada mostra o total; com loja, só o daquela loja.
    ean = f"{API}/produtos/ean/7891234567895"
    assert Decimal(client.get(ean, headers=farmacia_a["headers"]).json()["saldo"]) == 13
    assert Decimal(client.get(ean, params={"loja_id": filial["id"]}, headers=farmacia_a["headers"]).json()["saldo"]) == 3


def test_venda_baixa_so_da_loja_do_caixa(client, farmacia_a):
    matriz = _matriz(client, farmacia_a)
    filial = _filial(client, farmacia_a)
    produto = _produto(client, farmacia_a)
    _entrada(client, farmacia_a, produto, filial["id"], 4)

    # O PDV é da matriz, que não tem estoque.
    _abrir_caixa(client, farmacia_a)
    saldo = client.get(f"{API}/produtos/ean/7891234567895", headers=farmacia_a["headers"]).json()["saldo"]
    assert Decimal(saldo) == 0
    resposta = client.post(f"{API}/vendas", json=_venda(produto["id"]), headers=farmacia_a["headers"])
    assert resposta.status_code == 409

    _entrada(client, farmacia_a, produto, matriz["id"], 2)
    resposta = client.post(f"{API}/vendas", json=_venda(produto["id"]), headers=farmacia_a["headers"])
    assert resposta.status_code == 201, resposta.text
    assert _lotes(client, farmacia_a, produto, matriz["id"]) == {"L1": 1}
    assert _lotes(client, farmacia_a, produto, filial["id"]) == {"L1": 4}


def test_transferencia_entre_lojas(client, farmacia_a):
    matriz = _matriz(client, farmacia_a)
    filial = _filial(client, farmacia_a)
    produto = _produto(client, farmacia_a)
    _entrada(client, farmacia_a, produto, matriz["id"], 10, lote="T1", dias=120)
    lote = client.get(
        f"{API}/estoque/lotes", params={"produto_id": produto["id"], "loja_id": matriz["id"]}, headers=farmacia_a["headers"]
    ).json()[0]

    corpo = {"loja_destino_id": filial["id"], "itens": [{"lote_id": lote["id"], "quantidade": "4"}]}
    resposta = client.post(f"{API}/estoque/transferencias", json=corpo, headers=farmacia_a["headers"])
    assert resposta.status_code == 201, resposta.text
    saida, chegada = resposta.json()
    assert (saida["loja_id"], Decimal(saida["quantidade"])) == (matriz["id"], -4)
    assert (chegada["loja_id"], Decimal(chegada["quantidade"])) == (filial["id"], 4)
    assert saida["referencia_id"] == chegada["referencia_id"]

    assert _lotes(client, farmacia_a, produto, matriz["id"]) == {"T1": 6}
    assert _lotes(client, farmacia_a, produto, filial["id"]) == {"T1": 4}
    destino = client.get(
        f"{API}/estoque/lotes", params={"produto_id": produto["id"], "loja_id": filial["id"]}, headers=farmacia_a["headers"]
    ).json()[0]
    assert destino["validade"] == lote["validade"]

    # Mais do que tem: recusa e não mexe em nada.
    corpo["itens"][0]["quantidade"] = "7"
    assert client.post(f"{API}/estoque/transferencias", json=corpo, headers=farmacia_a["headers"]).status_code == 409
    assert _lotes(client, farmacia_a, produto, matriz["id"]) == {"T1": 6}

    # Para a mesma loja não faz sentido.
    corpo = {"loja_destino_id": matriz["id"], "itens": [{"lote_id": lote["id"], "quantidade": "1"}]}
    assert client.post(f"{API}/estoque/transferencias", json=corpo, headers=farmacia_a["headers"]).status_code == 400


def test_minimo_vale_para_cada_loja(client, farmacia_a):
    matriz = _matriz(client, farmacia_a)
    filial = _filial(client, farmacia_a)
    produto = _produto(client, farmacia_a, estoque_minimo="5")
    _entrada(client, farmacia_a, produto, matriz["id"], 10)

    alertas = client.get(f"{API}/estoque/alertas", headers=farmacia_a["headers"]).json()
    assert [(p["nome"], p["loja_nome"]) for p in alertas["abaixo_do_minimo"]] == [("Dipirona 500mg", "Filial Centro")]

    so_matriz = client.get(f"{API}/estoque/alertas", params={"loja_id": matriz["id"]}, headers=farmacia_a["headers"])
    assert so_matriz.json()["abaixo_do_minimo"] == []


def test_lojas_de_outra_farmacia_nao_servem(client, farmacia_a, farmacia_b):
    filial_b = _filial(client, farmacia_b, cnpj="33444555000181")
    produto = _produto(client, farmacia_a)
    corpo = {"loja_id": filial_b["id"], "itens": [{"produto_id": produto["id"], "numero_lote": "X",
             "validade": (hoje() + timedelta(days=30)).isoformat(), "quantidade": "1"}]}
    assert client.post(f"{API}/estoque/entradas", json=corpo, headers=farmacia_a["headers"]).status_code == 404
