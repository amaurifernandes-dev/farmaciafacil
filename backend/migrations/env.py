from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app.core.config import get_settings
from app.modules import todos_os_modelos  # noqa: F401  (registra as tabelas)
from app.shared.models import Base

if context.config.config_file_name:
    fileConfig(context.config.config_file_name)


def run_migrations_online() -> None:
    engine = create_engine(get_settings().migration_database_url)
    with engine.connect() as conexao:
        context.configure(connection=conexao, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
