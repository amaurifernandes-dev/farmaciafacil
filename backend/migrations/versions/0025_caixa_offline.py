"""Caixa aberto e fechado no PDV sem internet, enviado depois

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-01
"""
import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("caixas", sa.Column("aberto_offline", sa.Boolean, nullable=False, server_default=sa.false()))
    op.add_column("caixas", sa.Column("fechado_offline", sa.Boolean, nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("caixas", "fechado_offline")
    op.drop_column("caixas", "aberto_offline")
