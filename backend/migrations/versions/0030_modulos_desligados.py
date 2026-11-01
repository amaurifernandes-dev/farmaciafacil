"""Gerenciamento de telas: funções que o administrador desligou

Revision ID: 0030
Revises: 0029
Create Date: 2026-11-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "farmacias",
        sa.Column("modulos_desligados", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.create_check_constraint(
        "ck_farmacias_modulos_desligados", "farmacias", "jsonb_typeof(modulos_desligados) = 'array'"
    )


def downgrade() -> None:
    op.drop_constraint("ck_farmacias_modulos_desligados", "farmacias")
    op.drop_column("farmacias", "modulos_desligados")
