from tests.test_promocoes_relatorios import _produto, _promocao

API = "/api/v1"


def _lista(client, farmacia, **params):
    resposta = client.get(f"{API}/etiquetas", params=params, headers=farmacia["headers"])
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def _motivos(lista):
    return {i["nome"]: i["motivo"] for i in lista["itens"]}


def _marcar(client, farmacia, produtos):
    resposta = client.post(f"{API}/etiquetas/impressas", json={"produto_ids": [p["id"] for p in produtos]},
                           headers=farmacia["headers"])
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def test_etiqueta_pede_troca_quando_preco_ou_promocao_muda(client, farmacia_a):
    h = farmacia_a["headers"]
    dipirona = _produto(client, farmacia_a, "Dipirona", "8.90", ean="7891234567895")
    vitamina = _produto(client, farmacia_a, "Vitamina C", "20.00")
    sem_estoque = client.post(f"{API}/produtos", json={"nome": "Shampoo", "preco_venda": "15.00"}, headers=h).json()

    # Novos: nunca impressas. Sem estoque na loja fica de fora, a não ser que peça.
    lista = _lista(client, farmacia_a)
    assert _motivos(lista) == {"Dipirona": "nunca_impressa", "Vitamina C": "nunca_impressa"}
    assert (lista["para_trocar"], lista["nunca_impressas"]) == (2, 2)
    assert "Shampoo" in _motivos(_lista(client, farmacia_a, so_com_estoque=False))

    assert _marcar(client, farmacia_a, [dipirona, vitamina]) == {"marcadas": 2}
    assert _lista(client, farmacia_a)["itens"] == []
    todas = _lista(client, farmacia_a, situacao="todas")
    assert _motivos(todas) == {"Dipirona": None, "Vitamina C": None}
    assert todas["itens"][0]["impressa"]["preco"] == "8.90"

    # Mudou o preço: trocar, mostrando o preço que está na gôndola.
    client.patch(f"{API}/produtos/{dipirona['id']}", json={"preco_venda": "9.50"}, headers=h)
    lista = _lista(client, farmacia_a)
    assert _motivos(lista) == {"Dipirona": "preco_subiu"}
    item = lista["itens"][0]
    assert (item["preco"], item["impressa"]["preco"], lista["preco_mudou"]) == ("9.50", "8.90", 1)

    # Promoção para todos entra na etiqueta; a só para clientes, não.
    _promocao(client, farmacia_a, [vitamina], percentual="25")
    _promocao(client, farmacia_a, [dipirona], percentual="50", so_clientes=True)
    lista = _lista(client, farmacia_a)
    assert _motivos(lista) == {"Dipirona": "preco_subiu", "Vitamina C": "promocao_comecou"}
    vit = next(i for i in lista["itens"] if i["nome"] == "Vitamina C")
    assert (vit["preco_promocional"], vit["promocao"]) == ("15.00", "25% de desconto")

    _marcar(client, farmacia_a, [dipirona, vitamina])
    assert _lista(client, farmacia_a)["para_trocar"] == 0

    # Promoção acabou: volta a etiqueta normal.
    promocoes = client.get(f"{API}/promocoes", headers=h).json()
    para_todos = next(p for p in promocoes if not p["so_clientes"])
    assert client.post(f"{API}/promocoes/{para_todos['id']}/encerrar", headers=h).status_code == 200
    assert _motivos(_lista(client, farmacia_a)) == {"Vitamina C": "promocao_acabou"}

    # Leve e pague vai como texto (na gôndola ainda está a de 25%, que não foi trocada).
    _promocao(client, farmacia_a, [vitamina], tipo="leve_pague", percentual=None, leve=3, pague=2)
    vit = _lista(client, farmacia_a)["itens"][0]
    assert (vit["motivo"], vit["promocao"], vit["preco_promocional"]) == ("promocao_mudou", "Leve 3, pague 2", None)

    # Busca por nome ou código.
    assert _motivos(_lista(client, farmacia_a, situacao="todas", busca="7891234567895")) == {"Dipirona": None}
    assert client.post(f"{API}/etiquetas/impressas", json={"produto_ids": [sem_estoque["id"], "0" * 32]},
                       headers=h).status_code in (404, 422)


def test_etiquetas_sao_de_cada_farmacia(client, farmacia_a, farmacia_b):
    dipirona = _produto(client, farmacia_a, "Dipirona", "8.90")
    assert _lista(client, farmacia_b, so_com_estoque=False)["itens"] == []
    resposta = client.post(f"{API}/etiquetas/impressas", json={"produto_ids": [dipirona["id"]]},
                           headers=farmacia_b["headers"])
    assert resposta.status_code == 404
