"""Central de licenças: usuários, licenças e histórico

Revision ID: c0001
Revises:
Create Date: 2026-11-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "c0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usuarios_central",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("email", sa.String(200), nullable=False, unique=True),
        sa.Column("senha_hash", sa.String(100), nullable=False),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "licencas",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("cnpj", sa.String(14), nullable=False, index=True),
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("contato", sa.String(200)),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("plano", sa.String(10), nullable=False),
        sa.Column("inicio", sa.Date, nullable=False),
        sa.Column("vence", sa.Date),
        sa.Column("tolerancia_dias", sa.Integer, nullable=False, server_default="7"),
        sa.Column("max_usuarios", sa.Integer),
        sa.Column("max_caixas", sa.Integer),
        sa.Column("modulos", JSONB),
        sa.Column("chave_ativacao", sa.String(29), nullable=False, unique=True),
        sa.Column("maquina", sa.String(19)),
        sa.Column("suspensa", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("observacao", sa.Text),
        sa.Column("ultima_consulta_em", sa.DateTime(timezone=True)),
        sa.Column("criada_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizada_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("tipo IN ('nuvem', 'farmacia')", name="ck_licencas_tipo"),
        sa.CheckConstraint("plano IN ('mensal', 'anual', 'vitalicio')", name="ck_licencas_plano"),
    )
    op.create_table(
        "historico_licencas",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("licenca_id", sa.Integer, sa.ForeignKey("licencas.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("quando", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("quem", sa.String(120), nullable=False),
        sa.Column("o_que", sa.String(300), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("historico_licencas")
    op.drop_table("licencas")
    op.drop_table("usuarios_central")
