import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.security import gerar_hash_senha
from app.modules.auth.models import Usuario
from app.shared.datas import hoje

API = "/api/v1"


def _produto_com_estoque(client, farmacia, nome="Dipirona 500mg", preco="8.90", lotes=(("A", 30, 5),)) -> dict:
    produto = client.post(
        f"{API}/produtos", json={"nome": nome, "preco_venda": preco}, headers=farmacia["headers"]
    ).json()
    itens = [
        {
            "produto_id": produto["id"],
            "numero_lote": lote,
            "validade": (hoje() + timedelta(days=dias)).isoformat(),
            "quantidade": str(qtd),
        }
        for lote, dias, qtd in lotes
    ]
    resposta = client.post(f"{API}/estoque/entradas", json={"itens": itens}, headers=farmacia["headers"])
    assert resposta.status_code == 201, resposta.text
    return produto


def _registrar_pdv(client, headers, nome="PDV 01") -> str:
    """Cria um PDV na matriz e devolve a chave que o navegador guardaria."""
    matriz = client.get(f"{API}/lojas", headers=headers).json()[0]
    terminal = client.post(f"{API}/terminais", json={"loja_id": matriz["id"], "nome": nome}, headers=headers)
    assert terminal.status_code == 201, terminal.text
    vinculo = client.post(f"{API}/terminais/{terminal.json()['id']}/vincular", headers=headers)
    assert vinculo.status_code == 200, vinculo.text
    return vinculo.json()["chave"]


def _abrir_caixa(client, farmacia, valor="100.00") -> dict:
    """Registra um PDV, passa a usá-lo nas próximas chamadas (X-Terminal) e abre o caixa."""
    if "X-Terminal" not in farmacia["headers"]:
        farmacia["headers"]["X-Terminal"] = _registrar_pdv(client, farmacia["headers"])
    resposta = client.post(f"{API}/caixas/abrir", json={"valor_abertura": valor}, headers=farmacia["headers"])
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _venda(produto_id, quantidade="1", pagamentos=None, **extra) -> dict:
    return {
        "chave_idempotencia": str(uuid.uuid4()),
        "itens": [{"produto_id": produto_id, "quantidade": quantidade}],
        "pagamentos": pagamentos or [{"forma": "pix", "valor": "8.90"}],
        **extra,
    }


def _saldo(client, farmacia, produto_id) -> dict:
    lotes = client.get(
        f"{API}/estoque/lotes", params={"produto_id": produto_id, "incluir_zerados": True}, headers=farmacia["headers"]
    ).json()
    return {l["numero_lote"]: Decimal(l["quantidade"]) for l in lotes}


def test_venda_completa_baixa_estoque_fefo(client, farmacia_a):
    produto = _produto_com_estoque(client, farmacia_a, lotes=(("TARDE", 200, 5), ("CEDO", 20, 2)))
    _abrir_caixa(client, farmacia_a)

    resposta = client.post(
        f"{API}/vendas",
        json=_venda(produto["id"], "3", [{"forma": "dinheiro", "valor": "30.00"}]),
        headers=farmacia_a["headers"],
    )
    assert resposta.status_code == 201, resposta.text
    venda = resposta.json()
    assert venda["numero"] == 1
    assert venda["total"] == "26.70"
    assert venda["troco"] == "3.30"
    assert venda["itens"][0]["descricao"] == "Dipirona 500mg"
    assert _saldo(client, farmacia_a, produto["id"]) == {"CEDO": 0, "TARDE": 4}


def test_numeracao_sequencial(client, farmacia_a):
    produto = _produto_com_estoque(client, farmacia_a)
    _abrir_caixa(client, farmacia_a)
    numeros = [
        client.post(f"{API}/vendas", json=_venda(produto["id"]), headers=farmacia_a["headers"]).json()["numero"]
        for _ in range(3)
    ]
    assert numeros == [1, 2, 3]


def test_reenvio_com_mesma_chave_nao_duplica(client, farmacia_a):
    produto = _produto_com_estoque(client, farmacia_a)
    _abrir_caixa(client, farmacia_a)
    dados = _venda(produto["id"])

    primeira = client.post(f"{API}/vendas", json=dados, headers=farmacia_a["headers"])
    segunda = client.post(f"{API}/vendas", json=dados, headers=farmacia_a["headers"])
    assert primeira.status_code == 201
    assert segunda.status_code == 200
    assert segunda.json()["id"] == primeira.json()["id"]
    assert _saldo(client, farmacia_a, produto["id"]) == {"A": 4}


