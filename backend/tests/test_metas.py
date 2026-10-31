import calendar
from datetime import date, timedelta
from decimal import Decimal

from app.modules.metas.service import _andamento, _dias
from app.shared.datas import hoje
from tests.test_comissoes import _atendente, _vender
from tests.test_promocoes_relatorios import _produto
from tests.test_vendas import _abrir_caixa

API = "/api/v1"
ZERO = Decimal(0)


def _metas(client, farmacia, **params):
    resposta = client.get(f"{API}/metas", params=params, headers=farmacia["headers"])
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def _salvar(client, farmacia, esperado=200, **corpo):
    corpo.setdefault("mes", hoje().replace(day=1).isoformat())
    resposta = client.put(f"{API}/metas", json=corpo, headers=farmacia["headers"])
    assert resposta.status_code == esperado, resposta.text
    return resposta.json()


def test_andamento_no_meio_do_mes():
    dias = _dias(date(2026, 10, 1), date(2026, 10, 10))
    assert dias == (31, 10, 22)
    # Vendeu 3.000 em 10 dias de uma meta de 10.000: no passo de hoje, vende 9.300 no mês.
    a = _andamento(None, "Loja", None, Decimal(10000), (Decimal(3000), 30, Decimal(200)), ZERO, dias)
    assert (a.percentual, a.projecao, a.esperado_ate_hoje, a.falta, a.por_dia, a.situacao) == (
        Decimal("30.0"), Decimal("9300.00"), Decimal("3225.81"), Decimal(7000), Decimal("318.18"), "abaixo")
    a = _andamento(None, "Loja", None, Decimal(10000), (Decimal(3500), 30, ZERO), ZERO, dias)
    assert a.situacao == "no_ritmo"
    a = _andamento(None, "Loja", None, Decimal(10000), (Decimal(10500), 90, ZERO), ZERO, dias)
    assert (a.situacao, a.falta, a.por_dia) == ("batida", Decimal(0), None)
    # Mês que acabou e mês que ainda vem.
    assert _andamento(None, "L", None, Decimal(10), (ZERO, 0, ZERO), ZERO,
                      _dias(date(2026, 9, 1), date(2026, 10, 10))).situacao == "nao_batida"
    assert _andamento(None, "L", None, Decimal(10), (ZERO, 0, ZERO), ZERO,
                      _dias(date(2026, 11, 1), date(2026, 10, 10))).situacao == "nao_comecou"
    assert _andamento(None, "L", None, None, (ZERO, 0, ZERO), ZERO, dias).situacao == "sem_meta"


