import uuid
from datetime import timedelta

from app.shared.datas import hoje
from tests.test_promocoes_relatorios import _produto
from tests.test_vendas import _abrir_caixa

API = "/api/v1"
MES = f"{hoje():%Y-%m}"


def _do_programa(client, farmacia, nome, preco, valor):
    produto = _produto(client, farmacia, nome, preco)
    resposta = client.patch(f"{API}/produtos/{produto['id']}", json={"popular_valor": valor},
                            headers=farmacia["headers"])
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def _dados(autorizacao="123456789", cpf="529.982.247-25", **extra):
    return {
        "paciente_cpf": cpf, "paciente_nome": "Maria Souza", "prescritor_crm": "12345", "prescritor_uf": "sp",
        "receita_data": (hoje() - timedelta(days=10)).isoformat(), "autorizacao": autorizacao, **extra,
    }


def _vender(client, farmacia, itens, pagamentos, popular=None, esperado=201):
    corpo = {
        "chave_idempotencia": str(uuid.uuid4()),
        "itens": [{"produto_id": p["id"], "quantidade": str(q)} for p, q in itens],
        "pagamentos": pagamentos,
        "popular": popular,
    }
    resposta = client.post(f"{API}/vendas", json=corpo, headers=farmacia["headers"])
    assert resposta.status_code == esperado, resposta.text
    return resposta.json()


def _mes(client, farmacia):
    resposta = client.get(f"{API}/popular", params={"mes": MES}, headers=farmacia["headers"])
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def test_venda_com_a_parte_do_governo(client, farmacia_a):
    losartana = _do_programa(client, farmacia_a, "Losartana 50mg", "25.00", "18.40")
    metformina = _do_programa(client, farmacia_a, "Metformina 850mg", "9.00", "12.00")
    vitamina = _produto(client, farmacia_a, "Vitamina C", "20.00")
    _abrir_caixa(client, farmacia_a)

    # Losartana: governo paga 18,40 e o paciente 6,60. Metformina: preço menor que o valor, governo paga 9.
    # Vitamina fora do programa: o paciente paga tudo. Governo 27,40; paciente 26,60.
    venda = _vender(
        client, farmacia_a, [(losartana, 1), (metformina, 1), (vitamina, 1)],
        [{"forma": "popular", "valor": "27.40"}, {"forma": "dinheiro", "valor": "30.00"}], _dados(),
    )
    assert (venda["total"], venda["troco"], venda["cliente_cpf"]) == ("54.00", "3.40", "52998224725")

    registro = client.get(f"{API}/popular/venda/{venda['id']}", headers=farmacia_a["headers"]).json()
    assert (registro["valor_governo"], registro["valor_paciente"], registro["prescritor_uf"]) == ("27.40", "26.60", "SP")
    assert [(i["descricao"], i["governo"]) for i in registro["itens"]] == [("Losartana 50mg", "18.40"),
                                                                           ("Metformina 850mg", "9.00")]

    # Valor errado na parte do governo.
    erro = _vender(client, farmacia_a, [(losartana, 1)], [{"forma": "popular", "valor": "25.00"}],
                   _dados("9999", cpf="111.444.777-35"), esperado=400)
    assert "R$ 18.40" in erro["detail"]
    # Sem os dados, ou sem remédio do programa.
    _vender(client, farmacia_a, [(losartana, 1)], [{"forma": "popular", "valor": "18.40"}], esperado=400)
    erro = _vender(client, farmacia_a, [(vitamina, 1)], [{"forma": "dinheiro", "valor": "20.00"}],
                   _dados("9998", cpf="111.444.777-35"), esperado=400)
    assert "Nenhum remédio" in erro["detail"]
    # Receita vencida (mais de 180 dias) e receita do futuro.
    velha = (hoje() - timedelta(days=181)).isoformat()
    erro = _vender(client, farmacia_a, [(losartana, 1)], [{"forma": "popular", "valor": "18.40"},
                   {"forma": "pix", "valor": "6.60"}], _dados("9997", cpf="111.444.777-35", receita_data=velha),
                   esperado=400)
    assert "venceu" in erro["detail"]
    amanha = (hoje() + timedelta(days=1)).isoformat()
    _vender(client, farmacia_a, [(losartana, 1)], [{"forma": "popular", "valor": "18.40"},
            {"forma": "pix", "valor": "6.60"}], _dados("9996", cpf="111.444.777-35", receita_data=amanha), esperado=400)
    # A mesma autorização não vale duas vezes.
    erro = _vender(client, farmacia_a, [(losartana, 1)], [{"forma": "popular", "valor": "18.40"},
                   {"forma": "pix", "valor": "6.60"}], _dados(cpf="111.444.777-35"), esperado=409)
    assert f"venda nº {venda['numero']}" in erro["detail"]


