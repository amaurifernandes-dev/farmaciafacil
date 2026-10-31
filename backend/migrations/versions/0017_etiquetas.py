"""Etiquetas de gôndola: o que está impresso em cada loja, para saber o que trocar

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from migrations.helpers import FARMACIA_ATUAL, ativar_rls, conceder_app

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "etiquetas",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farmacia_id", UUID(as_uuid=True), sa.ForeignKey("farmacias.id"), nullable=False,
                  server_default=sa.text(FARMACIA_ATUAL)),
        sa.Column("loja_id", UUID(as_uuid=True), nullable=False),
        sa.Column("produto_id", UUID(as_uuid=True), nullable=False),
        # O que ficou impresso na última etiqueta: preço normal e a promoção (se tinha).
        sa.Column("preco", sa.Numeric(12, 2), nullable=False),
        sa.Column("preco_promocional", sa.Numeric(12, 2)),
        sa.Column("promocao", sa.String(120)),
        sa.Column("impressa_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usuario_id", UUID(as_uuid=True), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("farmacia_id", "loja_id", "produto_id", name="uq_etiquetas_loja_produto"),
        sa.ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "produto_id"], ["produtos.farmacia_id", "produtos.id"]),
    )
    ativar_rls("etiquetas")
    conceder_app("etiquetas", "SELECT, INSERT, UPDATE")


def downgrade() -> None:
    op.drop_table("etiquetas")
