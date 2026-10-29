"""Funções usadas pelas migrações para aplicar o isolamento por farmácia."""

from alembic import op

from app.core.config import get_settings

FARMACIA_ATUAL = "NULLIF(current_setting('app.farmacia_id', true), '')::uuid"


def ativar_rls(tabela: str, coluna: str = "farmacia_id") -> None:
    """Liga o RLS e cria a política: cada farmácia só lê e grava as próprias linhas."""
    op.execute(f"ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY isolamento_farmacia ON {tabela}
            USING ({coluna} = {FARMACIA_ATUAL})
            WITH CHECK ({coluna} = {FARMACIA_ATUAL})
        """
    )


def conceder_app(tabela: str, permissoes: str = "SELECT, INSERT, UPDATE, DELETE") -> None:
    op.execute(f"GRANT {permissoes} ON {tabela} TO {get_settings().app_db_role}")
