import uuid

from tests.test_promocoes_relatorios import _produto
from tests.test_vendas import _abrir_caixa

API = "/api/v1"


def _atendente(client, farmacia) -> tuple[dict, str]:
    corpo = {"nome": "Bruna Balconista", "email": "bruna@farmacia.com", "papel": "atendente", "senha": "senha-forte"}
    resposta = client.post(f"{API}/usuarios", json=corpo, headers=farmacia["headers"])
    assert resposta.status_code == 201, resposta.text
    token = client.post(f"{API}/auth/login", json={"email": corpo["email"], "senha": corpo["senha"]}).json()
    return {"Authorization": f"Bearer {token['access_token']}"}, resposta.json()["id"]


def _vender(client, farmacia, itens, valor, **extra):
    corpo = {
        "chave_idempotencia": str(uuid.uuid4()),
        "itens": [{"produto_id": p["id"], "quantidade": str(q)} for p, q in itens],
        "pagamentos": [{"forma": "dinheiro", "valor": valor}],
        **extra,
    }
    resposta = client.post(f"{API}/vendas", json=corpo, headers=farmacia["headers"])
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _por_nome(relatorio):
    return {v["nome"]: v for v in relatorio["vendedores"]}


def test_comissao_por_vendedor_e_por_produto(client, farmacia_a):
    h = farmacia_a["headers"]
    eu = client.get(f"{API}/auth/eu", headers=h).json()
    client.patch(f"{API}/configuracoes", json={"comissao_padrao": "2"}, headers=h)
    generico = _produto(client, farmacia_a, "Losartana genérico", "100.00")
    client.patch(f"{API}/produtos/{generico['id']}", json={"comissao": "5"}, headers=h)
    shampoo = _produto(client, farmacia_a, "Shampoo", "50.00")
    bruna, bruna_id = _atendente(client, farmacia_a)
    _abrir_caixa(client, farmacia_a)

    # A balconista faz a pré-venda; o caixa recebe. A venda é dela.
    pre = client.post(f"{API}/pre-vendas", json={"itens": [{"produto_id": generico["id"], "quantidade": "1"}]},
                      headers=bruna)
    assert pre.status_code == 201, pre.text
    _vender(client, farmacia_a, [(generico, 1)], "100.00", pre_venda_id=pre.json()["id"])
    # O caixa vende direto, com desconto de 10: a comissão é sobre os 40 que o cliente pagou.
    _vender(client, farmacia_a, [(shampoo, 1)], "40.00", desconto="10.00")
    cancelada = _vender(client, farmacia_a, [(shampoo, 2)], "100.00")
    client.post(f"{API}/vendas/{cancelada['id']}/cancelar", json={"motivo": "Desistiu"}, headers=h)

    relatorio = client.get(f"{API}/comissoes", headers=h).json()
    vendedores = _por_nome(relatorio)
    assert (vendedores["Bruna Balconista"]["vendido"], vendedores["Bruna Balconista"]["comissao"]) == ("100.00", "5.00")
    caixa = next(v for v in relatorio["vendedores"] if v["usuario_id"] == eu["usuario_id"])
    assert (caixa["vendas"], caixa["vendido"], caixa["comissao"]) == (1, "40.00", "0.80")
    assert (relatorio["total_vendido"], relatorio["total_comissao"]) == ("140.00", "5.80")

    # Mudar a regra depois não muda o que já foi vendido.
    client.patch(f"{API}/produtos/{generico['id']}", json={"comissao": "10"}, headers=h)
    assert _por_nome(client.get(f"{API}/comissoes", headers=h).json())["Bruna Balconista"]["comissao"] == "5.00"

    # Quem não recebe comissão aparece com zero.
    client.patch(f"{API}/usuarios/{eu['usuario_id']}", json={"recebe_comissao": False}, headers=h)
    caixa = next(v for v in client.get(f"{API}/comissoes", headers=h).json()["vendedores"]
                 if v["usuario_id"] == eu["usuario_id"])
    assert (caixa["vendido"], caixa["comissao"], caixa["recebe_comissao"]) == ("40.00", "0.00", False)

    # Detalhe do vendedor.
    detalhe = client.get(f"{API}/comissoes/vendedor/{bruna_id}", headers=h).json()
    assert [(v["vendido"], v["comissao"], v["pre_venda"]) for v in detalhe["vendas"]] == [("100.00", "5.00", True)]
    assert [(p["descricao"], p["percentual"]) for p in detalhe["produtos"]] == [("Losartana genérico", "5.00")]

    # A balconista vê só as próprias vendas.
    assert client.get(f"{API}/comissoes", headers=bruna).status_code == 403
    assert client.get(f"{API}/comissoes/vendedor/{eu['usuario_id']}", headers=bruna).status_code == 403
    minhas = client.get(f"{API}/comissoes/minhas", headers=bruna).json()
    assert (minhas["vendedor"]["nome"], minhas["vendedor"]["comissao"]) == ("Bruna Balconista", "5.00")

    planilha = client.get(f"{API}/comissoes/planilha", headers=h)
    linhas = planilha.content.decode("utf-8-sig").splitlines()
    assert linhas[2].startswith("Bruna Balconista;1;100,00") and linhas[-1].endswith(";5,00")  # o caixa deixou de receber

    # Período inválido.
    assert client.get(f"{API}/comissoes", params={"inicio": "2026-10-10", "fim": "2026-10-01"},
                      headers=h).status_code == 400
