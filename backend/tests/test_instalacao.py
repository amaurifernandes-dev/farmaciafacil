import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.scripts.criar_farmacia import criar_farmacia
from tests.test_pedidos import _ligar_loja

API = "/api/v1"


@pytest.fixture
def na_farmacia(monkeypatch):
    monkeypatch.setattr(get_settings(), "instalacao", "farmacia")


def test_na_nuvem_a_loja_online_existe(client, farmacia_a):
    assert client.get(f"{API}/instalacao").json() == {"modo": "nuvem", "loja_online": True}
    _ligar_loja(client, farmacia_a)
    assert client.get(f"{API}/loja/bem-estar").status_code == 200


def test_na_farmacia_a_loja_online_some(client, farmacia_a, na_farmacia):
    assert client.get(f"{API}/instalacao").json() == {"modo": "farmacia", "loja_online": False}
    _ligar_loja(client, farmacia_a)
    assert client.get(f"{API}/loja/bem-estar").status_code == 404
    assert client.get(f"{API}/loja/bem-estar/produtos").status_code == 404
    # O resto continua igual: os pedidos do WhatsApp e do telefone seguem na tela Pedidos.
    assert client.get(f"{API}/pedidos", headers=farmacia_a["headers"]).status_code == 200


def test_na_farmacia_so_existe_uma_farmacia(engine_dono, farmacia_a, na_farmacia):
    with Session(engine_dono) as db, pytest.raises(SystemExit):
        criar_farmacia(db, cnpj="33333333000133", razao_social="Outra LTDA", nome_fantasia="Outra", uf="SP",
                       admin_nome="Admin", admin_email="outra@farmacia.com", admin_senha="senha-forte-123")
