from tests.test_vendas import (
    API,
    _abrir_caixa,
    _login_caixa,
    _produto_com_estoque,
    _venda,
)


def _vender(client, farmacia, produto, forma, valor):
    resposta = client.post(
        f"{API}/vendas", json=_venda(produto["id"], "1", [{"forma": forma, "valor": valor}]), headers=farmacia["headers"]
    )
    assert resposta.status_code == 201, resposta.text


def _movimento(client, headers, caixa_id, tipo, valor, motivo="Teste"):
    return client.post(
        f"{API}/caixas/{caixa_id}/movimentos", json={"tipo": tipo, "valor": valor, "motivo": motivo}, headers=headers
    )


def test_sangria_e_suprimento_mudam_o_dinheiro_esperado(client, farmacia_a):
    produto = _produto_com_estoque(client, farmacia_a, preco="10.00")
    caixa = _abrir_caixa(client, farmacia_a, "50.00")
    _vender(client, farmacia_a, produto, "dinheiro", "10.00")

    suprimento = _movimento(client, farmacia_a["headers"], caixa["id"], "suprimento", "20.00", "Troco do cofre")
    assert suprimento.status_code == 201, suprimento.text
    assert suprimento.json()["dinheiro_esperado"] == "80.00"

    sangria = _movimento(client, farmacia_a["headers"], caixa["id"], "sangria", "60.00", "Cofre")
    assert sangria.status_code == 201, sangria.text
    resumo = sangria.json()
    assert resumo["dinheiro_esperado"] == "20.00"
    assert resumo["suprimentos"] == "20.00"
    assert resumo["sangrias"] == "60.00"
    assert [(m["tipo"], m["motivo"]) for m in resumo["movimentos"]] == [("suprimento", "Troco do cofre"), ("sangria", "Cofre")]
    assert resumo["movimentos"][0]["usuario"]

    # Não dá para tirar mais do que tem na gaveta.
    demais = _movimento(client, farmacia_a["headers"], caixa["id"], "sangria", "20.01")
    assert demais.status_code == 400
    assert "20,00" in demais.json()["detail"]


def test_fechamento_confere_cada_forma(client, farmacia_a):
    produto = _produto_com_estoque(client, farmacia_a, preco="10.00", lotes=(("A", 30, 10),))
    caixa = _abrir_caixa(client, farmacia_a, "0")
    _vender(client, farmacia_a, produto, "dinheiro", "10.00")
    _vender(client, farmacia_a, produto, "debito", "10.00")
    _vender(client, farmacia_a, produto, "credito", "10.00")
    _vender(client, farmacia_a, produto, "credito", "10.00")
    _vender(client, farmacia_a, produto, "pix", "10.00")

    aberto = client.get(f"{API}/caixas/{caixa['id']}", headers=farmacia_a["headers"]).json()
    assert [c["forma"] for c in aberto["conferencia"]] == ["dinheiro", "debito", "credito", "pix"]
    assert all(c["informado"] is None for c in aberto["conferencia"])
    assert aberto["diferenca_total"] is None

    fechado = client.post(
        f"{API}/caixas/{caixa['id']}/fechar",
        json={
            "valor_fechamento_informado": "10.00",
            "conferencia": {"debito": "10.00", "credito": "10.00"},
            "observacao": "Um comprovante de crédito sumiu",
        },
        headers=farmacia_a["headers"],
    )
    assert fechado.status_code == 200, fechado.text
    resumo = fechado.json()
    linhas = {c["forma"]: c for c in resumo["conferencia"]}
    assert linhas["dinheiro"]["diferenca"] == "0.00"
    assert linhas["debito"]["diferenca"] == "0.00"
    assert linhas["credito"]["esperado"] == "20.00"
    assert linhas["credito"]["diferenca"] == "-10.00"
    assert linhas["pix"]["informado"] is None  # não conferido
    assert resumo["diferenca_total"] == "-10.00"
    assert resumo["caixa"]["observacao_fechamento"] == "Um comprovante de crédito sumiu"

    # Fechado, não aceita mais sangria.
    assert _movimento(client, farmacia_a["headers"], caixa["id"], "sangria", "1.00").status_code == 409


