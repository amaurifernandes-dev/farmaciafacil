from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import gerar_hash_senha, ler_token
from app.modules.auth.models import Usuario
from app.modules.estoque import service as estoque
from app.modules.produtos.models import Produto
from app.shared.datas import hoje

API = "/api/v1"


def _produto(client, farmacia, **campos) -> dict:
    dados = {"nome": "Dipirona 500mg", "preco_venda": "8.90", "estoque_minimo": "5", **campos}
    resposta = client.post(f"{API}/produtos", json=dados, headers=farmacia["headers"])
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _entrada(client, farmacia, *itens) -> list:
    resposta = client.post(f"{API}/estoque/entradas", json={"itens": list(itens)}, headers=farmacia["headers"])
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _item(produto, lote, dias, quantidade, custo="4.10") -> dict:
    return {
        "produto_id": produto["id"],
        "numero_lote": lote,
        "validade": (hoje() + timedelta(days=dias)).isoformat(),
        "quantidade": str(quantidade),
        "custo_unitario": custo,
    }


def test_entrada_cria_lote_e_soma_no_mesmo_lote(client, farmacia_a):
    produto = _produto(client, farmacia_a)
    _entrada(client, farmacia_a, _item(produto, "abc1", 200, 10))
    _entrada(client, farmacia_a, _item(produto, "ABC1", 200, 5))

    lotes = client.get(f"{API}/estoque/lotes", params={"produto_id": produto["id"]}, headers=farmacia_a["headers"]).json()
    assert len(lotes) == 1
    assert lotes[0]["numero_lote"] == "ABC1"
    assert Decimal(lotes[0]["quantidade"]) == 15

    # O custo da última entrada vira o custo do produto.
    atualizado = client.get(f"{API}/produtos/{produto['id']}", headers=farmacia_a["headers"]).json()
    assert atualizado["preco_custo"] == "4.10"


def test_entrada_exige_lote_e_validade(client, farmacia_a):
    produto = _produto(client, farmacia_a)
    resposta = client.post(
        f"{API}/estoque/entradas",
        json={"itens": [{"produto_id": produto["id"], "quantidade": "3"}]},
        headers=farmacia_a["headers"],
    )
    assert resposta.status_code == 400


def test_entrada_recusa_lote_vencido(client, farmacia_a):
    produto = _produto(client, farmacia_a)
    resposta = client.post(
        f"{API}/estoque/entradas", json={"itens": [_item(produto, "V1", -1, 3)]}, headers=farmacia_a["headers"]
    )
    assert resposta.status_code == 400


def test_mesmo_lote_com_validade_diferente(client, farmacia_a):
    produto = _produto(client, farmacia_a)
    _entrada(client, farmacia_a, _item(produto, "L1", 100, 3))
    resposta = client.post(
        f"{API}/estoque/entradas", json={"itens": [_item(produto, "L1", 150, 3)]}, headers=farmacia_a["headers"]
    )
    assert resposta.status_code == 400


def test_produto_sem_controle_de_lote(client, farmacia_a):
    produto = _produto(client, farmacia_a, nome="Sabonete", controla_lote=False, tipo="perfumaria")
    _entrada(client, farmacia_a, {"produto_id": produto["id"], "quantidade": "12"})
    _entrada(client, farmacia_a, {"produto_id": produto["id"], "quantidade": "3"})

    lotes = client.get(f"{API}/estoque/lotes", params={"produto_id": produto["id"]}, headers=farmacia_a["headers"]).json()
    assert [(l["numero_lote"], l["validade"], Decimal(l["quantidade"])) for l in lotes] == [("SEM-LOTE", None, 15)]


def test_pdv_mostra_saldo_vendavel(client, farmacia_a):
    produto = _produto(client, farmacia_a, ean="7891234567890")
    _entrada(client, farmacia_a, _item(produto, "A", 30, 4), _item(produto, "B", 300, 6))

    resposta = client.get(f"{API}/produtos/ean/7891234567890", headers=farmacia_a["headers"]).json()
    assert Decimal(resposta["saldo"]) == 10


