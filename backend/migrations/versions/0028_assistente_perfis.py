"""Assistente de IA: quais perfis da farmácia podem usar

Revision ID: 0028
Revises: 0027
Create Date: 2026-11-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None

TODOS = '["admin", "gerente", "farmaceutico", "caixa", "atendente", "estoque"]'


def upgrade() -> None:
    op.add_column(
        "farmacias",
        sa.Column("assistente_perfis", JSONB, nullable=False, server_default=sa.text(f"'{TODOS}'::jsonb")),
    )
    op.create_check_constraint(
        "ck_farmacias_assistente_perfis", "farmacias", "jsonb_typeof(assistente_perfis) = 'array'"
    )


def downgrade() -> None:
    op.drop_constraint("ck_farmacias_assistente_perfis", "farmacias")
    op.drop_column("farmacias", "assistente_perfis")
