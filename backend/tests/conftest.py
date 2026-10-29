import os

# Banco de teste. Precisa ser configurado antes de importar o app.
os.environ.setdefault("DATABASE_URL", "postgresql://ff_app:ff_app@localhost:5432/farmaciafacil_test")
os.environ.setdefault(
    "MIGRATION_DATABASE_URL", "postgresql://ff_owner:ff_owner@localhost:5432/farmaciafacil_test"
)
os.environ.setdefault("APP_DB_ROLE", "ff_app")
os.environ.setdefault("JWT_SECRET", "segredo-de-teste-com-pelo-menos-32-bytes")

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.scripts.criar_farmacia import criar_farmacia  # noqa: E402

PASTA_BACKEND = os.path.dirname(os.path.dirname(__file__))


@pytest.fixture(scope="session")
def engine_dono():
    """Recria o schema do zero e aplica as migrações uma vez por rodada de testes."""
    engine = create_engine(get_settings().migration_database_url)
    with engine.begin() as conexao:
        conexao.execute(text("DROP SCHEMA public CASCADE"))
        conexao.execute(text("CREATE SCHEMA public"))

    config = Config(os.path.join(PASTA_BACKEND, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(PASTA_BACKEND, "migrations"))
    command.upgrade(config, "head")
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def banco_limpo(engine_dono):
    yield
    with engine_dono.begin() as conexao:
        conexao.execute(text("TRUNCATE farmacias CASCADE"))


@pytest.fixture
def client():
    return TestClient(app)


def _nova_farmacia(engine_dono, client, cnpj: str, email: str) -> dict:
    with Session(engine_dono, expire_on_commit=False) as db:
        farmacia, _ = criar_farmacia(
            db,
            cnpj=cnpj,
            razao_social=f"Farmácia {cnpj} LTDA",
            nome_fantasia=f"Farmácia {cnpj}",
            uf="SP",
            admin_nome="Admin",
            admin_email=email,
            admin_senha="senha-forte",
        )
    resposta = client.post("/api/v1/auth/login", json={"email": email, "senha": "senha-forte"})
    assert resposta.status_code == 200, resposta.text
    token = resposta.json()["access_token"]
    return {"id": farmacia.id, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
def farmacia_a(engine_dono, client):
    return _nova_farmacia(engine_dono, client, "11111111000111", "a@farmacia.com")


@pytest.fixture
def farmacia_b(engine_dono, client):
    return _nova_farmacia(engine_dono, client, "22222222000122", "b@farmacia.com")
