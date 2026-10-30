import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.security import gerar_hash_senha
from app.modules.auth.models import Usuario
from app.shared.datas import hoje
from tests.test_compras import _det, _importar, _validade, _xml
from tests.test_nfce import _configurar, sefaz  # noqa: F401
from tests.test_nfce import _produto as _produto_nfce
from tests.test_vendas import _abrir_caixa, _produto_com_estoque

API = "/api/v1"


def _conta(client, farmacia, **dados) -> list[dict]:
    corpo = {
        "tipo": "pagar",
        "descricao": "Aluguel da loja",
        "categoria": "aluguel",
        "valor_total": "1000.00",
        "primeiro_vencimento": (hoje() + timedelta(days=5)).isoformat(),
        **dados,
    }
    resposta = client.post(f"{API}/financeiro/contas", json=corpo, headers=farmacia["headers"])
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _listar(client, farmacia, tipo="pagar", **filtros) -> dict:
    resposta = client.get(f"{API}/financeiro/contas", params={"tipo": tipo, **filtros}, headers=farmacia["headers"])
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def _cliente(client, farmacia, nome="João da Silva", limite=None) -> dict:
    resposta = client.post(f"{API}/clientes", json={"nome": nome, "limite_credito": limite}, headers=farmacia["headers"])
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _vender(client, farmacia, produto, pagamentos, quantidade="1", **extra):
    corpo = {
        "chave_idempotencia": str(uuid.uuid4()),
        "itens": [{"produto_id": produto["id"], "quantidade": quantidade}],
        "pagamentos": pagamentos,
        **extra,
    }
    return client.post(f"{API}/vendas", json=corpo, headers=farmacia["headers"])


def test_conta_parcelada_divide_valor_e_vence_mes_a_mes(client, farmacia_a):
    inicio = hoje().replace(day=31) if hoje().month in (1, 3, 5, 7, 8, 10, 12) else hoje()
    contas = _conta(client, farmacia_a, valor_total="100.00", parcelas=3, primeiro_vencimento=inicio.isoformat())
    assert [Decimal(c["valor"]) for c in contas] == [Decimal("33.34"), Decimal("33.33"), Decimal("33.33")]
    assert [(c["parcela"], c["parcelas"]) for c in contas] == [(1, 3), (2, 3), (3, 3)]
    assert contas[0]["vencimento"] == inicio.isoformat()
    # O mês seguinte pode não ter o mesmo dia: usa o último.
    assert contas[1]["vencimento"][:7] != contas[0]["vencimento"][:7]


def test_categoria_invalida(client, farmacia_a):
    corpo = {"tipo": "receber", "descricao": "Sala", "categoria": "aluguel", "valor_total": "1",
             "primeiro_vencimento": hoje().isoformat()}
    assert client.post(f"{API}/financeiro/contas", json=corpo, headers=farmacia_a["headers"]).status_code == 400


