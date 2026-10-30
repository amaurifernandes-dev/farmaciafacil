"""Pré-venda: o balconista monta no balcão e o caixa central recebe."""

from tests.test_vendas import API, _abrir_caixa, _produto_com_estoque, _saldo, _venda


def test_pre_venda_recebida_no_caixa(client, farmacia_a):
    h = farmacia_a["headers"]
    produto = _produto_com_estoque(client, farmacia_a)
    criada = client.post(
        f"{API}/pre-vendas", json={"itens": [{"produto_id": produto["id"], "quantidade": "2"}]}, headers=h
    )
    assert criada.status_code == 201, criada.text
    pre = criada.json()
    assert pre["numero"] == 1
    assert pre["total"] == "17.80"
    assert pre["vendedor"] == "Admin"
    assert pre["itens"][0]["descricao"] == "Dipirona 500mg"
    # Pré-venda não mexe no estoque.
    assert _saldo(client, farmacia_a, produto["id"]) == {"A": 5}

    assert [p["numero"] for p in client.get(f"{API}/pre-vendas", headers=h).json()] == [1]
    assert client.get(f"{API}/pre-vendas/numero/1", headers=h).json()["id"] == pre["id"]

    _abrir_caixa(client, farmacia_a)
    venda = _venda(produto["id"], "2", [{"forma": "pix", "valor": "17.80"}], pre_venda_id=pre["id"])
    resposta = client.post(f"{API}/vendas", json=venda, headers=h)
    assert resposta.status_code == 201, resposta.text

    recebida = client.get(f"{API}/pre-vendas/{pre['id']}", headers=h).json()
    assert recebida["status"] == "recebida"
    assert recebida["venda_id"] == resposta.json()["id"]
    assert client.get(f"{API}/pre-vendas", headers=h).json() == []

    de_novo = _venda(produto["id"], "1", [{"forma": "pix", "valor": "8.90"}], pre_venda_id=pre["id"])
    assert client.post(f"{API}/vendas", json=de_novo, headers=h).status_code == 409


def test_cancelar_pre_venda(client, farmacia_a, farmacia_b):
    h = farmacia_a["headers"]
    produto = _produto_com_estoque(client, farmacia_a)
    pre = client.post(f"{API}/pre-vendas", json={"itens": [{"produto_id": produto["id"], "quantidade": "1"}]}, headers=h).json()
    assert client.get(f"{API}/pre-vendas/{pre['id']}", headers=farmacia_b["headers"]).status_code == 404
    assert client.post(f"{API}/pre-vendas/{pre['id']}/cancelar", headers=farmacia_b["headers"]).status_code == 404
    assert client.post(f"{API}/pre-vendas/{pre['id']}/cancelar", headers=h).json()["status"] == "cancelada"
    assert client.post(f"{API}/pre-vendas/{pre['id']}/cancelar", headers=h).status_code == 409
