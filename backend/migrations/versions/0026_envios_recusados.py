"""Envios feitos sem internet que o servidor recusou, para o gerente resolver

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

from migrations.helpers import FARMACIA_ATUAL, ativar_rls, conceder_app

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "envios_recusados",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farmacia_id", UUID(as_uuid=True), sa.ForeignKey("farmacias.id"), nullable=False,
                  server_default=sa.text(FARMACIA_ATUAL)),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("terminal_id", UUID(as_uuid=True), nullable=False),
        sa.Column("usuario_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chave", sa.String(80), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("feito_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("motivo", sa.Text, nullable=False),
        sa.Column("corpo", JSONB, nullable=False),
        sa.Column("resolvido_em", sa.DateTime(timezone=True)),
        sa.Column("resolvido_por", UUID(as_uuid=True)),
        sa.Column("resolucao", sa.String(10)),
        sa.UniqueConstraint("farmacia_id", "chave", name="uq_envios_recusados_chave"),
        sa.ForeignKeyConstraint(["farmacia_id", "terminal_id"], ["terminais.farmacia_id", "terminais.id"]),
        sa.CheckConstraint("tipo IN ('venda', 'abrir', 'fechar')", name="ck_envios_recusados_tipo"),
        sa.CheckConstraint("resolucao IS NULL OR resolucao IN ('enviada', 'manual')", name="ck_envios_recusados_resolucao"),
    )
    ativar_rls("envios_recusados")
    conceder_app("envios_recusados", "SELECT, INSERT, UPDATE")


def downgrade() -> None:
    op.drop_table("envios_recusados")