def test_pagar_estornar_e_cancelar(client, farmacia_a):
    vencida = _conta(client, farmacia_a, descricao="Conta de luz", categoria="contas_consumo", valor_total="250.00",
                     primeiro_vencimento=(hoje() - timedelta(days=3)).isoformat())[0]
    _conta(client, farmacia_a, valor_total="1000.00")

    pagina = _listar(client, farmacia_a)
    assert pagina["total"] == 2
    assert Decimal(pagina["soma"]) == 1250
    assert Decimal(pagina["totais"]["vencidas"]) == 250
    assert pagina["totais"]["quantidade_vencidas"] == 1
    assert Decimal(pagina["totais"]["proximos_7_dias"]) == 1000
    assert pagina["itens"][0]["vencida"] is True

    assert [c["descricao"] for c in _listar(client, farmacia_a, situacao="vencidas")["itens"]] == ["Conta de luz"]
    assert _listar(client, farmacia_a, busca="luz")["total"] == 1

    baixa = client.post(f"{API}/financeiro/contas/{vencida['id']}/baixar",
                        json={"forma_pagamento": "pix", "valor_pago": "255.10"}, headers=farmacia_a["headers"])
    assert baixa.status_code == 200, baixa.text
    assert (baixa.json()["status"], baixa.json()["valor_pago"], baixa.json()["pago_em"]) == ("paga", "255.10", hoje().isoformat())
    assert Decimal(_listar(client, farmacia_a)["totais"]["pago_no_mes"]) == Decimal("255.10")
    assert _listar(client, farmacia_a, situacao="pagas")["total"] == 1

    # Não paga duas vezes; o estorno volta para aberta.
    repetida = client.post(f"{API}/financeiro/contas/{vencida['id']}/baixar", json={"forma_pagamento": "pix"},
                           headers=farmacia_a["headers"])
    assert repetida.status_code == 409
    estorno = client.post(f"{API}/financeiro/contas/{vencida['id']}/estornar", headers=farmacia_a["headers"])
    assert (estorno.json()["status"], estorno.json()["valor_pago"]) == ("aberta", None)

    cancelada = client.post(f"{API}/financeiro/contas/{vencida['id']}/cancelar", headers=farmacia_a["headers"])
    assert cancelada.json()["status"] == "cancelada"
    assert _listar(client, farmacia_a)["total"] == 1

    # Ajuste de vencimento numa conta aberta.
    aberta = _listar(client, farmacia_a)["itens"][0]
    nova = (hoje() + timedelta(days=10)).isoformat()
    ajuste = client.patch(f"{API}/financeiro/contas/{aberta['id']}", json={"vencimento": nova}, headers=farmacia_a["headers"])
    assert ajuste.json()["vencimento"] == nova


def test_caixa_recebe_mas_nao_paga(client, engine_dono, farmacia_a):
    with Session(engine_dono) as db:
        db.add(Usuario(farmacia_id=farmacia_a["id"], nome="Caixa", email="caixa@a.com",
                       senha_hash=gerar_hash_senha("senha-forte"), papel="caixa"))
        db.commit()
    token = client.post(f"{API}/auth/login", json={"email": "caixa@a.com", "senha": "senha-forte"}).json()["access_token"]
    caixa = {"Authorization": f"Bearer {token}"}

    pagar = _conta(client, farmacia_a)[0]
    receber = _conta(client, farmacia_a, tipo="receber", categoria="outras", descricao="Aluguel de sala")[0]
    assert client.get(f"{API}/financeiro/contas", params={"tipo": "pagar"}, headers=caixa).status_code == 403
    assert client.post(f"{API}/financeiro/contas/{pagar['id']}/baixar", json={"forma_pagamento": "pix"},
                       headers=caixa).status_code == 403
    assert client.post(f"{API}/financeiro/contas/{receber['id']}/baixar", json={"forma_pagamento": "pix"},
                       headers=caixa).status_code == 200


def test_nota_de_compra_vira_contas_a_pagar(client, farmacia_a):
    client.post(f"{API}/produtos", json={"nome": "Dipirona", "preco_venda": "5", "ean": "7891234567895"},
                headers=farmacia_a["headers"])
    v1, v2 = (hoje() + timedelta(days=28)).isoformat(), (hoje() + timedelta(days=56)).isoformat()
    cobranca = (f"<cobr><dup><nDup>001</nDup><dVenc>{v1}</dVenc><vDup>60.00</vDup></dup>"
                f"<dup><nDup>002</nDup><dVenc>{v2}</dVenc><vDup>40.00</vDup></dup></cobr>")
    xml = _xml(_det(1, "A1", "7891234567895", "DIPIRONA", "10", "10.00", unidade="UN",
                    lotes=[("L1", 10, _validade())])).replace("<total>", cobranca + "<total>")
    nota = _importar(client, farmacia_a, xml).json()
    # Enquanto a nota não é confirmada, não há conta.
    assert _listar(client, farmacia_a)["total"] == 0
    client.post(f"{API}/compras/notas/{nota['id']}/confirmar", headers=farmacia_a["headers"])

    contas = _listar(client, farmacia_a)["itens"]
    assert [(c["documento"], c["vencimento"], c["valor"], c["parcela"], c["parcelas"]) for c in contas] == [
        ("001", v1, "60.00", 1, 2),
        ("002", v2, "40.00", 2, 2),
    ]
    assert all(c["categoria"] == "fornecedores" and c["pessoa"] == "DistriSaúde" for c in contas)
    assert contas[0]["nota_entrada_id"] == nota["id"]