def test_ajuste_por_contagem_e_perda(client, farmacia_a):
    produto = _produto(client, farmacia_a)
    lote_id = _entrada(client, farmacia_a, _item(produto, "A", 100, 10))[0]["lote_id"]

    ajuste = client.post(
        f"{API}/estoque/ajustes",
        json={"lote_id": lote_id, "nova_quantidade": "8", "motivo": "Inventário mensal"},
        headers=farmacia_a["headers"],
    )
    assert ajuste.status_code == 201, ajuste.text
    assert Decimal(ajuste.json()["quantidade"]) == -2

    perda = client.post(
        f"{API}/estoque/perdas",
        json={"lote_id": lote_id, "quantidade": "1", "motivo": "Caixa amassada"},
        headers=farmacia_a["headers"],
    )
    assert perda.status_code == 201

    demais = client.post(
        f"{API}/estoque/perdas",
        json={"lote_id": lote_id, "quantidade": "50", "motivo": "Erro"},
        headers=farmacia_a["headers"],
    )
    assert demais.status_code == 409

    movimentos = client.get(
        f"{API}/estoque/movimentos", params={"produto_id": produto["id"]}, headers=farmacia_a["headers"]
    ).json()
    assert [m["tipo"] for m in movimentos] == ["perda", "ajuste", "entrada"]
    lote = client.get(f"{API}/estoque/lotes", params={"produto_id": produto["id"]}, headers=farmacia_a["headers"]).json()[0]
    assert Decimal(lote["quantidade"]) == 7


def test_alertas(client, farmacia_a):
    pouco = _produto(client, farmacia_a, nome="Amoxicilina", estoque_minimo="10")
    _entrada(client, farmacia_a, _item(pouco, "P1", 20, 3))
    _produto(client, farmacia_a, nome="Sem estoque nenhum", estoque_minimo="2")
    farto = _produto(client, farmacia_a, nome="Paracetamol", estoque_minimo="1")
    _entrada(client, farmacia_a, _item(farto, "F1", 400, 50))

    alertas = client.get(f"{API}/estoque/alertas", params={"dias": 30}, headers=farmacia_a["headers"]).json()
    assert [l["numero_lote"] for l in alertas["vencendo"]] == ["P1"]
    assert alertas["vencendo"][0]["dias_para_vencer"] == 20
    assert [p["nome"] for p in alertas["abaixo_do_minimo"]] == ["Amoxicilina", "Sem estoque nenhum"]



def _usuario_id(farmacia):
    return ler_token(farmacia["headers"]["Authorization"].split()[1]).usuario_id


def test_baixa_fefo_tira_primeiro_do_que_vence_antes(client, farmacia_a):
    produto = _produto(client, farmacia_a)
    _entrada(
        client,
        farmacia_a,
        _item(produto, "TARDE", 300, 5),
        _item(produto, "CEDO", 30, 3),
        _item(produto, "MEIO", 100, 4),
    )

    with SessionLocal(info={"farmacia_id": farmacia_a["id"]}) as db:
        p = db.get(Produto, produto["id"])
        movimentos = estoque.baixar_fefo(
            db, p, Decimal(5), _usuario_id(farmacia_a), estoque.Referencia("teste")
        )
        db.commit()
        assert [(m.lote.numero_lote, m.quantidade) for m in movimentos] == [("CEDO", -3), ("MEIO", -2)]

        with pytest.raises(estoque.EstoqueInsuficiente):
            estoque.baixar_fefo(db, p, Decimal(100), _usuario_id(farmacia_a), estoque.Referencia("teste"))


def test_caixa_nao_pode_dar_entrada(client, engine_dono, farmacia_a):
    with Session(engine_dono) as db:
        db.add(
            Usuario(
                farmacia_id=farmacia_a["id"],
                nome="Caixa",
                email="caixa@farmacia.com",
                senha_hash=gerar_hash_senha("senha-forte"),
                papel="caixa",
            )
        )
        db.commit()
    token = client.post(f"{API}/auth/login", json={"email": "caixa@farmacia.com", "senha": "senha-forte"}).json()
    headers = {"Authorization": f"Bearer {token['access_token']}"}

    produto = _produto(client, farmacia_a)
    resposta = client.post(f"{API}/estoque/entradas", json={"itens": [_item(produto, "X", 30, 1)]}, headers=headers)
    assert resposta.status_code == 403
    # Mas consegue consultar.
    assert client.get(f"{API}/estoque/lotes", headers=headers).status_code == 200


def test_isolamento_do_estoque(client, farmacia_a, farmacia_b):
    produto = _produto(client, farmacia_a)
    lote_id = _entrada(client, farmacia_a, _item(produto, "A", 100, 10))[0]["lote_id"]

    assert client.get(f"{API}/estoque/lotes", headers=farmacia_b["headers"]).json() == []
    assert client.get(f"{API}/estoque/movimentos", headers=farmacia_b["headers"]).json() == []
    perda = client.post(
        f"{API}/estoque/perdas",
        json={"lote_id": lote_id, "quantidade": "1", "motivo": "Tentativa"},
        headers=farmacia_b["headers"],
    )
    assert perda.status_code == 404
    entrada = client.post(
        f"{API}/estoque/entradas", json={"itens": [_item(produto, "B", 100, 1)]}, headers=farmacia_b["headers"]
    )
    assert entrada.status_code == 404
