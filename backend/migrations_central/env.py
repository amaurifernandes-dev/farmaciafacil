"""Migrações do banco da central de licenças. Usa CENTRAL_DATABASE_URL, nunca o banco das farmácias."""

from alembic import context
from sqlalchemy import create_engine

from app.central.config import get_config
from app.central.models import BaseCentral


def run_migrations_online() -> None:
    url = context.config.get_main_option("sqlalchemy.url") or get_config().database_url
    engine = create_engine(url)
    with engine.connect() as conexao:
        context.configure(connection=conexao, target_metadata=BaseCentral.metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