def test_metas_da_loja_e_do_vendedor(client, farmacia_a):
    h = farmacia_a["headers"]
    eu = client.get(f"{API}/auth/eu", headers=h).json()
    dipirona = _produto(client, farmacia_a, "Dipirona", "50.00")
    bruna, bruna_id = _atendente(client, farmacia_a)
    _abrir_caixa(client, farmacia_a)

    # Sem metas: todo mundo aparece, sem meta.
    metas = _metas(client, farmacia_a)
    loja_id = metas["lojas"][0]["id"]
    assert metas["total"]["situacao"] == "sem_meta"
    assert {v["nome"]: v["situacao"] for v in metas["vendedores"]} == {"Bruna Balconista": "sem_meta"}
    assert client.get(f"{API}/painel", headers=h).json()["meta_farmacia"] is None

    metas = _salvar(client, farmacia_a, lojas=[{"id": loja_id, "valor": "1000.00"}],
                    vendedores=[{"id": bruna_id, "valor": "400.00"}, {"id": eu["usuario_id"], "valor": "300.00"}])
    assert metas["total"]["meta"] == "1000.00"

    pre = client.post(f"{API}/pre-vendas", json={"itens": [{"produto_id": dipirona["id"], "quantidade": "2"}]},
                      headers=bruna)
    _vender(client, farmacia_a, [(dipirona, 2)], "100.00", pre_venda_id=pre.json()["id"])
    _vender(client, farmacia_a, [(dipirona, 1)], "50.00")
    cancelada = _vender(client, farmacia_a, [(dipirona, 4)], "200.00")
    client.post(f"{API}/vendas/{cancelada['id']}/cancelar", json={"motivo": "Desistiu"}, headers=h)

    metas = _metas(client, farmacia_a)
    restantes = calendar.monthrange(hoje().year, hoje().month)[1] - hoje().day + 1
    loja = metas["lojas"][0]
    assert (loja["vendido"], loja["vendas"], loja["vendido_hoje"], loja["percentual"], loja["falta"]) == (
        "150.00", 2, "150.00", "15.0", "850.00")
    assert Decimal(loja["por_dia"]) == (Decimal(850) / restantes).quantize(Decimal("0.01"))
    vendedores = {v["nome"]: v for v in metas["vendedores"]}
    assert (vendedores["Bruna Balconista"]["vendido"], vendedores["Bruna Balconista"]["percentual"]) == ("100.00", "25.0")
    meu = next(v for v in metas["vendedores"] if v["id"] == eu["usuario_id"])
    assert (meu["vendido"], meu["meta"]) == ("50.00", "300.00")

    # A balconista vê a meta dela no painel e em /metas/minha, mas não as dos outros.
    assert client.get(f"{API}/metas", headers=bruna).status_code == 403
    assert client.put(f"{API}/metas", json={"mes": hoje().isoformat()}, headers=bruna).status_code == 403
    minha = client.get(f"{API}/metas/minha", headers=bruna).json()
    assert (minha["meta"], minha["vendido"]) == ("400.00", "100.00")
    painel = client.get(f"{API}/painel", headers=bruna).json()
    assert (painel["minha_meta"]["meta"], painel["meta_farmacia"]["vendido"]) == ("400.00", "150.00")

    # Mudar e apagar.
    metas = _salvar(client, farmacia_a, vendedores=[{"id": bruna_id, "valor": "100.00"},
                                                    {"id": eu["usuario_id"], "valor": None}])
    vendedores = {v["id"]: v for v in metas["vendedores"]}
    assert vendedores[bruna_id]["situacao"] == "batida"
    assert vendedores[eu["usuario_id"]]["meta"] is None  # vendeu no mês, continua na lista
    assert client.get(f"{API}/metas/minha", headers=h).json() is None
    assert _metas(client, farmacia_a)["lojas"][0]["meta"] == "1000.00"  # a da loja ficou

    # O mês que vem já pode ser planejado, mostrando o que vendeu neste mês.
    proximo = (hoje().replace(day=28) + timedelta(days=5)).replace(day=1)
    metas = _salvar(client, farmacia_a, mes=proximo.isoformat(), lojas=[{"id": loja_id, "valor": "2000"}])
    assert (metas["total"]["situacao"], metas["lojas"][0]["vendido_mes_passado"], metas["lojas"][0]["vendido"]) == (
        "nao_comecou", "150.00", "0")

    # Mês passado não muda; valores errados não passam.
    passado = (hoje().replace(day=1) - timedelta(days=1)).replace(day=1)
    _salvar(client, farmacia_a, 400, mes=passado.isoformat(), lojas=[{"id": loja_id, "valor": "10"}])
    _salvar(client, farmacia_a, 422, lojas=[{"id": loja_id, "valor": "0"}])
    _salvar(client, farmacia_a, 404, vendedores=[{"id": loja_id, "valor": "10"}])


def test_metas_sao_de_cada_farmacia(client, farmacia_a, farmacia_b):
    loja_a = _metas(client, farmacia_a)["lojas"][0]["id"]
    _salvar(client, farmacia_a, lojas=[{"id": loja_a, "valor": "500"}])
    assert _metas(client, farmacia_b)["total"]["meta"] is None
    _salvar(client, farmacia_b, 404, lojas=[{"id": loja_a, "valor": "500"}])
