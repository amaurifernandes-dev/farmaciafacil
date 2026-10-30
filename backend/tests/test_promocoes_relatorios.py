import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import text

from app.shared.datas import hoje
from tests.test_financeiro import _cliente
from tests.test_vendas import _abrir_caixa

API = "/api/v1"


def _produto(client, farmacia, nome, preco, custo=None, ean=None, quantidade=50):
    corpo = {"nome": nome, "preco_venda": preco}
    if ean:
        corpo["ean"] = ean
    produto = client.post(f"{API}/produtos", json=corpo, headers=farmacia["headers"])
    assert produto.status_code == 201, produto.text
    produto = produto.json()
    item = {"produto_id": produto["id"], "numero_lote": "L1", "quantidade": str(quantidade),
            "validade": (hoje() + timedelta(days=300)).isoformat()}
    if custo:
        item["custo_unitario"] = custo
    resposta = client.post(f"{API}/estoque/entradas", json={"itens": [item]}, headers=farmacia["headers"])
    assert resposta.status_code == 201, resposta.text
    return produto


def _promocao(client, farmacia, produtos, esperado=201, **dados):
    corpo = {"nome": "Promoção", "tipo": "percentual", "percentual": "20", "inicio": hoje().isoformat(),
             "produto_ids": [p["id"] for p in produtos], **dados}
    resposta = client.post(f"{API}/promocoes", json=corpo, headers=farmacia["headers"])
    assert resposta.status_code == esperado, resposta.text
    return resposta.json()


def _vender(client, farmacia, itens, pagamentos, **extra):
    corpo = {
        "chave_idempotencia": str(uuid.uuid4()),
        "itens": [{"produto_id": p["id"], "quantidade": str(q)} for p, q in itens],
        "pagamentos": pagamentos,
        **extra,
    }
    resposta = client.post(f"{API}/vendas", json=corpo, headers=farmacia["headers"])
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def test_promocao_percentual_aplicada_sozinha(client, farmacia_a):
    protetor = _produto(client, farmacia_a, "Protetor", "50.00", ean="7890000000031")
    promocao = _promocao(client, farmacia_a, [protetor], nome="Verão")
    assert (promocao["situacao"], promocao["resumo"]) == ("vigente", "20% de desconto")
    assert Decimal(promocao["produtos"][0]["preco_promocional"]) == 40
    _abrir_caixa(client, farmacia_a)

    # O PDV recebe a promoção junto com o produto para mostrar o preço certo.
    pdv = client.get(f"{API}/produtos/ean/7890000000031", headers=farmacia_a["headers"]).json()
    assert [p["resumo"] for p in pdv["promocoes"]] == ["20% de desconto"]

    venda = _vender(client, farmacia_a, [(protetor, 2)], [{"forma": "pix", "valor": "80.00"}])
    item = venda["itens"][0]
    assert (Decimal(item["desconto_promocao"]), item["promocao_id"]) == (20, promocao["id"])
    assert (Decimal(venda["total"]), Decimal(venda["desconto"])) == (80, 20)

    resultado = client.get(f"{API}/promocoes/{promocao['id']}", headers=farmacia_a["headers"]).json()["resultado"]
    assert (resultado["vendas"], Decimal(resultado["unidades"]), Decimal(resultado["desconto"])) == (1, 2, 20)


def test_leve_pague_e_preco_fixo(client, farmacia_a):
    fralda = _produto(client, farmacia_a, "Fralda", "10.00")
    sabonete = _produto(client, farmacia_a, "Sabonete", "4.00")
    _promocao(client, farmacia_a, [fralda], tipo="leve_pague", leve=3, pague=2, percentual=None)
    _promocao(client, farmacia_a, [sabonete], tipo="preco_fixo", preco="4.00", esperado=400)  # não é desconto
    _promocao(client, farmacia_a, [sabonete], tipo="preco_fixo", preco="2.99")
    _promocao(client, farmacia_a, [fralda], tipo="leve_pague", leve=2, pague=2, esperado=422)
    _abrir_caixa(client, farmacia_a)

    venda = _vender(client, farmacia_a, [(fralda, 7), (sabonete, 2)], [{"forma": "dinheiro", "valor": "56.00"}])
    descontos = [Decimal(i["desconto_promocao"]) for i in venda["itens"]]
    assert descontos == [Decimal("20.00"), Decimal("2.02")]  # 2 fraldas grátis; sabonete por 2,99
    assert Decimal(venda["total"]) == Decimal("55.98")