def test_sem_caixa_aberto(client, farmacia_a):
    produto = _produto_com_estoque(client, farmacia_a)
    sem_pdv = client.post(f"{API}/vendas", json=_venda(produto["id"]), headers=farmacia_a["headers"])
    assert sem_pdv.status_code == 400
    assert "registrado como PDV" in sem_pdv.json()["detail"]

    farmacia_a["headers"]["X-Terminal"] = _registrar_pdv(client, farmacia_a["headers"])
    resposta = client.post(f"{API}/vendas", json=_venda(produto["id"]), headers=farmacia_a["headers"])
    assert resposta.status_code == 400
    assert "Abra o caixa" in resposta.json()["detail"]


def test_estoque_insuficiente_nao_grava_nada(client, farmacia_a):
    produto = _produto_com_estoque(client, farmacia_a)
    _abrir_caixa(client, farmacia_a)
    resposta = client.post(
        f"{API}/vendas",
        json=_venda(produto["id"], "10", [{"forma": "pix", "valor": "89.00"}]),
        headers=farmacia_a["headers"],
    )
    assert resposta.status_code == 409
    assert client.get(f"{API}/vendas", headers=farmacia_a["headers"]).json() == []
    assert _saldo(client, farmacia_a, produto["id"]) == {"A": 5}


def test_pagamento_insuficiente_e_troco_sem_dinheiro(client, farmacia_a):
    produto = _produto_com_estoque(client, farmacia_a)
    _abrir_caixa(client, farmacia_a)
    falta = client.post(
        f"{API}/vendas", json=_venda(produto["id"], pagamentos=[{"forma": "pix", "valor": "5"}]), headers=farmacia_a["headers"]
    )
    assert falta.status_code == 400
    troco_no_cartao = client.post(
        f"{API}/vendas", json=_venda(produto["id"], pagamentos=[{"forma": "debito", "valor": "20"}]), headers=farmacia_a["headers"]
    )
    assert troco_no_cartao.status_code == 400


def test_pagamento_dividido(client, farmacia_a):
    produto = _produto_com_estoque(client, farmacia_a)
    _abrir_caixa(client, farmacia_a)
    resposta = client.post(
        f"{API}/vendas",
        json=_venda(produto["id"], "2", [{"forma": "credito", "valor": "10.00"}, {"forma": "dinheiro", "valor": "10.00"}]),
        headers=farmacia_a["headers"],
    )
    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["troco"] == "2.20"


def test_cpf_na_nota(client, farmacia_a):
    produto = _produto_com_estoque(client, farmacia_a)
    _abrir_caixa(client, farmacia_a)
    invalido = client.post(f"{API}/vendas", json=_venda(produto["id"], cliente_cpf="123.456.789-00"), headers=farmacia_a["headers"])
    assert invalido.status_code == 422
    valido = client.post(f"{API}/vendas", json=_venda(produto["id"], cliente_cpf="529.982.247-25"), headers=farmacia_a["headers"])
    assert valido.json()["cliente_cpf"] == "52998224725"


def test_cancelamento_devolve_ao_mesmo_lote(client, farmacia_a):
    produto = _produto_com_estoque(client, farmacia_a, lotes=(("TARDE", 200, 5), ("CEDO", 20, 2)))
    _abrir_caixa(client, farmacia_a)
    venda = client.post(
        f"{API}/vendas", json=_venda(produto["id"], "3", [{"forma": "pix", "valor": "26.70"}]), headers=farmacia_a["headers"]
    ).json()

    resposta = client.post(f"{API}/vendas/{venda['id']}/cancelar", json={"motivo": "Cliente desistiu"}, headers=farmacia_a["headers"])
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["status"] == "cancelada"
    assert _saldo(client, farmacia_a, produto["id"]) == {"CEDO": 2, "TARDE": 5}

    de_novo = client.post(f"{API}/vendas/{venda['id']}/cancelar", json={"motivo": "Outra vez"}, headers=farmacia_a["headers"])
    assert de_novo.status_code == 409


