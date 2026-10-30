import uuid
from decimal import Decimal

from tests.test_financeiro import _cliente
from tests.test_promocoes_relatorios import _produto, _promocao
from tests.test_vendas import _abrir_caixa

API = "/api/v1"


def _ligar_loja(client, farmacia, endereco="bem-estar", **extra):
    corpo = {"loja_online_ativa": True, "loja_online_endereco": endereco, "whatsapp": "11999998888", **extra}
    resposta = client.patch(f"{API}/configuracoes", json=corpo, headers=farmacia["headers"])
    assert resposta.status_code == 200, resposta.text


def _pedir(client, itens, loja="bem-estar", esperado=201, **dados):
    corpo = {"itens": [{"produto_id": p["id"], "quantidade": str(q)} for p, q in itens], "nome": "Ana Lima",
             "telefone": "(11) 98888-7777", **dados}
    resposta = client.post(f"{API}/loja/{loja}/pedidos", json=corpo)
    assert resposta.status_code == esperado, resposta.text
    return resposta.json()


def _acao(client, farmacia, pedido_id, acao, esperado=200, **corpo):
    resposta = client.post(f"{API}/pedidos/{pedido_id}/{acao}", json=corpo or None, headers=farmacia["headers"])
    assert resposta.status_code == esperado, resposta.text
    return resposta.json()


def test_loja_online_desligada_nao_aparece(client, farmacia_a):
    assert client.get(f"{API}/loja/bem-estar").status_code == 404
    # Ligar exige escolher o endereço.
    resposta = client.patch(f"{API}/configuracoes", json={"loja_online_ativa": True}, headers=farmacia_a["headers"])
    assert resposta.status_code == 400
    resposta = client.patch(f"{API}/configuracoes", json={"loja_online_endereco": "Com Espaço"},
                            headers=farmacia_a["headers"])
    assert resposta.status_code == 422


def test_endereco_da_loja_e_unico(client, farmacia_a, farmacia_b):
    _ligar_loja(client, farmacia_a)
    resposta = client.patch(f"{API}/configuracoes", json={"loja_online_endereco": "bem-estar"},
                            headers=farmacia_b["headers"])
    assert resposta.status_code == 409


def test_catalogo_mostra_so_o_que_vende_online_e_tem_estoque(client, farmacia_a):
    _ligar_loja(client, farmacia_a, loja_online_mensagem="Entregamos no centro")
    protetor = _produto(client, farmacia_a, "Protetor", "50.00")
    _promocao(client, farmacia_a, [protetor], percentual="10")
    sem_estoque = client.post(f"{API}/produtos", json={"nome": "Sabonete", "preco_venda": "3.00"},
                              headers=farmacia_a["headers"]).json()
    remedio = client.post(f"{API}/produtos", json={"nome": "Amoxicilina", "preco_venda": "20.00", "tipo": "medicamento"},
                          headers=farmacia_a["headers"]).json()
    assert remedio["vende_online"] is False and sem_estoque["vende_online"] is True

    loja = client.get(f"{API}/loja/bem-estar").json()
    assert (loja["nome"], loja["mensagem"], loja["whatsapp"]) == ("Farmácia 11111111000111", "Entregamos no centro",
                                                                  "11999998888")
    catalogo = client.get(f"{API}/loja/bem-estar/produtos").json()
    assert [p["nome"] for p in catalogo["produtos"]] == ["Protetor"]
    item = catalogo["produtos"][0]
    assert (Decimal(item["preco_promocional"]), item["promocao"], item["maximo"]) == (45, "10% de desconto", 10)
    assert client.get(f"{API}/loja/bem-estar/produtos", params={"busca": "xyz"}).json()["total"] == 0


