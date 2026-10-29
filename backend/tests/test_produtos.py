DIPIRONA = {
    "ean": "7891234567890",
    "nome": "Dipirona 500mg",
    "apresentacao": "10 comprimidos",
    "preco_venda": "8.90",
    "tipo": "medicamento",
}


def test_criar_e_buscar_por_ean(client, farmacia_a):
    criado = client.post("/api/v1/produtos", json=DIPIRONA, headers=farmacia_a["headers"])
    assert criado.status_code == 201, criado.text
    assert criado.json()["preco_venda"] == "8.90"

    achado = client.get("/api/v1/produtos/ean/7891234567890", headers=farmacia_a["headers"])
    assert achado.status_code == 200
    assert achado.json()["nome"] == "Dipirona 500mg"


def test_ean_duplicado_na_mesma_farmacia(client, farmacia_a):
    client.post("/api/v1/produtos", json=DIPIRONA, headers=farmacia_a["headers"])
    repetido = client.post("/api/v1/produtos", json=DIPIRONA, headers=farmacia_a["headers"])
    assert repetido.status_code == 409


def test_codigo_extra_encontra_produto(client, farmacia_a):
    produto = client.post("/api/v1/produtos", json=DIPIRONA, headers=farmacia_a["headers"]).json()
    resposta = client.post(
        f"/api/v1/produtos/{produto['id']}/codigos", json={"ean": "7890000000001"}, headers=farmacia_a["headers"]
    )
    assert resposta.status_code == 201, resposta.text

    achado = client.get("/api/v1/produtos/ean/7890000000001", headers=farmacia_a["headers"])
    assert achado.json()["id"] == produto["id"]

    # O código extra também não pode ser usado como EAN de outro produto.
    outro = client.post(
        "/api/v1/produtos", json={**DIPIRONA, "ean": "7890000000001"}, headers=farmacia_a["headers"]
    )
    assert outro.status_code == 409


def test_busca_por_nome_e_paginacao(client, farmacia_a):
    for i in range(3):
        client.post(
            "/api/v1/produtos",
            json={"nome": f"Vitamina C {i}", "preco_venda": "10"},
            headers=farmacia_a["headers"],
        )
    client.post("/api/v1/produtos", json=DIPIRONA, headers=farmacia_a["headers"])

    pagina = client.get(
        "/api/v1/produtos", params={"busca": "vitamina", "por_pagina": 2}, headers=farmacia_a["headers"]
    ).json()
    assert pagina["total"] == 3
    assert len(pagina["itens"]) == 2


def test_atualizar_e_desativar(client, farmacia_a):
    produto = client.post("/api/v1/produtos", json=DIPIRONA, headers=farmacia_a["headers"]).json()
    resposta = client.patch(
        f"/api/v1/produtos/{produto['id']}", json={"preco_venda": "9.50", "ativo": False}, headers=farmacia_a["headers"]
    )
    assert resposta.json()["preco_venda"] == "9.50"

    # Produto inativo não aparece no PDV.
    assert client.get("/api/v1/produtos/ean/7891234567890", headers=farmacia_a["headers"]).status_code == 404


def test_preco_negativo_recusado(client, farmacia_a):
    resposta = client.post("/api/v1/produtos", json={**DIPIRONA, "preco_venda": "-1"}, headers=farmacia_a["headers"])
    assert resposta.status_code == 422
