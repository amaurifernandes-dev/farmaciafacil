import uuid
from decimal import Decimal

from app.modules.devolucoes.service import _bloqueio_do_produto
from app.modules.produtos.models import Produto
from tests.test_financeiro import _cliente
from tests.test_vendas import _abrir_caixa, _login_caixa, _produto_com_estoque, _registrar_pdv, _saldo

API = "/api/v1"


def _vender(client, farmacia, produto, quantidade, pagamentos, esperado=201, **extra):
    corpo = {
        "chave_idempotencia": str(uuid.uuid4()),
        "itens": [{"produto_id": produto["id"], "quantidade": str(quantidade)}],
        "pagamentos": pagamentos,
        **extra,
    }
    resposta = client.post(f"{API}/vendas", json=corpo, headers=farmacia["headers"])
    assert resposta.status_code == esperado, resposta.text
    return resposta.json()


def _devolver(client, farmacia, venda, itens, destino="vale", esperado=201, motivo="Cliente trocou", headers=None):
    corpo = {"venda_id": venda["id"], "destino": destino, "motivo": motivo, "itens": itens}
    resposta = client.post(f"{API}/devolucoes", json=corpo, headers=headers or farmacia["headers"])
    assert resposta.status_code == esperado, resposta.text
    return resposta.json()


def _item(venda, quantidade, **extra):
    return {"venda_item_id": venda["itens"][0]["id"], "quantidade": str(quantidade), **extra}


def test_devolve_parte_em_dinheiro_e_o_resto_em_vale(client, farmacia_a):
    h = farmacia_a["headers"]
    shampoo = _produto_com_estoque(client, farmacia_a, "Shampoo", "10.00", lotes=(("CEDO", 30, 2), ("TARDE", 200, 5)))
    _abrir_caixa(client, farmacia_a)
    # 3 x 10,00 com 3,00 de desconto na venda: cada um sai por 9,00.
    venda = _vender(client, farmacia_a, shampoo, 3, [{"forma": "dinheiro", "valor": "30.00"}], desconto="3.00")
    assert (venda["total"], venda["troco"]) == ("27.00", "3.00")
    assert _saldo(client, farmacia_a, shampoo["id"]) == {"CEDO": 0, "TARDE": 4}

    consulta = client.get(f"{API}/devolucoes/venda", params={"numero": venda["numero"]}, headers=h).json()
    assert consulta["bloqueio"] is None
    item = consulta["itens"][0]
    assert (item["disponivel"], item["valor_pago"], item["valor_unitario"], item["volta_estoque_sugerido"]) == (
        "3.000", "27.00", "9.00", True)

    # Um em dinheiro: sai da gaveta e volta para o lote de onde saiu.
    d1 = _devolver(client, farmacia_a, venda, [_item(venda, 1)], destino="dinheiro")
    assert (d1["numero"], d1["valor_total"], d1["vale"], d1["venda_numero"]) == (1, "9.00", None, venda["numero"])
    assert _saldo(client, farmacia_a, shampoo["id"]) == {"CEDO": 1, "TARDE": 4}
    caixa = client.get(f"{API}/caixas/atual", headers=h).json()
    assert (caixa["devolucoes_dinheiro"], caixa["dinheiro_esperado"]) == ("9.00", "118.00")  # 100 + 30 - 3 - 9

    # Os outros dois em vale-troca: o último leva os centavos que sobraram.
    d2 = _devolver(client, farmacia_a, venda, [_item(venda, 2)])
    vale = d2["vale"]
    assert (d2["valor_total"], vale["valor"], vale["saldo"], vale["status"], len(vale["codigo"])) == (
        "18.00", "18.00", "18.00", "ativo", 8)
    assert _saldo(client, farmacia_a, shampoo["id"]) == {"CEDO": 2, "TARDE": 5}

    erro = _devolver(client, farmacia_a, venda, [_item(venda, 1)], esperado=400)
    assert "já foi devolvido" in erro["detail"]
    consulta = client.get(f"{API}/devolucoes/venda", params={"venda_id": venda["id"]}, headers=h).json()
    assert "já foram devolvidos" in consulta["bloqueio"]
    assert [d["numero"] for d in consulta["devolucoes"]] == [1, 2]
    cancelar = client.post(f"{API}/vendas/{venda['id']}/cancelar", json={"motivo": "Teste"}, headers=h)
    assert cancelar.status_code == 409

    # O vale paga outra compra no PDV (o código aceita minúsculas e traço).
    digitado = f"{vale['codigo'][:4].lower()}-{vale['codigo'][4:]}"
    assert client.get(f"{API}/vales/{digitado}", headers=h).json()["saldo"] == "18.00"
    compra = _vender(client, farmacia_a, shampoo, 1, [{"forma": "vale", "valor": "10.00", "vale_codigo": digitado}])
    assert compra["pagamentos"] == [{"forma": "vale", "valor": "10.00"}]
    assert client.get(f"{API}/vales/{vale['codigo']}", headers=h).json()["saldo"] == "8.00"
    erro = _vender(client, farmacia_a, shampoo, 1, [{"forma": "vale", "valor": "10.00", "vale_codigo": vale["codigo"]}],
                   esperado=400)
    assert "só tem R$ 8.00" in erro["detail"]
    erro = _vender(client, farmacia_a, shampoo, 1, [{"forma": "vale", "valor": "10.00"}], esperado=400)
    assert "código do vale" in erro["detail"]
    assert client.get(f"{API}/vales/NAOEXISTE", headers=h).status_code == 404

    # Vale não dá troco em dinheiro.
    erro = _vender(client, farmacia_a, shampoo, 1, [{"forma": "vale", "valor": "8.00", "vale_codigo": vale["codigo"]},
                                                    {"forma": "pix", "valor": "5.00"}], esperado=400)
    assert "Troco" in erro["detail"]
    # Gastou o resto: vale usado.
    _vender(client, farmacia_a, shampoo, 1, [{"forma": "vale", "valor": "8.00", "vale_codigo": vale["codigo"]},
                                             {"forma": "pix", "valor": "2.00"}])
    assert client.get(f"{API}/vales/{vale['codigo']}", headers=h).json()["status"] == "usado"

    # Cancelar a compra paga com vale devolve o saldo ao vale.
    client.post(f"{API}/vendas/{compra['id']}/cancelar", json={"motivo": "Errado"}, headers=h)
    assert client.get(f"{API}/vales/{vale['codigo']}", headers=h).json()["saldo"] == "10.00"

    # Venda paga com vale só devolve em vale (o vale não vira dinheiro).
    paga_com_vale = _vender(client, farmacia_a, shampoo, 1,
                            [{"forma": "vale", "valor": "10.00", "vale_codigo": vale["codigo"]}])
    erro = _devolver(client, farmacia_a, paga_com_vale, [_item(paga_com_vale, 1)], destino="dinheiro", esperado=400)
    assert "vale-troca" in erro["detail"]

    lista = client.get(f"{API}/devolucoes", headers=h).json()
    assert (lista["quantidade"], lista["em_dinheiro"], lista["em_vale"], lista["total"]) == (2, "9.00", "18.00", "27.00")
    assert lista["itens"][0]["numero"] == 2