def test_pedido_do_site_vira_pre_venda_e_e_entregue_no_caixa(client, farmacia_a):
    _ligar_loja(client, farmacia_a)
    protetor = _produto(client, farmacia_a, "Protetor", "50.00", quantidade=3)
    _promocao(client, farmacia_a, [protetor], percentual="10")
    ana = _cliente(client, farmacia_a, "Ana Lima")
    client.patch(f"{API}/clientes/{ana["id"]}", json={"telefone": "11988887777"},
               headers=farmacia_a["headers"])

    _pedir(client, [(protetor, 4)], esperado=400)  # só tem 3
    _pedir(client, [(protetor, 1)], entrega=True, endereco="Rua A, 10", esperado=400)  # sem entrega
    _pedir(client, [(protetor, 1)], forma_pagamento="dinheiro", troco_para="10.00", esperado=400)
    pedido = _pedir(client, [(protetor, 2)], forma_pagamento="dinheiro", troco_para="100.00", observacao="Sem sacola")
    assert (pedido["numero"], pedido["status"], Decimal(pedido["total"])) == (1, "novo", 90)
    assert client.get(f"{API}/loja/bem-estar/pedidos/{pedido['codigo']}").json()["status"] == "novo"

    lista = client.get(f"{API}/pedidos", headers=farmacia_a["headers"]).json()
    assert lista["resumo"]["novo"] == 1
    assert client.get(f"{API}/painel", headers=farmacia_a["headers"]).json()["pedidos_novos"] == 1
    salvo = lista["pedidos"][0]
    assert (salvo["canal"], salvo["cliente_id"], salvo["observacao"]) == ("site", ana["id"], "Sem sacola")

    confirmado = _acao(client, farmacia_a, salvo["id"], "confirmar")
    assert (confirmado["status"], confirmado["pre_venda_numero"], confirmado["pago"]) == ("separando", 1, False)
    _acao(client, farmacia_a, salvo["id"], "saiu", esperado=400)  # é para retirar
    assert _acao(client, farmacia_a, salvo["id"], "pronto")["status"] == "pronto"

    # O cliente chega e paga no caixa: o PDV recebe a pré-venda e o pedido fica entregue.
    _abrir_caixa(client, farmacia_a)
    pre_venda = client.get(f"{API}/pre-vendas/numero/1", headers=farmacia_a["headers"]).json()
    venda = client.post(
        f"{API}/vendas",
        json={"chave_idempotencia": str(uuid.uuid4()), "pre_venda_id": pre_venda["id"],
              "itens": [{"produto_id": protetor["id"], "quantidade": "2"}],
              "pagamentos": [{"forma": "dinheiro", "valor": "100.00"}]},
        headers=farmacia_a["headers"],
    )
    assert venda.status_code == 201, venda.text
    assert Decimal(venda.json()["total"]) == 90  # o caixa cobra o mesmo que o site mostrou
    final = client.get(f"{API}/pedidos/{salvo['id']}", headers=farmacia_a["headers"]).json()
    assert (final["status"], final["pago"]) == ("entregue", True)
    assert client.get(f"{API}/loja/bem-estar/pedidos/{pedido['codigo']}").json()["status"] == "entregue"


def test_pedido_do_whatsapp_com_entrega_e_cancelamento(client, farmacia_a):
    _ligar_loja(client, farmacia_a, entrega_ativa=True, entrega_minimo="30.00")
    fralda = _produto(client, farmacia_a, "Fralda", "20.00")
    _pedir(client, [(fralda, 1)], entrega=True, endereco="Rua B, 5", esperado=400)  # abaixo do mínimo
    _pedir(client, [(fralda, 2)], entrega=True, esperado=422)  # sem endereço

    resposta = client.post(
        f"{API}/pedidos",
        json={"canal": "whatsapp", "itens": [{"produto_id": fralda["id"], "quantidade": "2"}], "nome": "Rita",
              "telefone": "11977771234", "entrega": True, "endereco": "Rua B, 5", "forma_pagamento": "cartao"},
        headers=farmacia_a["headers"],
    )
    assert resposta.status_code == 201, resposta.text
    pedido = resposta.json()
    assert (pedido["canal"], pedido["entrega"], Decimal(pedido["total"])) == ("whatsapp", True, 40)

    _acao(client, farmacia_a, pedido["id"], "confirmar")
    assert _acao(client, farmacia_a, pedido["id"], "saiu")["status"] == "saiu"
    cancelado = _acao(client, farmacia_a, pedido["id"], "cancelar", motivo="Cliente não estava em casa")
    assert cancelado["status"] == "cancelado"
    # A pré-venda some da fila do caixa.
    pre_venda = client.get(f"{API}/pre-vendas/numero/1", headers=farmacia_a["headers"]).json()
    assert pre_venda["status"] == "cancelada"
    _acao(client, farmacia_a, pedido["id"], "confirmar", esperado=409)


def test_site_nao_aceita_produto_fora_da_loja_online(client, farmacia_a):
    _ligar_loja(client, farmacia_a)
    remedio = _produto(client, farmacia_a, "Amoxicilina", "20.00")
    client.patch(f"{API}/produtos/{remedio['id']}", json={"vende_online": False}, headers=farmacia_a["headers"])
    _pedir(client, [(remedio, 1)], esperado=404)
    _pedir(client, [(remedio, 1.5)], esperado=404)


def test_pedidos_isolados_por_farmacia(client, farmacia_a, farmacia_b):
    _ligar_loja(client, farmacia_a)
    protetor = _produto(client, farmacia_a, "Protetor", "50.00")
    pedido = _pedir(client, [(protetor, 1)])
    assert client.get(f"{API}/pedidos", headers=farmacia_b["headers"]).json()["pedidos"] == []
    assert client.get(f"{API}/pedidos", headers=farmacia_a["headers"]).json()["pedidos"][0]["codigo"] == pedido["codigo"]