def test_vale_a_melhor_e_so_clientes(client, farmacia_a):
    produto = _produto(client, farmacia_a, "Vitamina C", "30.00")
    _promocao(client, farmacia_a, [produto], percentual="10")
    clube = _promocao(client, farmacia_a, [produto], percentual="25", so_clientes=True, nome="Clube")
    maria = _cliente(client, farmacia_a, nome="Maria")
    _abrir_caixa(client, farmacia_a)

    sem_cliente = _vender(client, farmacia_a, [(produto, 1)], [{"forma": "pix", "valor": "27.00"}])
    assert Decimal(sem_cliente["total"]) == 27
    com_cliente = _vender(client, farmacia_a, [(produto, 1)], [{"forma": "pix", "valor": "22.50"}],
                          cliente_id=maria["id"])
    assert (Decimal(com_cliente["total"]), com_cliente["itens"][0]["promocao_id"]) == (Decimal("22.50"), clube["id"])


def test_periodo_e_encerramento(client, farmacia_a):
    produto = _produto(client, farmacia_a, "Shampoo", "20.00")
    agendada = _promocao(client, farmacia_a, [produto], inicio=(hoje() + timedelta(days=3)).isoformat())
    assert agendada["situacao"] == "agendada"
    _promocao(client, farmacia_a, [produto], inicio=(hoje() - timedelta(days=10)).isoformat(),
              fim=(hoje() - timedelta(days=1)).isoformat())
    vigente = _promocao(client, farmacia_a, [produto], percentual="5")
    _promocao(client, farmacia_a, [produto], fim=(hoje() - timedelta(days=1)).isoformat(), esperado=422)
    _abrir_caixa(client, farmacia_a)

    venda = _vender(client, farmacia_a, [(produto, 1)], [{"forma": "pix", "valor": "19.00"}])
    assert Decimal(venda["total"]) == 19  # só a vigente vale

    encerrada = client.post(f"{API}/promocoes/{vigente['id']}/encerrar", headers=farmacia_a["headers"]).json()
    assert encerrada["situacao"] in ("pausada", "encerrada")
    venda = _vender(client, farmacia_a, [(produto, 1)], [{"forma": "pix", "valor": "20.00"}])
    assert Decimal(venda["total"]) == 20

    def nomes(situacao):
        return len(client.get(f"{API}/promocoes", params={"situacao": situacao}, headers=farmacia_a["headers"]).json())

    assert (nomes("vigente"), nomes("agendada"), nomes("encerrada")) == (0, 1, 2)


def test_editar_promocao(client, farmacia_a):
    a = _produto(client, farmacia_a, "A", "10.00")
    b = _produto(client, farmacia_a, "B", "10.00")
    promocao = _promocao(client, farmacia_a, [a])
    corpo = {"nome": "Nova", "tipo": "percentual", "percentual": "15", "inicio": hoje().isoformat(),
             "produto_ids": [a["id"], b["id"]], "ativa": True}
    editada = client.put(f"{API}/promocoes/{promocao['id']}", json=corpo, headers=farmacia_a["headers"])
    assert editada.status_code == 200, editada.text
    assert [p["nome"] for p in editada.json()["produtos"]] == ["A", "B"]
    corpo["produto_ids"] = [b["id"]]
    editada = client.put(f"{API}/promocoes/{promocao['id']}", json=corpo, headers=farmacia_a["headers"]).json()
    assert [p["nome"] for p in editada["produtos"]] == ["B"]


