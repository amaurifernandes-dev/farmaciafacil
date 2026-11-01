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


def test_caixa_aberto_e_fechado_sem_internet(client, farmacia_a):
    h = farmacia_a["headers"]
    h["X-Terminal"] = _registrar_pdv(client, h)
    produto = _produto_com_estoque(client, farmacia_a, "Soro", "5.00", lotes=(("A", 90, 10),))
    caixa_id = str(uuid.uuid4())
    aberto_em = datetime.now(UTC) - timedelta(hours=3)
    abertura = {"id": caixa_id, "valor_abertura": "50.00", "offline_em": aberto_em.isoformat()}

    # Chega tudo na ordem em que aconteceu: abertura, vendas, fechamento.
    resposta = client.post(f"{API}/caixas/abrir", json=abertura, headers=h)
    assert resposta.status_code == 201, resposta.text
    caixa = resposta.json()
    assert (caixa["id"], caixa["aberto_offline"]) == (caixa_id, True)
    assert abs(datetime.fromisoformat(caixa["aberto_em"]) - aberto_em) < timedelta(seconds=1)
    # Reenviar a abertura devolve o mesmo caixa.
    assert client.post(f"{API}/caixas/abrir", json=abertura, headers=h).json()["id"] == caixa_id

    venda = _offline(produto, 2, "5.00", [{"forma": "dinheiro", "valor": "20.00"}], caixa_id,
                     datetime.now(UTC) - timedelta(hours=2))
    assert client.post(f"{API}/vendas", json=venda, headers=h).status_code == 201

    fechado_em = datetime.now(UTC) - timedelta(hours=1)
    fechamento = {"valor_fechamento_informado": "58.00", "offline_em": fechado_em.isoformat()}
    resposta = client.post(f"{API}/caixas/{caixa_id}/fechar", json=fechamento, headers=h)
    assert resposta.status_code == 200, resposta.text
    resumo = resposta.json()
    assert (resumo["caixa"]["status"], resumo["caixa"]["fechado_offline"]) == ("fechado", True)
    assert (resumo["dinheiro_esperado"], resumo["diferenca"]) == ("60.00", "-2.00")
    # Reenviar o fechamento não dá erro; fechar de novo de verdade, sim.
    assert client.post(f"{API}/caixas/{caixa_id}/fechar", json=fechamento, headers=h).status_code == 200
    outro = {"valor_fechamento_informado": "58.00", "offline_em": datetime.now(UTC).isoformat()}
    assert client.post(f"{API}/caixas/{caixa_id}/fechar", json=outro, headers=h).status_code == 409

    # Depois dele, o PDV abre outro caixa normalmente.
    assert client.post(f"{API}/caixas/abrir", json={"valor_abertura": "0"}, headers=h).status_code == 201


def test_regras_do_caixa_sem_internet(client, farmacia_a):
    h = farmacia_a["headers"]
    h["X-Terminal"] = _registrar_pdv(client, h)
    velho = {"id": str(uuid.uuid4()), "valor_abertura": "0",
             "offline_em": (datetime.now(UTC) - timedelta(days=8)).isoformat()}
    assert "7 dias" in client.post(f"{API}/caixas/abrir", json=velho, headers=h).json()["detail"]

    agora = datetime.now(UTC)
    caixa_id = str(uuid.uuid4())
    abertura = {"id": caixa_id, "valor_abertura": "0", "offline_em": (agora - timedelta(minutes=5)).isoformat()}
    assert client.post(f"{API}/caixas/abrir", json=abertura, headers=h).status_code == 201
    antes = {"valor_fechamento_informado": "0", "offline_em": (agora - timedelta(hours=1)).isoformat()}
    resposta = client.post(f"{API}/caixas/{caixa_id}/fechar", json=antes, headers=h)
    assert (resposta.status_code, "anterior" in resposta.json()["detail"]) == (400, True)
    # Mesmo código de caixa usado por outro PDV: recusa.
    h2 = {**h, "X-Terminal": _registrar_pdv(client, h, "PDV 02")}
    assert client.post(f"{API}/caixas/abrir", json=abertura, headers=h2).status_code == 409
