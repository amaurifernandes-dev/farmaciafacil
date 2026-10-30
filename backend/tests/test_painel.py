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
