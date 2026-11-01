"""Fechamento de caixa detalhado: sangrias, suprimentos e conferência por forma de pagamento

Revision ID: 0029
Revises: 0028
Create Date: 2026-11-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

from migrations.helpers import FARMACIA_ATUAL, ativar_rls, conceder_app

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "caixa_movimentos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farmacia_id", UUID(as_uuid=True), sa.ForeignKey("farmacias.id"), nullable=False,
                  server_default=sa.text(FARMACIA_ATUAL)),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("caixa_id", UUID(as_uuid=True), nullable=False),
        sa.Column("usuario_id", UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("motivo", sa.String(200), nullable=False),
        sa.UniqueConstraint("farmacia_id", "id"),
        sa.ForeignKeyConstraint(["farmacia_id", "caixa_id"], ["caixas.farmacia_id", "caixas.id"]),
        sa.CheckConstraint("tipo IN ('sangria', 'suprimento')", name="ck_caixa_movimentos_tipo"),
        sa.CheckConstraint("valor > 0", name="ck_caixa_movimentos_valor"),
    )
    op.create_index("ix_caixa_movimentos_caixa", "caixa_movimentos", ["farmacia_id", "caixa_id"])
    ativar_rls("caixa_movimentos")
    conceder_app("caixa_movimentos", "SELECT, INSERT")

    # O que o operador contou de cada forma (comprovantes de cartão, Pix) e a explicação da diferença.
    op.add_column("caixas", sa.Column("conferencia", JSONB))
    op.add_column("caixas", sa.Column("observacao_fechamento", sa.String(500)))


def downgrade() -> None:
    op.drop_column("caixas", "observacao_fechamento")
    op.drop_column("caixas", "conferencia")
    op.drop_table("caixa_movimentos")