def test_relatorio_de_vendas_com_lucro(client, farmacia_a):
    dipirona = _produto(client, farmacia_a, "Dipirona", "10.00", custo="4.00")
    protetor = _produto(client, farmacia_a, "Protetor", "50.00", custo="30.00")
    sem_custo = _produto(client, farmacia_a, "Brinde", "5.00")
    _promocao(client, farmacia_a, [protetor], percentual="10")
    _abrir_caixa(client, farmacia_a)

    _vender(client, farmacia_a, [(dipirona, 3)], [{"forma": "dinheiro", "valor": "50.00"}])  # troco 20
    _vender(client, farmacia_a, [(protetor, 1), (dipirona, 1)], [{"forma": "pix", "valor": "55.00"}])
    cancelada = _vender(client, farmacia_a, [(dipirona, 1)], [{"forma": "pix", "valor": "10.00"}])
    client.post(f"{API}/vendas/{cancelada['id']}/cancelar", json={"motivo": "erro"}, headers=farmacia_a["headers"])
    _vender(client, farmacia_a, [(sem_custo, 1)], [{"forma": "pix", "valor": "5.00"}])

    relatorio = client.get(f"{API}/relatorios/vendas", headers=farmacia_a["headers"])
    assert relatorio.status_code == 200, relatorio.text
    relatorio = relatorio.json()
    resumo = relatorio["resumo"]
    assert resumo["quantidade"] == 3
    assert Decimal(resumo["faturamento"]) == 90  # 30 + 55 + 5
    assert Decimal(resumo["descontos_promocao"]) == 5
    assert Decimal(resumo["custo"]) == 46  # 4*4 + 30
    assert Decimal(resumo["lucro_bruto"]) == 44
    assert resumo["itens_sem_custo"] == 1
    assert (resumo["canceladas"], Decimal(resumo["valor_cancelado"])) == (1, 10)
    assert relatorio["anterior"]["quantidade"] == 0
    assert len(relatorio["por_dia"]) == 30 and relatorio["por_dia"][-1]["quantidade"] == 3
    formas = {f["forma"]: Decimal(f["valor"]) for f in relatorio["por_forma"]}
    assert formas == {"dinheiro": 30, "pix": 60}
    assert relatorio["por_operador"][0]["quantidade"] == 3

    produtos = client.get(f"{API}/relatorios/produtos", headers=farmacia_a["headers"]).json()
    linhas = {p["nome"]: p for p in produtos["produtos"]}
    assert [p["nome"] for p in produtos["produtos"]] == ["Protetor", "Dipirona", "Brinde"]
    assert (Decimal(linhas["Protetor"]["lucro"]), Decimal(linhas["Protetor"]["margem"])) == (15, Decimal("33.3"))
    assert linhas["Brinde"]["lucro"] is None
    assert [p["curva"] for p in produtos["produtos"]] == ["A", "A", "B"]  # o Brinde começa em 85 de 90 (94%)

    assert client.get(f"{API}/relatorios/vendas", params={"inicio": "2026-02-01", "fim": "2026-01-01"},
                      headers=farmacia_a["headers"]).status_code == 400


def test_produtos_parados(client, farmacia_a, engine_dono):
    vende = _produto(client, farmacia_a, "Vende bem", "10.00", custo="5.00")
    parado = _produto(client, farmacia_a, "Encalhado", "20.00", custo="12.00", quantidade=10)
    antigo = _produto(client, farmacia_a, "Vendeu faz tempo", "8.00", custo="3.00", quantidade=4)
    _abrir_caixa(client, farmacia_a)
    _vender(client, farmacia_a, [(vende, 1)], [{"forma": "pix", "valor": "10.00"}])
    venda = _vender(client, farmacia_a, [(antigo, 1)], [{"forma": "pix", "valor": "8.00"}])
    with engine_dono.begin() as conexao:
        conexao.execute(text("UPDATE vendas SET finalizada_em = now() - interval '100 days' WHERE id = :id"),
                        {"id": venda["id"]})

    relatorio = client.get(f"{API}/relatorios/parados", headers=farmacia_a["headers"]).json()
    linhas = {p["nome"]: p for p in relatorio["produtos"]}
    assert set(linhas) == {"Encalhado", "Vendeu faz tempo"}
    assert (Decimal(linhas["Encalhado"]["valor_parado"]), linhas["Encalhado"]["dias_parado"]) == (120, None)
    assert linhas["Vendeu faz tempo"]["dias_parado"] >= 99
    assert Decimal(relatorio["valor_total"]) == 129  # 120 + 3 * 3
    assert relatorio["produtos"][0]["nome"] == "Encalhado"

    em_120_dias = client.get(f"{API}/relatorios/parados", params={"dias": 120}, headers=farmacia_a["headers"]).json()
    assert [p["nome"] for p in em_120_dias["produtos"]] == ["Encalhado"]


def test_promocoes_isoladas_e_so_gerente_cadastra(client, farmacia_a, farmacia_b):
    produto = _produto(client, farmacia_a, "A", "10.00")
    promocao = _promocao(client, farmacia_a, [produto])
    assert client.get(f"{API}/promocoes/{promocao['id']}", headers=farmacia_b["headers"]).status_code == 404
    assert client.get(f"{API}/promocoes", headers=farmacia_b["headers"]).json() == []
    # Produto de outra farmácia não entra na promoção.
    _promocao(client, farmacia_b, [produto], esperado=404)
