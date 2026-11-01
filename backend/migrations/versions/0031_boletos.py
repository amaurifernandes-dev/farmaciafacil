"""Contas a pagar com boleto: o código de barras fica na conta

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-01
"""
import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contas", sa.Column("codigo_barras", sa.String(44)))
    # O mesmo boleto não é lançado duas vezes (cancelada não conta).
    op.create_index(
        "uq_contas_codigo_barras",
        "contas",
        ["farmacia_id", "codigo_barras"],
        unique=True,
        postgresql_where=sa.text("codigo_barras IS NOT NULL AND status <> 'cancelada'"),
    )


def downgrade() -> None:
    op.drop_index("uq_contas_codigo_barras", "contas")
    op.drop_column("contas", "codigo_barras")