def test_paciente_so_leva_de_novo_depois_do_intervalo(client, farmacia_a):
    losartana = _do_programa(client, farmacia_a, "Losartana 50mg", "18.00", "18.40")
    metformina = _do_programa(client, farmacia_a, "Metformina 850mg", "9.00", "12.00")
    _abrir_caixa(client, farmacia_a)
    _vender(client, farmacia_a, [(losartana, 1)], [{"forma": "popular", "valor": "18.00"}], _dados("1001"))

    erro = _vender(client, farmacia_a, [(losartana, 1)], [{"forma": "popular", "valor": "18.00"}], _dados("1002"),
                   esperado=400)
    volta = hoje() + timedelta(days=30)
    assert f"a partir de {volta:%d/%m/%Y}" in erro["detail"]
    # Outro remédio, ou outro paciente, pode.
    _vender(client, farmacia_a, [(metformina, 1)], [{"forma": "popular", "valor": "9.00"}], _dados("1003"))
    _vender(client, farmacia_a, [(losartana, 1)], [{"forma": "popular", "valor": "18.00"}],
            _dados("1004", cpf="111.444.777-35"))
    # Com o intervalo desligado, a farmácia confia só no autorizador do governo.
    client.patch(f"{API}/configuracoes", json={"popular_intervalo_dias": 0}, headers=farmacia_a["headers"])
    _vender(client, farmacia_a, [(losartana, 1)], [{"forma": "popular", "valor": "18.00"}], _dados("1005"))


def test_lancar_o_mes_no_financeiro_e_desfazer(client, farmacia_a):
    losartana = _do_programa(client, farmacia_a, "Losartana 50mg", "25.00", "18.40")
    _abrir_caixa(client, farmacia_a)
    h = farmacia_a["headers"]
    primeira = _vender(client, farmacia_a, [(losartana, 1)],
                       [{"forma": "popular", "valor": "18.40"}, {"forma": "dinheiro", "valor": "6.60"}], _dados("2001"))
    _vender(client, farmacia_a, [(losartana, 2)],
            [{"forma": "popular", "valor": "36.80"}, {"forma": "pix", "valor": "13.20"}],
            _dados("2002", cpf="111.444.777-35"))

    mes = _mes(client, farmacia_a)
    assert (mes["quantidade"], mes["pacientes"], mes["total_governo"], mes["em_aberto"]) == (2, 2, "55.20", "55.20")
    assert mes["pode_lancar"] and mes["lancamentos"] == []

    resposta = client.post(f"{API}/popular/lancar", json={"mes": MES}, headers=h)
    assert resposta.status_code == 201, resposta.text
    conta = resposta.json()
    assert (conta["valor"], conta["categoria"], conta["pessoa"]) == ("55.20", "popular", "Ministério da Saúde")
    assert conta["vencimento"] > hoje().isoformat()
    assert client.post(f"{API}/popular/lancar", json={"mes": MES}, headers=h).status_code == 400
    mes = _mes(client, farmacia_a)
    assert (mes["em_aberto"], mes["pode_lancar"], len(mes["lancamentos"])) == ("0", False, 1)
    assert {v["status"] for v in mes["vendas"]} == {"lancada"}

    # Planilha do mês.
    planilha = client.get(f"{API}/popular/planilha", params={"mes": MES}, headers=h)
    linhas = planilha.content.decode("utf-8-sig").splitlines()
    assert "2002" in linhas[2] and "111.444.777-35" in linhas[2] and "2 Losartana 50mg" in linhas[2]
    assert linhas[-1].startswith("Total;") and ";55,20;" in linhas[-1]

    # O valor não muda pelo Financeiro, nem dá para lançar Farmácia Popular à mão.
    assert client.patch(f"{API}/financeiro/contas/{conta['id']}", json={"valor": "10.00"}, headers=h).status_code == 400
    assert client.post(f"{API}/financeiro/contas/{conta['id']}/cancelar", headers=h).status_code == 400
    manual = {"tipo": "receber", "descricao": "Repasse do governo", "categoria": "popular", "valor_total": "1.00",
              "primeiro_vencimento": hoje().isoformat()}
    assert client.post(f"{API}/financeiro/contas", json=manual, headers=h).status_code == 400

    # Venda já lançada só cancela depois de desfazer o lançamento.
    cancelar = {"motivo": "Paciente desistiu"}
    assert client.post(f"{API}/vendas/{primeira['id']}/cancelar", json=cancelar, headers=h).status_code == 409
    assert client.post(f"{API}/popular/lancamentos/{conta['id']}/desfazer", headers=h).status_code == 204
    assert client.post(f"{API}/vendas/{primeira['id']}/cancelar", json=cancelar, headers=h).status_code == 200
    mes = _mes(client, farmacia_a)
    assert (mes["quantidade"], mes["em_aberto"]) == (1, "36.80")
    # Cancelada, a autorização pode ser usada de novo.
    _vender(client, farmacia_a, [(losartana, 1)],
            [{"forma": "popular", "valor": "18.40"}, {"forma": "dinheiro", "valor": "6.60"}],
            _dados("2001", cpf="111.444.777-35"), esperado=400)  # mesmo paciente e remédio dentro do intervalo


def test_popular_e_de_cada_farmacia(client, farmacia_a, farmacia_b):
    losartana = _do_programa(client, farmacia_a, "Losartana 50mg", "25.00", "18.40")
    _abrir_caixa(client, farmacia_a)
    venda = _vender(client, farmacia_a, [(losartana, 1)],
                    [{"forma": "popular", "valor": "18.40"}, {"forma": "dinheiro", "valor": "6.60"}], _dados())
    assert _mes(client, farmacia_b)["quantidade"] == 0
    assert client.get(f"{API}/popular/venda/{venda['id']}", headers=farmacia_b["headers"]).status_code == 404