def test_fechamento_de_caixa(client, farmacia_a):
    produto = _produto_com_estoque(client, farmacia_a)
    caixa = _abrir_caixa(client, farmacia_a, "50.00")
    client.post(f"{API}/vendas", json=_venda(produto["id"], "1", [{"forma": "dinheiro", "valor": "10.00"}]), headers=farmacia_a["headers"])
    client.post(f"{API}/vendas", json=_venda(produto["id"], "1", [{"forma": "pix", "valor": "8.90"}]), headers=farmacia_a["headers"])
    cancelada = client.post(f"{API}/vendas", json=_venda(produto["id"]), headers=farmacia_a["headers"]).json()
    client.post(f"{API}/vendas/{cancelada['id']}/cancelar", json={"motivo": "Erro"}, headers=farmacia_a["headers"])

    resumo = client.post(
        f"{API}/caixas/{caixa['id']}/fechar", json={"valor_fechamento_informado": "58.00"}, headers=farmacia_a["headers"]
    ).json()
    assert resumo["quantidade_vendas"] == 2
    assert resumo["total_vendido"] == "17.80"
    assert resumo["dinheiro_esperado"] == "58.90"  # 50 + 10 - 1,10 de troco
    assert resumo["diferenca"] == "-0.90"
    assert client.post(f"{API}/vendas", json=_venda(produto["id"]), headers=farmacia_a["headers"]).status_code == 400


def test_um_caixa_aberto_por_vez(client, farmacia_a):
    _abrir_caixa(client, farmacia_a)
    resposta = client.post(f"{API}/caixas/abrir", json={"valor_abertura": "0"}, headers=farmacia_a["headers"])
    assert resposta.status_code == 409


def _login_caixa(client, engine_dono, farmacia) -> dict:
    with Session(engine_dono) as db:
        db.add(Usuario(farmacia_id=farmacia["id"], nome="Caixa", email="caixa@farmacia.com",
                       senha_hash=gerar_hash_senha("senha-forte"), papel="caixa"))
        db.commit()
    token = client.post(f"{API}/auth/login", json={"email": "caixa@farmacia.com", "senha": "senha-forte"}).json()
    return {"Authorization": f"Bearer {token['access_token']}"}


def test_operador_de_caixa_limites(client, engine_dono, farmacia_a):
    produto = _produto_com_estoque(client, farmacia_a, preco="100.00")
    headers = _login_caixa(client, engine_dono, farmacia_a)
    headers["X-Terminal"] = _registrar_pdv(client, farmacia_a["headers"])
    assert client.post(f"{API}/caixas/abrir", json={"valor_abertura": "0"}, headers=headers).status_code == 201

    ok = client.post(f"{API}/vendas", json=_venda(produto["id"], pagamentos=[{"forma": "pix", "valor": "90"}], desconto="10.00"), headers=headers)
    assert ok.status_code == 201, ok.text
    demais = client.post(f"{API}/vendas", json=_venda(produto["id"], pagamentos=[{"forma": "pix", "valor": "80"}], desconto="20.00"), headers=headers)
    assert demais.status_code == 403

    cancelar = client.post(f"{API}/vendas/{ok.json()['id']}/cancelar", json={"motivo": "Teste"}, headers=headers)
    assert cancelar.status_code == 403


def test_isolamento_das_vendas(client, farmacia_a, farmacia_b):
    produto = _produto_com_estoque(client, farmacia_a)
    _abrir_caixa(client, farmacia_a)
    venda = client.post(f"{API}/vendas", json=_venda(produto["id"]), headers=farmacia_a["headers"]).json()

    _abrir_caixa(client, farmacia_b)
    assert client.get(f"{API}/vendas", headers=farmacia_b["headers"]).json() == []
    assert client.get(f"{API}/vendas/{venda['id']}", headers=farmacia_b["headers"]).status_code == 404
    # Farmácia B não consegue vender produto da A.
    assert client.post(f"{API}/vendas", json=_venda(produto["id"]), headers=farmacia_b["headers"]).status_code == 404
    # E a numeração é separada por farmácia.
    produto_b = _produto_com_estoque(client, farmacia_b)
    assert client.post(f"{API}/vendas", json=_venda(produto_b["id"]), headers=farmacia_b["headers"]).json()["numero"] == 1
