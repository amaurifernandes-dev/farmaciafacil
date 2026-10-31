import uuid
from datetime import timedelta
from decimal import Decimal

from app.shared.datas import hoje
from tests.test_promocoes_relatorios import _produto, _promocao
from tests.test_vendas import _abrir_caixa

API = "/api/v1"


def _convenio(client, farmacia, esperado=201, **dados):
    corpo = {"nome": "Metalúrgica Silva", "desconto": "10", "limite_padrao": "100,00", "dia_fechamento": 20, **dados}
    resposta = client.post(f"{API}/convenios", json=corpo, headers=farmacia["headers"])
    assert resposta.status_code == esperado, resposta.text
    return resposta.json()


def _funcionario(client, farmacia, convenio, nome="Pedro Alves", **extra):
    corpo = {"nome": nome, "convenio_id": convenio["id"], "convenio_matricula": "M-01", **extra}
    resposta = client.post(f"{API}/clientes", json=corpo, headers=farmacia["headers"])
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _vender(client, farmacia, itens, pagamentos, cliente=None, esperado=201):
    corpo = {
        "chave_idempotencia": str(uuid.uuid4()),
        "itens": [{"produto_id": p["id"], "quantidade": str(q)} for p, q in itens],
        "pagamentos": pagamentos,
        "cliente_id": cliente["id"] if cliente else None,
    }
    resposta = client.post(f"{API}/vendas", json=corpo, headers=farmacia["headers"])
    assert resposta.status_code == esperado, resposta.text
    return resposta.json()


def _detalhe(client, farmacia, convenio):
    resposta = client.get(f"{API}/convenios/{convenio['id']}", headers=farmacia["headers"])
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def test_cadastro_e_funcionario(client, farmacia_a):
    convenio = _convenio(client, farmacia_a, cnpj="11.222.333/0001-81")
    assert (convenio["limite_padrao"], convenio["desconto"], convenio["cnpj"]) == ("100.00", "10.00", "11222333000181")
    _convenio(client, farmacia_a, esperado=422, dia_fechamento=31)
    pedro = _funcionario(client, farmacia_a, convenio)
    _funcionario(client, farmacia_a, convenio, nome="Lúcia Reis", convenio_limite="250,00")
    assert pedro["convenio_matricula"] == "M-01"
    resposta = client.post(f"{API}/clientes", json={"nome": "X", "convenio_id": str(uuid.uuid4())},
                           headers=farmacia_a["headers"])
    assert resposta.status_code == 404

    lista = client.get(f"{API}/convenios", headers=farmacia_a["headers"]).json()
    assert [(c["nome"], c["funcionarios"]) for c in lista] == [("Metalúrgica Silva", 2)]
    pdv = client.get(f"{API}/convenios/cliente/{pedro['id']}", headers=farmacia_a["headers"]).json()
    assert (pdv["nome"], pdv["desconto"], pdv["disponivel"]) == ("Metalúrgica Silva", "10.00", "100.00")
    limites = {f["nome"]: f["limite"] for f in _detalhe(client, farmacia_a, convenio)["funcionarios"]}
    assert limites == {"Lúcia Reis": "250.00", "Pedro Alves": "100.00"}

    # Empresa desativada: o funcionário volta a ser cliente comum.
    client.patch(f"{API}/convenios/{convenio['id']}", json={"ativo": False}, headers=farmacia_a["headers"])
    assert client.get(f"{API}/convenios/cliente/{pedro['id']}", headers=farmacia_a["headers"]).status_code == 404
    assert client.get(f"{API}/convenios", headers=farmacia_a["headers"]).json() == []


def test_venda_no_convenio_com_desconto_e_limite(client, farmacia_a):
    convenio = _convenio(client, farmacia_a)
    pedro = _funcionario(client, farmacia_a, convenio)
    comum = client.post(f"{API}/clientes", json={"nome": "Cliente comum"}, headers=farmacia_a["headers"]).json()
    remedio = _produto(client, farmacia_a, "Losartana", "40.00")
    vitamina = _produto(client, farmacia_a, "Vitamina C", "20.00")
    _promocao(client, farmacia_a, [vitamina], percentual="50")
    _abrir_caixa(client, farmacia_a)

    # 40 + (20 - 10 da promoção) = 50; 10% do convênio = 5; total 45.
    venda = _vender(client, farmacia_a, [(remedio, 1), (vitamina, 1)], [{"forma": "convenio", "valor": "45.00"}], pedro)
    assert (venda["desconto_convenio"], venda["total"]) == ("5.00", "45.00")
    assert client.get(f"{API}/convenios/cliente/{pedro['id']}", headers=farmacia_a["headers"]).json()["disponivel"] == "55.00"

    # Conveniado ganha o desconto mesmo pagando em dinheiro.
    venda = _vender(client, farmacia_a, [(remedio, 1)], [{"forma": "dinheiro", "valor": "36.00"}], pedro)
    assert venda["total"] == "36.00"

    # Limite: sobrou 55.
    erro = _vender(client, farmacia_a, [(remedio, 2)], [{"forma": "convenio", "valor": "72.00"}], pedro, esperado=400)
    assert "disponível R$ 55.00" in erro["detail"]
    # Parte no convênio, parte no Pix.
    _vender(client, farmacia_a, [(remedio, 2)], [{"forma": "convenio", "valor": "55.00"}, {"forma": "pix", "valor": "17.00"}], pedro)
    # Sem cliente, ou cliente fora do convênio, não vende no convênio.
    _vender(client, farmacia_a, [(vitamina, 1)], [{"forma": "convenio", "valor": "10.00"}], esperado=400)
    erro = _vender(client, farmacia_a, [(vitamina, 1)], [{"forma": "convenio", "valor": "10.00"}], comum, esperado=400)
    assert "não é de nenhum convênio" in erro["detail"]

    detalhe = _detalhe(client, farmacia_a, convenio)
    assert detalhe["convenio"]["em_aberto"] == "100.00"
    assert [c["valor"] for c in detalhe["compras_abertas"]] == ["45.00", "55.00"]


