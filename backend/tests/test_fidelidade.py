from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import text

from app.shared.datas import hoje
from tests.test_financeiro import _cliente, _vender
from tests.test_vendas import _abrir_caixa, _produto_com_estoque

API = "/api/v1"


def _ativar(client, farmacia, **campos):
    corpo = {"fidelidade_ativa": True, "pontos_por_real": "1", "valor_ponto": "0.10", "pontos_minimo_resgate": 50,
             **campos}
    resposta = client.patch(f"{API}/configuracoes", json=corpo, headers=farmacia["headers"])
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def _pontos(client, farmacia, cliente, movimentos=0) -> dict:
    resposta = client.get(f"{API}/clientes/{cliente['id']}/pontos", params={"movimentos": movimentos},
                          headers=farmacia["headers"])
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def _ajustar(client, farmacia, cliente, pontos, observacao="Bônus de boas-vindas"):
    return client.post(f"{API}/clientes/{cliente['id']}/pontos/ajuste",
                       json={"pontos": pontos, "observacao": observacao}, headers=farmacia["headers"])


def test_cliente_ganha_pontos_e_ficha_mostra_as_compras(client, farmacia_a):
    _ativar(client, farmacia_a)
    produto = _produto_com_estoque(client, farmacia_a, preco="30.50", lotes=(("A", 90, 10),))
    maria = _cliente(client, farmacia_a, nome="Maria")
    _abrir_caixa(client, farmacia_a)

    venda = _vender(client, farmacia_a, produto, [{"forma": "pix", "valor": "30.50"}], cliente_id=maria["id"])
    assert venda.status_code == 201, venda.text
    assert venda.json()["pontos_ganhos"] == 30  # arredonda para baixo
    _vender(client, farmacia_a, produto, [{"forma": "dinheiro", "valor": "61.00"}], quantidade="2",
            cliente_id=maria["id"])
    # Sem cliente identificado não pontua.
    _vender(client, farmacia_a, produto, [{"forma": "dinheiro", "valor": "30.50"}])

    pontos = _pontos(client, farmacia_a, maria, movimentos=10)
    assert (pontos["saldo"], Decimal(pontos["valor"]), pontos["pode_resgatar"]) == (91, Decimal("9.10"), True)
    assert [m["tipo"] for m in pontos["movimentos"]] == ["ganho", "ganho"]
    assert pontos["movimentos"][1]["venda_numero"] == venda.json()["numero"]
    assert pontos["expiram_em"] is not None

    ficha = client.get(f"{API}/clientes/{maria['id']}/ficha", headers=farmacia_a["headers"])
    assert ficha.status_code == 200, ficha.text
    ficha = ficha.json()
    assert ficha["compras"]["quantidade"] == 2
    assert Decimal(ficha["compras"]["total"]) == Decimal("91.50")
    assert Decimal(ficha["compras"]["ticket_medio"]) == Decimal("45.75")
    assert ficha["compras"]["dias_sem_comprar"] == 0
    frequente = ficha["produtos_frequentes"][0]
    assert (frequente["produto_id"], frequente["vezes"], Decimal(frequente["quantidade"])) == (produto["id"], 2, 3)
    assert [c["formas"] for c in ficha["ultimas_compras"]] == [["dinheiro"], ["pix"]]
    assert ficha["pontos"]["saldo"] == 91

    lista = client.get(f"{API}/clientes", headers=farmacia_a["headers"]).json()["itens"]
    assert lista[0]["pontos"] == 91 and lista[0]["ultima_compra"] is not None


def test_troca_de_pontos_vira_desconto(client, farmacia_a):
    _ativar(client, farmacia_a)
    produto = _produto_com_estoque(client, farmacia_a, preco="30.00", lotes=(("A", 90, 10),))
    maria = _cliente(client, farmacia_a, nome="Maria")
    assert _ajustar(client, farmacia_a, maria, 200).status_code == 200
    _abrir_caixa(client, farmacia_a)

    def vender(pontos, pago="20.00", **extra):
        return _vender(client, farmacia_a, produto, [{"forma": "dinheiro", "valor": pago}],
                       pontos_resgatados=pontos, **{"cliente_id": maria["id"], **extra})

    assert vender(100, cliente_id=None).status_code == 400  # sem cliente
    assert "mínimo" in vender(40).json()["detail"]
    assert "só 200 pontos" in vender(250).json()["detail"]

    venda = vender(100)
    assert venda.status_code == 201, venda.text
    venda = venda.json()
    assert (Decimal(venda["desconto"]), Decimal(venda["desconto_pontos"]), Decimal(venda["total"])) == (10, 10, 20)
    assert (venda["pontos_resgatados"], venda["pontos_ganhos"]) == (100, 20)
    assert _pontos(client, farmacia_a, maria)["saldo"] == 120

    # Cancelar devolve os pontos trocados e tira os ganhos.
    cancelar = client.post(f"{API}/vendas/{venda['id']}/cancelar", json={"motivo": "desistiu"},
                           headers=farmacia_a["headers"])
    assert cancelar.status_code == 200, cancelar.text
    pontos = _pontos(client, farmacia_a, maria, movimentos=10)
    assert pontos["saldo"] == 200
    assert [m["tipo"] for m in pontos["movimentos"]][:1] == ["estorno"]


def test_pontos_nao_podem_passar_do_valor_da_compra(client, farmacia_a):
    _ativar(client, farmacia_a, valor_ponto="1")
    produto = _produto_com_estoque(client, farmacia_a, preco="30.00", lotes=(("A", 90, 10),))
    maria = _cliente(client, farmacia_a, nome="Maria")
    _ajustar(client, farmacia_a, maria, 100)
    _abrir_caixa(client, farmacia_a)
    resposta = _vender(client, farmacia_a, produto, [{"forma": "dinheiro", "valor": "1.00"}],
                       cliente_id=maria["id"], pontos_resgatados=100)
    assert resposta.status_code == 400
    assert "valem mais" in resposta.json()["detail"]