def test_nota_sem_parcelas_vira_uma_conta(client, farmacia_a):
    client.post(f"{API}/produtos", json={"nome": "Dipirona", "preco_venda": "5", "ean": "7891234567895"},
                headers=farmacia_a["headers"])
    nota = _importar(client, farmacia_a, _xml(_det(1, "A1", "7891234567895", "DIPIRONA", "1", "10.00", unidade="UN",
                                                 lotes=[("L1", 1, _validade())]))).json()
    client.post(f"{API}/compras/notas/{nota['id']}/confirmar", headers=farmacia_a["headers"])
    contas = _listar(client, farmacia_a)["itens"]
    assert [(c["valor"], c["vencimento"]) for c in contas] == [("100.00", "2026-10-28")]


def test_venda_a_prazo(client, farmacia_a):
    produto = _produto_com_estoque(client, farmacia_a, preco="30.00", lotes=(("A", 90, 10),))
    sem_limite = _cliente(client, farmacia_a, nome="Sem limite")
    joao = _cliente(client, farmacia_a, limite="50.00")
    _abrir_caixa(client, farmacia_a)
    prazo = [{"forma": "prazo", "valor": "30.00"}]

    assert _vender(client, farmacia_a, produto, prazo).status_code == 400  # sem cliente
    assert _vender(client, farmacia_a, produto, prazo, cliente_id=sem_limite["id"]).status_code == 400

    venda = _vender(client, farmacia_a, produto, prazo, cliente_id=joao["id"])
    assert venda.status_code == 201, venda.text
    assert venda.json()["cliente_id"] == joao["id"]

    credito = client.get(f"{API}/financeiro/clientes/{joao['id']}/credito", headers=farmacia_a["headers"]).json()
    assert (Decimal(credito["em_aberto"]), Decimal(credito["disponivel"])) == (30, 20)
    conta = credito["contas"][0]
    assert conta["vencimento"] == (hoje() + timedelta(days=30)).isoformat()
    assert (conta["categoria"], conta["venda_id"]) == ("venda_prazo", venda.json()["id"])

    # Passa do limite: recusa e não baixa estoque.
    recusada = _vender(client, farmacia_a, produto, prazo, cliente_id=joao["id"])
    assert recusada.status_code == 400
    assert "disponível R$ 20.00" in recusada.json()["detail"]

    # Parte a prazo, parte em dinheiro, com vencimento escolhido.
    vencimento = (hoje() + timedelta(days=10)).isoformat()
    misto = _vender(client, farmacia_a, produto, [{"forma": "prazo", "valor": "20.00", "vencimento": vencimento},
                                                   {"forma": "dinheiro", "valor": "10.00"}], cliente_id=joao["id"])
    assert misto.status_code == 201, misto.text
    credito = client.get(f"{API}/financeiro/clientes/{joao['id']}/credito", headers=farmacia_a["headers"]).json()
    assert Decimal(credito["disponivel"]) == 0

    # Cancelar a venda cancela o fiado e libera o limite.
    cancelar = client.post(f"{API}/vendas/{venda.json()['id']}/cancelar", json={"motivo": "desistiu"},
                           headers=farmacia_a["headers"])
    assert cancelar.status_code == 200, cancelar.text
    credito = client.get(f"{API}/financeiro/clientes/{joao['id']}/credito", headers=farmacia_a["headers"]).json()
    assert Decimal(credito["disponivel"]) == 30


