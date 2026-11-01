from datetime import timedelta

from sqlalchemy import text

from app.shared.datas import hoje
from tests.test_vendas import API, _abrir_caixa, _produto_com_estoque, _venda


def test_painel_vazio(client, farmacia_a):
    resposta = client.get(f"{API}/painel", headers=farmacia_a["headers"])
    assert resposta.status_code == 200, resposta.text
    painel = resposta.json()
    assert painel["farmacia"] == "Farmácia 11111111000111"
    assert painel["quantidade_vendas_hoje"] == 0
    assert painel["ticket_medio_hoje"] == "0"
    assert len(painel["semana"]) == 7
    assert painel["semana"][-1]["data"] == hoje().isoformat()
    assert painel["meu_caixa_aberto"] is False


def test_painel_com_vendas(client, engine_dono, farmacia_a, farmacia_b):
    produto = _produto_com_estoque(client, farmacia_a, lotes=(("A", 20, 10),))
    _abrir_caixa(client, farmacia_a)
    for _ in range(2):
        client.post(f"{API}/vendas", json=_venda(produto["id"]), headers=farmacia_a["headers"])
    cancelada = client.post(f"{API}/vendas", json=_venda(produto["id"]), headers=farmacia_a["headers"]).json()
    client.post(f"{API}/vendas/{cancelada['id']}/cancelar", json={"motivo": "Erro"}, headers=farmacia_a["headers"])
    ontem = client.post(f"{API}/vendas", json=_venda(produto["id"]), headers=farmacia_a["headers"]).json()
    with engine_dono.begin() as conexao:
        conexao.execute(
            text("UPDATE vendas SET finalizada_em = finalizada_em - interval '1 day' WHERE id = :id"),
            {"id": ontem["id"]},
        )

    painel = client.get(f"{API}/painel", headers=farmacia_a["headers"]).json()
    assert painel["vendas_hoje"] == "17.80"
    assert painel["quantidade_vendas_hoje"] == 2
    assert painel["ticket_medio_hoje"] == "8.90"
    assert painel["vendas_ontem"] == "8.90"
    assert painel["semana"][-2] == {"data": (hoje() - timedelta(days=1)).isoformat(), "total": "8.90", "quantidade": 1}
    assert painel["caixas_abertos"] == 1
    assert painel["meu_caixa_aberto"] is True
    assert painel["produtos_ativos"] == 1
    assert painel["lotes_vencendo"] == 1

    outra = client.get(f"{API}/painel", headers=farmacia_b["headers"]).json()
    assert outra["quantidade_vendas_hoje"] == 0
    assert outra["caixas_abertos"] == 0


def _entrar(client, farmacia, papel, email):
    dados = {"nome": papel.title(), "email": email, "papel": papel, "senha": "senha-boa-123"}
    assert client.post(f"{API}/usuarios", json=dados, headers=farmacia["headers"]).status_code == 201
    login = client.post(f"{API}/auth/login", json={"email": email, "senha": dados["senha"]}).json()
    return {"headers": {"Authorization": f"Bearer {login['access_token']}"}}


def test_cada_perfil_ve_o_seu_bloco(client, farmacia_a):
    h = farmacia_a["headers"]
    produto = _produto_com_estoque(client, farmacia_a, lotes=(("A", 20, 3),))
    client.patch(f"{API}/produtos/{produto['id']}", json={"estoque_minimo": "10"}, headers=h)
    _abrir_caixa(client, farmacia_a)
    client.post(f"{API}/vendas", json=_venda(produto["id"]), headers=h)
    pre = client.post(f"{API}/pre-vendas", json={"itens": [{"produto_id": produto["id"], "quantidade": "1"}]}, headers=h)
    assert pre.status_code == 201, pre.text

    # Administrador: vê todos os blocos.
    admin = client.get(f"{API}/painel", headers=h).json()
    balcao = admin["balcao"]
    assert balcao["meu_caixa"]["vendas"] == 1 and balcao["meu_caixa"]["total"] == "8.90"
    assert balcao["pre_vendas_abertas"] == 1 and balcao["pre_vendas"][0]["numero"] == pre.json()["numero"]
    assert balcao["minhas_vendas_hoje"] == {"quantidade": 1, "total": "8.90"}
    estoque = admin["estoque"]
    assert [(p["nome"], p["saldo"]) for p in estoque["repor"]] == [("Dipirona 500mg", "2.000")]
    assert estoque["vencendo"][0]["numero_lote"] == "A" and estoque["vencendo"][0]["dias_para_vencer"] == 20
    assert (estoque["notas_para_conferir"], estoque["pedidos_compra_abertos"]) == (0, 0)
    assert admin["farmacia_bloco"] == {"controlados_hoje": 0, "atendimentos_hoje": 0}
    assert admin["gestao"]["pagar_vencidas"] == {"quantidade": 0, "total": "0"}

    # Caixa: só o balcão (o caixa dela está fechado e ela não vendeu).
    caixa = client.get(f"{API}/painel", headers=_entrar(client, farmacia_a, "caixa", "julia@f.com")["headers"]).json()
    assert caixa["balcao"]["meu_caixa"] is None
    assert caixa["balcao"]["pre_vendas_abertas"] == 1
    assert caixa["balcao"]["minhas_vendas_hoje"]["quantidade"] == 0
    assert (caixa["estoque"], caixa["farmacia_bloco"], caixa["gestao"]) == (None, None, None)

    # Estoque: só o bloco de estoque.
    estoquista = client.get(f"{API}/painel", headers=_entrar(client, farmacia_a, "estoque", "eva@f.com")["headers"]).json()
    assert estoquista["estoque"]["repor"][0]["nome"] == "Dipirona 500mg"
    assert (estoquista["balcao"], estoquista["farmacia_bloco"], estoquista["gestao"]) == (None, None, None)

    # Farmacêutico: balcão, estoque e farmácia, sem as contas.
    farma = client.get(f"{API}/painel", headers=_entrar(client, farmacia_a, "farmaceutico", "fe@f.com")["headers"]).json()
    assert farma["balcao"] and farma["estoque"] and farma["farmacia_bloco"] and farma["gestao"] is None


def test_contas_vencidas_no_painel_do_gerente(client, farmacia_a):
    h = farmacia_a["headers"]
    ontem = (hoje() - timedelta(days=1)).isoformat()
    for vencimento, valor in ((ontem, "100.00"), (hoje().isoformat(), "40.00")):
        conta = {"tipo": "pagar", "descricao": "Aluguel", "categoria": "aluguel", "valor_total": valor,
                 "primeiro_vencimento": vencimento}
        resposta = client.post(f"{API}/financeiro/contas", json=conta, headers=h)
        assert resposta.status_code == 201, resposta.text
    gestao = client.get(f"{API}/painel", headers=h).json()["gestao"]
    assert gestao["pagar_vencidas"] == {"quantidade": 1, "total": "100.00"}
    assert gestao["pagar_hoje"] == {"quantidade": 1, "total": "40.00"}
