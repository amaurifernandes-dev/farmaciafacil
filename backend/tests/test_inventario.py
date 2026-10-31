from datetime import timedelta

from app.shared.datas import hoje
from tests.test_comissoes import _atendente, _vender
from tests.test_controlados import _controlado
from tests.test_promocoes_relatorios import _produto
from tests.test_vendas import _abrir_caixa

API = "/api/v1"


def _abrir(client, farmacia, esperado=201, **corpo):
    resposta = client.post(f"{API}/inventarios", json=corpo, headers=farmacia["headers"])
    assert resposta.status_code == esperado, resposta.text
    return resposta.json()


def _contar(client, headers, inventario, esperado=200, **corpo):
    resposta = client.post(f"{API}/inventarios/{inventario['id']}/contar", json=corpo, headers=headers)
    assert resposta.status_code == esperado, resposta.text
    return resposta.json()


def _saldo_por_lote(client, farmacia, produto):
    lotes = client.get(f"{API}/estoque/lotes", params={"produto_id": produto["id"]}, headers=farmacia["headers"]).json()
    return {lote["numero_lote"]: lote["quantidade"] for lote in lotes}


def _entrada(client, farmacia, produto, lote, quantidade, dias):
    item = {"produto_id": produto["id"], "numero_lote": lote, "quantidade": str(quantidade),
            "validade": (hoje() + timedelta(days=dias)).isoformat()}
    assert client.post(f"{API}/estoque/entradas", json={"itens": [item]},
                       headers=farmacia["headers"]).status_code == 201


def test_inventario_parcial_conta_bipando_e_ajusta(client, farmacia_a):
    h = farmacia_a["headers"]
    dipirona = _produto(client, farmacia_a, "Dipirona", "10.00", custo="4.00", ean="7891234567895", quantidade=10)
    _entrada(client, farmacia_a, dipirona, "L2", 5, 600)  # L1 vence antes, L2 depois
    shampoo = _produto(client, farmacia_a, "Shampoo", "20.00", custo="8.00", quantidade=3)
    vitamina = _produto(client, farmacia_a, "Vitamina", "30.00", quantidade=7)  # não entra: parcial
    bruna, _ = _atendente(client, farmacia_a)
    _abrir_caixa(client, farmacia_a)

    # A balconista não abre inventário, mas ajuda a contar.
    assert client.post(f"{API}/inventarios", json={}, headers=bruna).status_code == 403
    inventario = _abrir(client, farmacia_a, descricao="Corredor 1")
    _abrir(client, farmacia_a, 409)  # uma contagem aberta por loja

    # Bipando: cada leitura soma um. Quem conta não vê o saldo do sistema.
    for _ in range(3):
        item = _contar(client, bruna, inventario, codigo="7891234567895")
    assert (item["quantidade"], item["saldo_sistema"], item["diferenca"]) == ("3.000", None, None)
    _contar(client, bruna, inventario, codigo="7891234567895", quantidade="9")  # mais uma caixa com 9
    _contar(client, bruna, inventario, codigo="7891234567895", quantidade="-1")  # bipou a mais
    _contar(client, h, inventario, produto_id=shampoo["id"], quantidade="5", modo="definir")
    _contar(client, bruna, inventario, 404, codigo="0000000000000")

    # Vendeu 2 dipironas durante a contagem: não vira diferença.
    _vender(client, farmacia_a, [(dipirona, 2)], "20.00")

    detalhe = client.get(f"{API}/inventarios/{inventario['id']}", headers=h).json()
    itens = {i["nome"]: i for i in detalhe["itens"]}
    assert (itens["Dipirona"]["quantidade"], itens["Dipirona"]["saldo_sistema"], itens["Dipirona"]["diferenca"]) == (
        "11.000", "15.000", "-4.000")
    assert (itens["Shampoo"]["diferenca"], itens["Shampoo"]["valor_diferenca"]) == ("2.000", "16.00")
    resumo = detalhe["resumo"]
    assert (resumo["produtos_contados"], resumo["com_diferenca"], resumo["valor_falta"], resumo["valor_sobra"]) == (
        2, 2, "16.00", "16.00")
    assert detalhe["nao_contados"] is None
    visto_pela_bruna = client.get(f"{API}/inventarios/{inventario['id']}", headers=bruna).json()
    assert (visto_pela_bruna["ve_saldo"], visto_pela_bruna["resumo"]["valor_falta"]) == (False, None)
    assert client.post(f"{API}/inventarios/{inventario['id']}/finalizar", headers=bruna).status_code == 403

    resposta = client.post(f"{API}/inventarios/{inventario['id']}/finalizar", headers=h)
    assert resposta.status_code == 200, resposta.text
    fim = resposta.json()
    assert (fim["status"], fim["produtos_ajustados"], fim["valor_falta"], fim["valor_sobra"]) == (
        "finalizado", 2, "16.00", "16.00")
    # Tinha 13 depois da venda (L1 8, L2 5); faltaram 4, que saem do lote que vence primeiro.
    assert _saldo_por_lote(client, farmacia_a, dipirona) == {"L1": "4.000", "L2": "5.000"}
    assert _saldo_por_lote(client, farmacia_a, shampoo) == {"L1": "5.000"}
    assert _saldo_por_lote(client, farmacia_a, vitamina) == {"L1": "7.000"}
    movimentos = client.get(f"{API}/estoque/movimentos", params={"produto_id": shampoo["id"]}, headers=h).json()
    ajuste = next(m for m in movimentos if m["tipo"] == "ajuste")
    assert (ajuste["quantidade"], ajuste["motivo"], ajuste["referencia_tipo"]) == ("2.000", "Inventário: Corredor 1",
                                                                                 "inventario")

    # Encerrado não muda mais.
    _contar(client, h, inventario, 400, produto_id=shampoo["id"])
    assert client.post(f"{API}/inventarios/{inventario['id']}/cancelar", headers=h).status_code == 400
    assert [i["status"] for i in client.get(f"{API}/inventarios", headers=h).json()] == ["finalizado"]


