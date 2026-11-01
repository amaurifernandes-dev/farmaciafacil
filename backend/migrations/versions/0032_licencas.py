"""Licença do FarmáciaFácil: o código vindo da central e a identidade do servidor

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.core.config import get_settings
from migrations.helpers import conceder_app

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Sem RLS: a tela da licença é lida antes do login, e o código só vale para o CNPJ que está dentro dele.
    op.create_table(
        "licencas_instaladas",
        sa.Column("cnpj", sa.String(14), primary_key=True),
        sa.Column("codigo", sa.Text, nullable=False),
        sa.Column("chave_ativacao", sa.String(29)),
        sa.Column("emitida_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("instalada_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ultima_tentativa_em", sa.DateTime(timezone=True)),
        sa.Column("ultimo_erro", sa.String(300)),
    )
    conceder_app("licencas_instaladas", "SELECT, INSERT, UPDATE")

    op.create_table(
        "servidor_local",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("maquina_id", UUID(as_uuid=True), nullable=False),
        sa.Column("maior_data", sa.Date),
        sa.CheckConstraint("id = 1", name="ck_servidor_local_uma_linha"),
    )
    conceder_app("servidor_local", "SELECT, INSERT, UPDATE")

    # Antes do login, instalado na farmácia: qual é o CNPJ da farmácia (o RLS esconderia a linha).
    op.execute(
        """
        CREATE FUNCTION licenca_cnpjs() RETURNS SETOF text
            LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
            AS $$ SELECT cnpj FROM farmacias WHERE ativo $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION licenca_cnpjs() FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION licenca_cnpjs() TO {get_settings().app_db_role}")


def downgrade() -> None:
    op.execute("DROP FUNCTION licenca_cnpjs()")
    op.drop_table("servidor_local")
    op.drop_table("licencas_instaladas")