def test_regras_da_devolucao(client, engine_dono, farmacia_a):
    h = farmacia_a["headers"]
    remedio = _produto_com_estoque(client, farmacia_a, "Amoxicilina", "20.00", lotes=(("R1", 90, 5),))
    client.patch(f"{API}/produtos/{remedio['id']}", json={"tipo": "medicamento"}, headers=h)
    _abrir_caixa(client, farmacia_a)
    venda = _vender(client, farmacia_a, remedio, 2, [{"forma": "pix", "valor": "40.00"}])

    # Remédio não volta para a prateleira, a não ser que o gerente marque.
    consulta = client.get(f"{API}/devolucoes/venda", params={"numero": venda["numero"]}, headers=h).json()
    assert consulta["itens"][0]["volta_estoque_sugerido"] is False
    d = _devolver(client, farmacia_a, venda, [_item(venda, 1)])
    assert (d["itens"][0]["volta_estoque"], d["valor_total"]) == (False, "20.00")
    assert _saldo(client, farmacia_a, remedio["id"]) == {"R1": 3}
    _devolver(client, farmacia_a, venda, [_item(venda, 1, volta_estoque=True)])
    assert _saldo(client, farmacia_a, remedio["id"]) == {"R1": 4}

    erro = _devolver(client, farmacia_a, venda, [{"venda_item_id": str(uuid.uuid4()), "quantidade": "1"}],
                     esperado=400)
    assert "não é desta venda" in erro["detail"]
    nova = _vender(client, farmacia_a, remedio, 1, [{"forma": "pix", "valor": "20.00"}])
    erro = _devolver(client, farmacia_a, nova, [_item(nova, 2)], esperado=400)
    assert "só dá para devolver 1" in erro["detail"]

    # Venda a prazo (fiado) não aceita devolução de item: só cancelando inteira.
    joao = _cliente(client, farmacia_a, limite="100.00")
    fiado = _vender(client, farmacia_a, remedio, 1, [{"forma": "prazo", "valor": "20.00"}], cliente_id=joao["id"])
    consulta = client.get(f"{API}/devolucoes/venda", params={"numero": fiado["numero"]}, headers=h).json()
    assert "a prazo" in consulta["bloqueio"]
    _devolver(client, farmacia_a, fiado, [_item(fiado, 1)], esperado=400)

    # Venda cancelada também não.
    cancelada = _vender(client, farmacia_a, remedio, 1, [{"forma": "pix", "valor": "20.00"}])
    client.post(f"{API}/vendas/{cancelada['id']}/cancelar", json={"motivo": "Teste"}, headers=h)
    _devolver(client, farmacia_a, cancelada, [_item(cancelada, 1)], esperado=400)

    # O operador de caixa não devolve (como no cancelamento, é com o gerente).
    caixa = _login_caixa(client, engine_dono, farmacia_a)
    _devolver(client, farmacia_a, nova, [_item(nova, 1)], headers=caixa, esperado=403)
    assert client.get(f"{API}/devolucoes/venda", params={"numero": 1}, headers=caixa).status_code == 403

    # Dinheiro só sai de um caixa aberto.
    caixa_atual = client.get(f"{API}/caixas/atual", headers=h).json()
    client.post(f"{API}/caixas/{caixa_atual['caixa']['id']}/fechar", json={"valor_fechamento_informado": "100"},
                headers=h)
    erro = _devolver(client, farmacia_a, nova, [_item(nova, 1)], destino="dinheiro", esperado=400)
    assert "caixa aberto" in erro["detail"]
    sem_pdv = {"Authorization": h["Authorization"]}
    _devolver(client, farmacia_a, nova, [_item(nova, 1)], destino="dinheiro", esperado=400, headers=sem_pdv)

    assert client.get(f"{API}/devolucoes/venda", params={"numero": 999}, headers=h).status_code == 404


