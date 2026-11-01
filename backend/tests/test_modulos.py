from tests.test_pedidos import _ligar_loja
from tests.test_vendas import API, _login_caixa


def _desligar(client, farmacia, modulos):
    resposta = client.patch(f"{API}/configuracoes", json={"modulos_desligados": modulos}, headers=farmacia["headers"])
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def test_tudo_ligado_por_padrao(client, farmacia_a):
    assert client.get(f"{API}/configuracoes", headers=farmacia_a["headers"]).json()["modulos_desligados"] == []
    assert client.get(f"{API}/faltas", headers=farmacia_a["headers"]).status_code == 200


def test_funcao_desligada_bloqueia_ate_o_administrador(client, farmacia_a):
    config = _desligar(client, farmacia_a, ["faltas", "devolucoes", "faltas"])
    assert config["modulos_desligados"] == ["devolucoes", "faltas"]  # na ordem da lista, sem repetir

    faltas = client.get(f"{API}/faltas", headers=farmacia_a["headers"])
    assert faltas.status_code == 403
    assert "Gerenciamento de telas" in faltas.json()["detail"]
    assert client.get(f"{API}/devolucoes", headers=farmacia_a["headers"]).status_code == 403
    # O que não foi desligado continua funcionando.
    assert client.get(f"{API}/convenios", headers=farmacia_a["headers"]).status_code == 200

    # Ligando de novo, volta.
    _desligar(client, farmacia_a, [])
    assert client.get(f"{API}/faltas", headers=farmacia_a["headers"]).status_code == 200


def test_so_o_administrador_muda(client, engine_dono, farmacia_a):
    headers = _login_caixa(client, engine_dono, farmacia_a)
    resposta = client.patch(f"{API}/configuracoes", json={"modulos_desligados": ["faltas"]}, headers=headers)
    assert resposta.status_code == 403
    # Mas todos leem, para as telas saberem o que esconder.
    assert client.get(f"{API}/configuracoes", headers=headers).json()["modulos_desligados"] == []


def test_funcao_desconhecida_e_recusada(client, farmacia_a):
    resposta = client.patch(f"{API}/configuracoes", json={"modulos_desligados": ["vendas"]}, headers=farmacia_a["headers"])
    assert resposta.status_code == 422


def test_loja_online_some_quando_desligada_ou_sem_pedidos(client, farmacia_a):
    _ligar_loja(client, farmacia_a)
    assert client.get(f"{API}/loja/bem-estar").status_code == 200
    _desligar(client, farmacia_a, ["loja_online"])
    assert client.get(f"{API}/loja/bem-estar").status_code == 404
    # Sem a função de pedidos, a loja online também não abre.
    _desligar(client, farmacia_a, ["pedidos"])
    assert client.get(f"{API}/loja/bem-estar").status_code == 404
    assert client.get(f"{API}/pedidos", headers=farmacia_a["headers"]).status_code == 403
    _desligar(client, farmacia_a, [])
    assert client.get(f"{API}/loja/bem-estar").status_code == 200


def test_desligar_numa_farmacia_nao_afeta_a_outra(client, farmacia_a, farmacia_b):
    _desligar(client, farmacia_a, ["faltas"])
    assert client.get(f"{API}/faltas", headers=farmacia_b["headers"]).status_code == 200
