import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from tests.test_vendas import _abrir_caixa, _produto_com_estoque, _registrar_pdv, _saldo

API = "/api/v1"


def _offline(produto, quantidade, preco, pagamentos, caixa_id, quando=None, **extra):
    return {
        "chave_idempotencia": str(uuid.uuid4()),
        "itens": [{"produto_id": produto["id"], "quantidade": str(quantidade), "preco_unitario": preco}],
        "pagamentos": pagamentos,
        "offline_em": (quando or datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        "caixa_id": caixa_id,
        **extra,
    }


def test_catalogo_do_caixa(client, farmacia_a):
    h = farmacia_a["headers"]
    produto = _produto_com_estoque(client, farmacia_a, "Dipirona", "8.90", lotes=(("A", 30, 5), ("B", 90, 3)))
    client.post(f"{API}/produtos/{produto['id']}/codigos", json={"ean": "7891234567895"}, headers=h)
    inativo = _produto_com_estoque(client, farmacia_a, "Antigo", "1.00")
    client.patch(f"{API}/produtos/{inativo['id']}", json={"ativo": False}, headers=h)

    assert client.get(f"{API}/pdv/catalogo", headers=h).status_code == 400  # fora de um PDV
    h["X-Terminal"] = _registrar_pdv(client, h)
    catalogo = client.get(f"{API}/pdv/catalogo", headers=h).json()
    assert [p["nome"] for p in catalogo["produtos"]] == ["Dipirona"]
    item = catalogo["produtos"][0]
    assert (item["preco_venda"], Decimal(item["saldo"]), [c["ean"] for c in item["codigos"]]) == (
        "8.90", 8, ["7891234567895"])
    assert catalogo["desconto_maximo_caixa"]


def test_venda_feita_sem_internet_entra_depois(client, farmacia_a):
    h = farmacia_a["headers"]
    produto = _produto_com_estoque(client, farmacia_a, "Shampoo", "10.00", lotes=(("A", 90, 2),))
    caixa = _abrir_caixa(client, farmacia_a)
    # Enquanto o caixa estava offline, o preço mudou no sistema: vale o da cópia.
    client.patch(f"{API}/produtos/{produto['id']}", json={"preco_venda": "12.00"}, headers=h)

    quando = datetime.now(UTC) - timedelta(minutes=40)
    corpo = _offline(produto, 3, "10.00", [{"forma": "dinheiro", "valor": "50.00"}], caixa["id"], quando)
    resposta = client.post(f"{API}/vendas", json=corpo, headers=h)
    assert resposta.status_code == 201, resposta.text
    venda = resposta.json()
    assert (venda["offline"], venda["total"], venda["troco"]) == (True, "30.00", "20.00")
    assert abs(datetime.fromisoformat(venda["finalizada_em"]) - quando) < timedelta(seconds=1)
    # Vendeu 3 com 2 no sistema: o estoque zera e a diferença fica anotada.
    assert Decimal(venda["itens"][0]["sem_estoque"]) == 1
    assert _saldo(client, farmacia_a, produto["id"]) == {"A": 0}

    # Reenviar (a internet caiu no meio do envio) não duplica.
    de_novo = client.post(f"{API}/vendas", json=corpo, headers=h)
    assert (de_novo.status_code, de_novo.json()["numero"]) == (200, venda["numero"])

    resumo = client.get(f"{API}/caixas/atual", headers=h).json()
    assert (resumo["quantidade_vendas"], resumo["dinheiro_esperado"]) == (1, "130.00")  # 100 + 50 - 20


def test_regras_da_venda_offline(client, farmacia_a, farmacia_b):
    h = farmacia_a["headers"]
    produto = _produto_com_estoque(client, farmacia_a, "Sabonete", "5.00", lotes=(("A", 90, 10),))
    caixa = _abrir_caixa(client, farmacia_a)
    pix = [{"forma": "pix", "valor": "5.00"}]

    def enviar(corpo, esperado):
        resposta = client.post(f"{API}/vendas", json=corpo, headers=h)
        assert resposta.status_code == esperado, resposta.text
        return resposta.json()

    erro = enviar(_offline(produto, 1, "5.00", [{"forma": "prazo", "valor": "5.00"}], caixa["id"]), 400)
    assert "dinheiro, cartão ou Pix" in erro["detail"]
    velha = datetime.now(UTC) - timedelta(days=8)
    assert "7 dias" in enviar(_offline(produto, 1, "5.00", pix, caixa["id"], velha), 400)["detail"]
    futuro = datetime.now(UTC) + timedelta(hours=2)
    assert "relógio" in enviar(_offline(produto, 1, "5.00", pix, caixa["id"], futuro), 400)["detail"]
    enviar(_offline(produto, 1, "5.00", pix, str(uuid.uuid4())), 404)
    enviar(_offline(produto, 1, "5.00", pix, caixa["id"], pontos_resgatados=10), 400)

    # Outro PDV não envia vendas deste caixa.
    outro = dict(h, **{"X-Terminal": _registrar_pdv(client, h, "PDV 02")})
    resposta = client.post(f"{API}/vendas", json=_offline(produto, 1, "5.00", pix, caixa["id"]), headers=outro)
    assert resposta.status_code == 400 and "outro PDV" in resposta.json()["detail"]

    # Produto desativado depois da venda: a venda entra mesmo assim.
    client.patch(f"{API}/produtos/{produto['id']}", json={"ativo": False}, headers=h)
    assert enviar(_offline(produto, 1, "5.00", pix, caixa["id"]), 201)["offline"] is True

    # Outra farmácia não enxerga o caixa.
    hb = farmacia_b["headers"]
    hb["X-Terminal"] = _registrar_pdv(client, hb)
    resposta = client.post(f"{API}/vendas", json=_offline(produto, 1, "5.00", pix, caixa["id"]), headers=hb)
    assert resposta.status_code == 404