def test_fiado_recebido_em_dinheiro_entra_no_caixa(client, farmacia_a):
    produto = _produto_com_estoque(client, farmacia_a, preco="30.00", lotes=(("A", 90, 10),))
    joao = _cliente(client, farmacia_a, limite="100.00")
    _abrir_caixa(client, farmacia_a, valor="50.00")
    venda = _vender(client, farmacia_a, produto, [{"forma": "prazo", "valor": "30.00"}], cliente_id=joao["id"]).json()
    conta = client.get(f"{API}/financeiro/clientes/{joao['id']}/credito", headers=farmacia_a["headers"]).json()["contas"][0]

    # Com a conta do fiado recebida, a venda não pode mais ser cancelada sem estornar.
    baixa = client.post(f"{API}/financeiro/contas/{conta['id']}/baixar", json={"forma_pagamento": "dinheiro"},
                        headers=farmacia_a["headers"])
    assert baixa.status_code == 200, baixa.text
    resumo = client.get(f"{API}/caixas/atual", headers=farmacia_a["headers"]).json()
    assert Decimal(resumo["recebimentos_dinheiro"]) == 30
    assert Decimal(resumo["dinheiro_esperado"]) == 80
    assert Decimal(resumo["por_forma"]["prazo"]) == 30

    cancelar = client.post(f"{API}/vendas/{venda['id']}/cancelar", json={"motivo": "erro"}, headers=farmacia_a["headers"])
    assert cancelar.status_code == 409


def test_fluxo_de_caixa(client, farmacia_a):
    produto = _produto_com_estoque(client, farmacia_a, preco="10.00", lotes=(("A", 90, 10),))
    joao = _cliente(client, farmacia_a, limite="100.00")
    _abrir_caixa(client, farmacia_a)
    # 20 em dinheiro para uma venda de 10: troco de 10, entra 10.
    _vender(client, farmacia_a, produto, [{"forma": "dinheiro", "valor": "20.00"}])
    _vender(client, farmacia_a, produto, [{"forma": "prazo", "valor": "10.00"}], cliente_id=joao["id"])
    _conta(client, farmacia_a, valor_total="300.00", primeiro_vencimento=(hoje() + timedelta(days=2)).isoformat())
    _conta(client, farmacia_a, valor_total="40.00", descricao="Conta atrasada",
           primeiro_vencimento=(hoje() - timedelta(days=5)).isoformat())

    fluxo = client.get(f"{API}/financeiro/fluxo", params={"inicio": hoje().isoformat()}, headers=farmacia_a["headers"])
    assert fluxo.status_code == 200, fluxo.text
    corpo = fluxo.json()
    assert len(corpo["dias"]) == 30
    dia0, _, dia2 = corpo["dias"][:3]
    assert Decimal(dia0["vendas"]) == 10
    assert Decimal(dia2["previsto_pagar"]) == 300
    # O fiado vence em 30 dias, fora do período padrão (hoje até hoje + 29).
    assert Decimal(corpo["vencido_pagar"]) == 40
    assert Decimal(corpo["resultado"]) == -290
    assert Decimal(corpo["dias"][-1]["acumulado"]) == -290


def test_contas_de_outra_farmacia_nao_aparecem(client, farmacia_a, farmacia_b):
    conta = _conta(client, farmacia_a)[0]
    assert _listar(client, farmacia_b)["total"] == 0
    assert client.get(f"{API}/financeiro/contas/{conta['id']}", headers=farmacia_b["headers"]).status_code == 404


def test_nfce_da_venda_a_prazo_usa_credito_loja(client, farmacia_a, sefaz):
    _configurar(client, farmacia_a)
    produto = _produto_nfce(client, farmacia_a)  # R$ 10,00, com NCM
    joao = _cliente(client, farmacia_a, limite="100.00")
    _abrir_caixa(client, farmacia_a)
    venda = _vender(client, farmacia_a, produto, [{"forma": "prazo", "valor": "10.00"}], cliente_id=joao["id"]).json()
    assert venda["nota"]["status"] == "autorizada"
    assert sefaz.enviadas[venda["id"]]["formas_pagamento"] == [{"forma_pagamento": "05", "valor_pagamento": "10.00"}]
