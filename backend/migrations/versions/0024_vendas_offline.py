"""Vendas feitas no caixa sem internet, enviadas depois

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-01
"""
import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Feita sem internet: finalizada_em é a hora no caixa; criado_em, a hora em que chegou.
    op.add_column("vendas", sa.Column("offline", sa.Boolean, nullable=False, server_default=sa.false()))
    # Vendido sem saldo no sistema (só acontece offline): o estoque do sistema estava abaixo do real.
    op.add_column("venda_itens", sa.Column("sem_estoque", sa.Numeric(12, 3), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("venda_itens", "sem_estoque")
    op.drop_column("vendas", "offline")