def test_fechar_o_mes_cobrar_a_empresa_e_desfazer(client, farmacia_a):
    convenio = _convenio(client, farmacia_a, desconto="0", dias_para_pagar=5)
    pedro = _funcionario(client, farmacia_a, convenio)
    lucia = _funcionario(client, farmacia_a, convenio, nome="Lúcia Reis", convenio_matricula="M-02")
    remedio = _produto(client, farmacia_a, "Losartana", "30.00")
    _abrir_caixa(client, farmacia_a)
    primeira = _vender(client, farmacia_a, [(remedio, 1)], [{"forma": "convenio", "valor": "30.00"}], pedro)
    _vender(client, farmacia_a, [(remedio, 2)], [{"forma": "convenio", "valor": "60.00"}], lucia)
    h = farmacia_a["headers"]

    assert client.post(f"{API}/convenios/{convenio['id']}/fechar",
                       json={"ate": (hoje() + timedelta(days=1)).isoformat()}, headers=h).status_code == 400
    resposta = client.post(f"{API}/convenios/{convenio['id']}/fechar", json={"ate": hoje().isoformat()}, headers=h)
    assert resposta.status_code == 201, resposta.text
    fatura = resposta.json()
    assert (fatura["valor"], fatura["categoria"], fatura["pessoa"]) == ("90.00", "convenio", "Metalúrgica Silva")
    assert fatura["vencimento"] == (hoje() + timedelta(days=5)).isoformat()
    # Nada mais para faturar, e o limite volta para o próximo mês.
    assert client.post(f"{API}/convenios/{convenio['id']}/fechar", json={"ate": hoje().isoformat()},
                       headers=h).status_code == 400
    assert client.get(f"{API}/convenios/cliente/{lucia['id']}", headers=h).json()["disponivel"] == "100.00"

    detalhe = _detalhe(client, farmacia_a, convenio)
    assert detalhe["compras_abertas"] == []
    assert [(f["valor"], f["compras"], f["status"]) for f in detalhe["faturas"]] == [("90.00", 2, "aberta")]
    assert detalhe["convenio"]["a_receber"] == "90.00"

    # A fatura aparece nas contas a receber.
    receber = client.get(f"{API}/financeiro/contas", params={"tipo": "receber"}, headers=h).json()["itens"]
    assert [c["valor"] for c in receber if c["convenio_id"] == convenio["id"]] == ["90.00"]

    extrato = client.get(f"{API}/convenios/{convenio['id']}/extrato", params={"conta_id": fatura["id"]}, headers=h)
    assert extrato.status_code == 200
    linhas = extrato.content.decode("utf-8-sig").splitlines()
    assert "Lúcia Reis;M-02" in linhas[2] and linhas[2].endswith(";60,00")
    assert linhas[-1] == "Total da empresa;;;;90,00"

    # A venda já faturada só cancela depois de desfazer a fatura; a fatura não cancela pelo Financeiro.
    cancelar = {"motivo": "Cliente desistiu"}
    assert client.post(f"{API}/vendas/{primeira['id']}/cancelar", json=cancelar, headers=h).status_code == 409
    assert client.post(f"{API}/financeiro/contas/{fatura['id']}/cancelar", headers=h).status_code == 400
    assert client.post(f"{API}/convenios/faturas/{fatura['id']}/desfazer", headers=h).status_code == 204
    assert [c["valor"] for c in _detalhe(client, farmacia_a, convenio)["compras_abertas"]] == ["30.00", "60.00"]
    assert client.post(f"{API}/vendas/{primeira['id']}/cancelar", json=cancelar, headers=h).status_code == 200
    detalhe = _detalhe(client, farmacia_a, convenio)
    assert [c["valor"] for c in detalhe["compras_abertas"]] == ["60.00"]
    assert detalhe["faturas"] == []
    assert Decimal(detalhe["convenio"]["em_aberto"]) == 60


def test_convenios_sao_de_cada_farmacia(client, farmacia_a, farmacia_b):
    convenio = _convenio(client, farmacia_a)
    assert client.get(f"{API}/convenios", headers=farmacia_b["headers"]).json() == []
    assert client.get(f"{API}/convenios/{convenio['id']}", headers=farmacia_b["headers"]).status_code == 404
    resposta = client.post(f"{API}/clientes", json={"nome": "Intruso", "convenio_id": convenio["id"]},
                           headers=farmacia_b["headers"])
    assert resposta.status_code == 404
