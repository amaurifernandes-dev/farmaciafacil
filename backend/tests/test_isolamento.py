"""Uma farmácia nunca pode ver nem alterar dados de outra."""

from sqlalchemy import select, text

from app.core.db import SessionLocal
from app.modules.produtos.models import Produto

PRODUTO = {"ean": "7891234567890", "nome": "Dipirona 500mg", "preco_venda": "8.90"}


def test_listagem_mostra_so_a_propria_farmacia(client, farmacia_a, farmacia_b):
    client.post("/api/v1/produtos", json=PRODUTO, headers=farmacia_a["headers"])
    assert client.get("/api/v1/produtos", headers=farmacia_b["headers"]).json()["total"] == 0


def test_mesmo_ean_em_farmacias_diferentes(client, farmacia_a, farmacia_b):
    assert client.post("/api/v1/produtos", json=PRODUTO, headers=farmacia_a["headers"]).status_code == 201
    assert client.post("/api/v1/produtos", json=PRODUTO, headers=farmacia_b["headers"]).status_code == 201


def test_nao_le_nem_altera_produto_de_outra_farmacia(client, farmacia_a, farmacia_b):
    produto = client.post("/api/v1/produtos", json=PRODUTO, headers=farmacia_a["headers"]).json()
    url = f"/api/v1/produtos/{produto['id']}"

    assert client.get(url, headers=farmacia_b["headers"]).status_code == 404
    assert client.patch(url, json={"preco_venda": "0.01"}, headers=farmacia_b["headers"]).status_code == 404
    assert client.get("/api/v1/produtos/ean/7891234567890", headers=farmacia_b["headers"]).status_code == 404
    assert client.get(url, headers=farmacia_a["headers"]).json()["preco_venda"] == "8.90"


def test_banco_bloqueia_mesmo_sem_filtro_na_aplicacao(client, farmacia_a, farmacia_b):
    """Mesmo uma consulta sem WHERE só enxerga a farmácia da sessão (RLS)."""
    client.post("/api/v1/produtos", json=PRODUTO, headers=farmacia_a["headers"])

    with SessionLocal(info={"farmacia_id": farmacia_b["id"]}) as db:
        assert db.scalars(select(Produto)).all() == []

    with SessionLocal() as db:  # sem farmácia definida: não vê nada
        assert db.scalars(select(Produto)).all() == []


def test_banco_recusa_gravar_em_outra_farmacia(farmacia_a, farmacia_b):
    with SessionLocal(info={"farmacia_id": farmacia_a["id"]}) as db:
        try:
            db.execute(
                text("INSERT INTO produtos (id, farmacia_id, nome, preco_venda) VALUES (gen_random_uuid(), :f, 'x', 1)"),
                {"f": farmacia_b["id"]},
            )
            db.commit()
            gravou = True
        except Exception as erro:
            assert "row-level security" in str(erro)
            gravou = False
    assert not gravou
