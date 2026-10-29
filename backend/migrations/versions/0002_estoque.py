"""Estoque: lotes com validade e movimentos

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-29
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from migrations.helpers import FARMACIA_ATUAL, ativar_rls, conceder_app

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lotes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farmacia_id", UUID(as_uuid=True), sa.ForeignKey("farmacias.id"), nullable=False,
                  server_default=sa.text(FARMACIA_ATUAL)),
        sa.Column("produto_id", UUID(as_uuid=True), nullable=False),
        sa.Column("numero_lote", sa.String(40), nullable=False),
        sa.Column("validade", sa.Date),
        sa.Column("quantidade", sa.Numeric(12, 3), nullable=False, server_default="0"),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("farmacia_id", "produto_id", "numero_lote"),
        sa.UniqueConstraint("farmacia_id", "id"),
        sa.ForeignKeyConstraint(["farmacia_id", "produto_id"], ["produtos.farmacia_id", "produtos.id"]),
        sa.CheckConstraint("quantidade >= 0", name="ck_lotes_quantidade"),
    )
    op.create_index("ix_lotes_validade", "lotes", ["farmacia_id", "validade"])
    ativar_rls("lotes")
    conceder_app("lotes", "SELECT, INSERT, UPDATE")

    op.create_table(
        "movimentos_estoque",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farmacia_id", UUID(as_uuid=True), sa.ForeignKey("farmacias.id"), nullable=False,
                  server_default=sa.text(FARMACIA_ATUAL)),
        sa.Column("produto_id", UUID(as_uuid=True), nullable=False),
        sa.Column("lote_id", UUID(as_uuid=True), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("quantidade", sa.Numeric(12, 3), nullable=False),
        sa.Column("custo_unitario", sa.Numeric(12, 4)),
        sa.Column("referencia_tipo", sa.String(30)),
        sa.Column("referencia_id", UUID(as_uuid=True)),
        sa.Column("usuario_id", UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("motivo", sa.String(200)),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["farmacia_id", "produto_id"], ["produtos.farmacia_id", "produtos.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "lote_id"], ["lotes.farmacia_id", "lotes.id"]),
        sa.CheckConstraint(
            "tipo IN ('entrada', 'venda', 'ajuste', 'perda', 'devolucao')", name="ck_movimentos_tipo"
        ),
        sa.CheckConstraint("quantidade <> 0", name="ck_movimentos_quantidade"),
    )
    op.create_index("ix_movimentos_produto", "movimentos_estoque", ["farmacia_id", "produto_id", "criado_em"])
    op.create_index("ix_movimentos_referencia", "movimentos_estoque", ["referencia_tipo", "referencia_id"])
    ativar_rls("movimentos_estoque")
    # Histórico imutável: a aplicação só lê e insere.
    conceder_app("movimentos_estoque", "SELECT, INSERT")


def downgrade() -> None:
    op.drop_table("movimentos_estoque")
    op.drop_table("lotes")
