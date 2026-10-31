"""Metas de vendas do mês: de cada loja e de cada vendedor

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from migrations.helpers import FARMACIA_ATUAL, ativar_rls, conceder_app

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "metas",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farmacia_id", UUID(as_uuid=True), sa.ForeignKey("farmacias.id"), nullable=False,
                  server_default=sa.text(FARMACIA_ATUAL)),
        sa.Column("mes", sa.Date, nullable=False),  # sempre o dia 1º
        # A meta é de uma loja ou de um vendedor (que pode vender em qualquer loja).
        sa.Column("loja_id", UUID(as_uuid=True)),
        sa.Column("usuario_id", UUID(as_uuid=True), sa.ForeignKey("usuarios.id")),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
        sa.CheckConstraint("(loja_id IS NULL) <> (usuario_id IS NULL)", name="ck_metas_loja_ou_vendedor"),
        sa.CheckConstraint("valor > 0", name="ck_metas_valor"),
        sa.CheckConstraint("EXTRACT(DAY FROM mes) = 1", name="ck_metas_mes"),
    )
    op.create_index("uq_metas_loja", "metas", ["farmacia_id", "mes", "loja_id"], unique=True,
                    postgresql_where=sa.text("loja_id IS NOT NULL"))
    op.create_index("uq_metas_vendedor", "metas", ["farmacia_id", "mes", "usuario_id"], unique=True,
                    postgresql_where=sa.text("usuario_id IS NOT NULL"))
    ativar_rls("metas")
    conceder_app("metas")


def downgrade() -> None:
    op.drop_table("metas")