def test_fechamento_antigo_sem_conferencia_continua_valendo(client, farmacia_a):
    caixa = _abrir_caixa(client, farmacia_a, "30.00")
    resumo = client.post(
        f"{API}/caixas/{caixa['id']}/fechar", json={"valor_fechamento_informado": "30.00"}, headers=farmacia_a["headers"]
    ).json()
    assert resumo["diferenca"] == "0.00"
    assert [c["forma"] for c in resumo["conferencia"]] == ["dinheiro"]
    assert resumo["caixa"]["observacao_fechamento"] is None


def test_operador_so_mexe_no_proprio_caixa(client, engine_dono, farmacia_a):
    caixa = _abrir_caixa(client, farmacia_a, "50.00")  # aberto pelo admin
    headers = _login_caixa(client, engine_dono, farmacia_a)
    assert _movimento(client, headers, caixa["id"], "sangria", "10.00").status_code == 403
    # E o relatório do dia é só para a gerência.
    assert client.get(f"{API}/caixas/relatorio", headers=headers).status_code == 403


def test_relatorio_do_dia_soma_os_caixas(client, farmacia_a):
    produto = _produto_com_estoque(client, farmacia_a, preco="10.00", lotes=(("A", 30, 10),))
    caixa = _abrir_caixa(client, farmacia_a, "100.00")
    _vender(client, farmacia_a, produto, "dinheiro", "10.00")
    _vender(client, farmacia_a, produto, "pix", "10.00")
    _movimento(client, farmacia_a["headers"], caixa["id"], "sangria", "50.00", "Cofre")
    client.post(
        f"{API}/caixas/{caixa['id']}/fechar",
        json={"valor_fechamento_informado": "55.00", "conferencia": {"pix": "10.00"}},
        headers=farmacia_a["headers"],
    )
    # Um segundo caixa fechado sem conferir o Pix.
    _abrir_caixa(client, farmacia_a, "0")
    segundo = client.get(f"{API}/caixas/atual", headers=farmacia_a["headers"]).json()["caixa"]
    _vender(client, farmacia_a, produto, "pix", "10.00")
    client.post(
        f"{API}/caixas/{segundo['id']}/fechar", json={"valor_fechamento_informado": "0"}, headers=farmacia_a["headers"]
    )
    # Um terceiro no mesmo PDV, ainda aberto.
    _abrir_caixa(client, farmacia_a, "20.00")
    _vender(client, farmacia_a, produto, "debito", "10.00")

    relatorio = client.get(f"{API}/caixas/relatorio", headers=farmacia_a["headers"])
    assert relatorio.status_code == 200, relatorio.text
    dia = relatorio.json()
    assert len(dia["caixas"]) == 3
    assert dia["abertos"] == 1
    assert dia["quantidade_vendas"] == 4
    assert dia["total_vendido"] == "40.00"
    assert dia["por_forma"] == {"dinheiro": "10.00", "pix": "20.00", "debito": "10.00"}
    assert dia["sangrias"] == "50.00"
    linhas = {c["forma"]: c for c in dia["conferencia"]}  # só do caixa fechado
    assert linhas["dinheiro"]["esperado"] == "60.00"
    assert linhas["dinheiro"]["diferenca"] == "-5.00"
    assert linhas["pix"]["esperado"] == "20.00"
    assert linhas["pix"]["informado"] == "10.00"
    assert linhas["pix"]["sem_conferir"] == "10.00"  # o segundo caixa não conferiu o Pix
    assert linhas["pix"]["diferenca"] == "0.00"
    assert "debito" not in linhas
    assert dia["diferenca_total"] == "-5.00"

    outro_dia = client.get(f"{API}/caixas/relatorio?dia=2020-01-01", headers=farmacia_a["headers"]).json()
    assert outro_dia["caixas"] == []
    assert outro_dia["diferenca_total"] == "0"
