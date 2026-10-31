"""Pontos de fidelidade acertados em cada devolução

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Quanto o saldo de pontos do cliente mudou com a devolução (negativo: perdeu pontos).
    op.add_column("devolucoes", sa.Column("pontos", sa.Integer, nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("devolucoes", "pontos")