def test_programa_desligado_nao_pontua(client, farmacia_a):
    produto = _produto_com_estoque(client, farmacia_a, preco="30.00", lotes=(("A", 90, 10),))
    maria = _cliente(client, farmacia_a, nome="Maria")
    _abrir_caixa(client, farmacia_a)
    venda = _vender(client, farmacia_a, produto, [{"forma": "dinheiro", "valor": "30.00"}], cliente_id=maria["id"])
    assert venda.json()["pontos_ganhos"] == 0
    pontos = _pontos(client, farmacia_a, maria)
    assert (pontos["ativo"], pontos["saldo"], pontos["pode_resgatar"]) == (False, 0, False)
    recusada = _vender(client, farmacia_a, produto, [{"forma": "dinheiro", "valor": "30.00"}],
                       cliente_id=maria["id"], pontos_resgatados=100)
    assert "não está ativo" in recusada.json()["detail"]


def test_pontos_expiram_sem_compras(client, farmacia_a, engine_dono):
    _ativar(client, farmacia_a, pontos_validade_meses=6)
    produto = _produto_com_estoque(client, farmacia_a, preco="30.00", lotes=(("A", 90, 10),))
    maria = _cliente(client, farmacia_a, nome="Maria")
    _abrir_caixa(client, farmacia_a)
    _vender(client, farmacia_a, produto, [{"forma": "dinheiro", "valor": "30.00"}], cliente_id=maria["id"])
    with engine_dono.begin() as conexao:
        conexao.execute(text("UPDATE movimentos_pontos SET criado_em = now() - interval '7 months'"))

    assert _pontos(client, farmacia_a, maria)["saldo"] == 0

    # Na próxima compra a expiração fica registrada e os novos pontos entram.
    _vender(client, farmacia_a, produto, [{"forma": "dinheiro", "valor": "30.00"}], cliente_id=maria["id"])
    pontos = _pontos(client, farmacia_a, maria, movimentos=10)
    assert pontos["saldo"] == 30
    assert [m["tipo"] for m in pontos["movimentos"]] == ["ganho", "expirado", "ganho"]

    # Sem validade, não expiram.
    _ativar(client, farmacia_a, pontos_validade_meses=None)
    with engine_dono.begin() as conexao:
        conexao.execute(text("UPDATE movimentos_pontos SET criado_em = now() - interval '3 years'"))
    assert _pontos(client, farmacia_a, maria)["saldo"] == 30


def test_ajuste_so_gerente_e_com_motivo(client, farmacia_a):
    maria = _cliente(client, farmacia_a, nome="Maria")
    assert _ajustar(client, farmacia_a, maria, 10, observacao="").status_code == 422
    assert _ajustar(client, farmacia_a, maria, 0).status_code == 400
    assert _ajustar(client, farmacia_a, maria, -30, observacao="Correção").json()["saldo"] == -30


def test_aniversariantes_e_sumidos(client, farmacia_a, engine_dono):
    hoje_ = hoje()
    aniversario = date(1980, hoje_.month, min(hoje_.day, 28))
    outro_mes = date(1980, hoje_.month % 12 + 1, 10)
    client.post(f"{API}/clientes", json={"nome": "Ana", "data_nascimento": aniversario.isoformat()},
                headers=farmacia_a["headers"])
    client.post(f"{API}/clientes", json={"nome": "Bia", "data_nascimento": outro_mes.isoformat()},
                headers=farmacia_a["headers"])
    sumido = _cliente(client, farmacia_a, nome="Carlos")
    ativo = _cliente(client, farmacia_a, nome="Davi")
    produto = _produto_com_estoque(client, farmacia_a, preco="10.00", lotes=(("A", 90, 10),))
    _abrir_caixa(client, farmacia_a)
    antiga = _vender(client, farmacia_a, produto, [{"forma": "dinheiro", "valor": "10.00"}],
                     cliente_id=sumido["id"]).json()
    _vender(client, farmacia_a, produto, [{"forma": "dinheiro", "valor": "10.00"}], cliente_id=ativo["id"])
    with engine_dono.begin() as conexao:
        conexao.execute(text("UPDATE vendas SET finalizada_em = now() - interval '90 days' WHERE id = :id"),
                        {"id": antiga["id"]})

    def nomes(filtro):
        resposta = client.get(f"{API}/clientes", params={"filtro": filtro}, headers=farmacia_a["headers"])
        return [c["nome"] for c in resposta.json()["itens"]]

    assert nomes("aniversariantes") == ["Ana"]
    assert nomes("sumidos") == ["Carlos"]
    ficha = client.get(f"{API}/clientes/{sumido['id']}/ficha", headers=farmacia_a["headers"]).json()
    assert ficha["compras"]["dias_sem_comprar"] >= 89


def test_pontos_isolados_por_farmacia(client, farmacia_a, farmacia_b):
    maria = _cliente(client, farmacia_a, nome="Maria")
    _ajustar(client, farmacia_a, maria, 100)
    assert client.get(f"{API}/clientes/{maria['id']}/pontos", headers=farmacia_b["headers"]).status_code == 404
    assert client.get(f"{API}/clientes/{maria['id']}/ficha", headers=farmacia_b["headers"]).status_code == 404
    assert _ajustar(client, farmacia_b, maria, 100).status_code == 404