def test_controlado_nao_pode_ser_trocado():
    assert "SNGPC" in _bloqueio_do_produto(Produto(controle="C1"))
    assert _bloqueio_do_produto(Produto(controle=None)) is None


def test_devolucao_sai_da_comissao_e_da_meta(client, farmacia_a):
    h = farmacia_a["headers"]
    client.patch(f"{API}/configuracoes", json={"comissao_padrao": "10"}, headers=h)
    perfume = _produto_com_estoque(client, farmacia_a, "Perfume", "50.00", lotes=(("P", 300, 5),))
    _abrir_caixa(client, farmacia_a)
    venda = _vender(client, farmacia_a, perfume, 2, [{"forma": "pix", "valor": "100.00"}])
    _devolver(client, farmacia_a, venda, [_item(venda, 1)])

    vendedor = client.get(f"{API}/comissoes", headers=h).json()["vendedores"][0]
    assert (vendedor["vendas"], vendedor["vendido"], vendedor["comissao"]) == (1, "50.00", "5.00")
    loja = client.get(f"{API}/metas", headers=h).json()["lojas"][0]
    assert (loja["vendido"], loja["vendas"]) == ("50.00", 1)
    detalhe = client.get(f"{API}/comissoes/vendedor/{venda['usuario_id']}", headers=h).json()
    assert Decimal(detalhe["produtos"][0]["quantidade"]) == 1


def test_isolamento_das_devolucoes(client, farmacia_a, farmacia_b):
    produto = _produto_com_estoque(client, farmacia_a, "Sabonete", "5.00", lotes=(("S", 90, 5),))
    _abrir_caixa(client, farmacia_a)
    venda = _vender(client, farmacia_a, produto, 1, [{"forma": "pix", "valor": "5.00"}])
    d = _devolver(client, farmacia_a, venda, [_item(venda, 1)])
    hb = farmacia_b["headers"]
    hb["X-Terminal"] = _registrar_pdv(client, hb)
    assert client.get(f"{API}/devolucoes/venda", params={"venda_id": venda["id"]}, headers=hb).status_code == 404
    assert client.get(f"{API}/devolucoes/{d['id']}", headers=hb).status_code == 404
    assert client.get(f"{API}/vales/{d['vale']['codigo']}", headers=hb).status_code == 404
    assert client.get(f"{API}/devolucoes", headers=hb).json()["quantidade"] == 0