def test_inventario_geral_zera_o_que_ninguem_contou(client, farmacia_a):
    h = farmacia_a["headers"]
    dipirona = _produto(client, farmacia_a, "Dipirona", "10.00", custo="4.00", quantidade=10)
    sumiu = _produto(client, farmacia_a, "Protetor", "50.00", custo="25.00", quantidade=2)
    rivotril = _controlado(client, farmacia_a, "Rivotril", "B1", "7896004700304")

    inventario = _abrir(client, farmacia_a, escopo="geral")
    _contar(client, h, inventario, produto_id=dipirona["id"], quantidade="10", modo="definir")
    resposta = _contar(client, h, inventario, 400, produto_id=rivotril["id"])
    assert "controlado" in resposta["detail"]

    detalhe = client.get(f"{API}/inventarios/{inventario['id']}", headers=h).json()
    assert [(i["nome"], i["diferenca"]) for i in detalhe["nao_contados"]] == [("Protetor", "-2.000")]
    assert (detalhe["resumo"]["nao_contados"], detalhe["resumo"]["valor_falta"]) == (1, "50.00")

    # Apagar uma contagem devolve o produto para "não contado".
    assert client.delete(f"{API}/inventarios/{inventario['id']}/itens/{dipirona['id']}", headers=h).status_code == 204
    assert client.get(f"{API}/inventarios/{inventario['id']}", headers=h).json()["resumo"]["nao_contados"] == 2
    _contar(client, h, inventario, produto_id=dipirona["id"], quantidade="10", modo="definir")

    fim = client.post(f"{API}/inventarios/{inventario['id']}/finalizar", headers=h).json()
    assert (fim["produtos_ajustados"], fim["valor_falta"]) == (1, "50.00")
    assert _saldo_por_lote(client, farmacia_a, sumiu) == {}  # lote zerado sai da lista
    assert _saldo_por_lote(client, farmacia_a, rivotril) == {"CTRL1": "10.000"}  # controlado não mexe

    planilha = client.get(f"{API}/inventarios/{inventario['id']}/planilha", headers=h)
    linhas = planilha.content.decode("utf-8-sig").splitlines()
    assert linhas[1].startswith("Produto;") and any(linha.startswith("Protetor (não contado);") for linha in linhas)


def test_sobra_de_produto_sem_lote_e_cancelar(client, farmacia_a, farmacia_b):
    h = farmacia_a["headers"]
    novo = client.post(f"{API}/produtos", json={"nome": "Escova", "preco_venda": "9.00", "controla_lote": False},
                       headers=h).json()
    inventario = _abrir(client, farmacia_a)
    _contar(client, h, inventario, produto_id=novo["id"], quantidade="4", modo="definir")
    client.post(f"{API}/inventarios/{inventario['id']}/finalizar", headers=h)
    assert _saldo_por_lote(client, farmacia_a, novo) == {"SEM-LOTE": "4.000"}

    vazio = _abrir(client, farmacia_a)
    assert client.post(f"{API}/inventarios/{vazio['id']}/finalizar", headers=h).status_code == 400
    assert client.post(f"{API}/inventarios/{vazio['id']}/cancelar", headers=h).json()["status"] == "cancelado"
    _abrir(client, farmacia_a)  # cancelado libera a loja

    # Outra farmácia não vê nem conta.
    assert client.get(f"{API}/inventarios/{vazio['id']}", headers=farmacia_b["headers"]).status_code == 404
    _contar(client, farmacia_b["headers"], vazio, 404, produto_id=novo["id"])
