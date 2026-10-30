"""Fidelidade: pontos do cliente, ganhos nas compras e trocados por desconto

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-30
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from migrations.helpers import FARMACIA_ATUAL, ativar_rls, conceder_app

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("farmacias", sa.Column("fidelidade_ativa", sa.Boolean, nullable=False, server_default="false"))
    op.add_column("farmacias", sa.Column("pontos_por_real", sa.Numeric(6, 2), nullable=False, server_default="1"))
    op.add_column("farmacias", sa.Column("valor_ponto", sa.Numeric(8, 4), nullable=False, server_default="0.05"))
    op.add_column("farmacias", sa.Column("pontos_minimo_resgate", sa.Integer, nullable=False, server_default="100"))
    # Vazio: os pontos não expiram. Senão, expiram se o cliente ficar esse tempo sem comprar.
    op.add_column("farmacias", sa.Column("pontos_validade_meses", sa.Integer, server_default="12"))
    op.create_check_constraint(
        "ck_farmacias_fidelidade",
        "farmacias",
        "pontos_por_real >= 0 AND valor_ponto > 0 AND pontos_minimo_resgate >= 1"
        " AND (pontos_validade_meses IS NULL OR pontos_validade_meses BETWEEN 1 AND 60)",
    )

    op.add_column("vendas", sa.Column("pontos_ganhos", sa.Integer, nullable=False, server_default="0"))
    op.add_column("vendas", sa.Column("pontos_resgatados", sa.Integer, nullable=False, server_default="0"))
    op.add_column("vendas", sa.Column("desconto_pontos", sa.Numeric(12, 2), nullable=False, server_default="0"))

    op.create_table(
        "movimentos_pontos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farmacia_id", UUID(as_uuid=True), sa.ForeignKey("farmacias.id"), nullable=False,
                  server_default=sa.text(FARMACIA_ATUAL)),
        sa.Column("cliente_id", UUID(as_uuid=True), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("pontos", sa.Integer, nullable=False),
        sa.Column("venda_id", UUID(as_uuid=True)),
        sa.Column("usuario_id", UUID(as_uuid=True), sa.ForeignKey("usuarios.id")),
        sa.Column("observacao", sa.String(200)),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["farmacia_id", "cliente_id"], ["clientes.farmacia_id", "clientes.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "venda_id"], ["vendas.farmacia_id", "vendas.id"]),
        sa.CheckConstraint("tipo IN ('ganho', 'resgate', 'estorno', 'ajuste', 'expirado')", name="ck_pontos_tipo"),
        sa.CheckConstraint("pontos <> 0", name="ck_pontos_valor"),
    )
    op.create_index("ix_pontos_cliente", "movimentos_pontos", ["farmacia_id", "cliente_id", "criado_em"])
    op.create_index("ix_vendas_cliente", "vendas", ["farmacia_id", "cliente_id", "finalizada_em"],
                    postgresql_where=sa.text("cliente_id IS NOT NULL"))
    ativar_rls("movimentos_pontos")
    # Extrato: só se acrescenta, nunca se altera.
    conceder_app("movimentos_pontos", "SELECT, INSERT")


def downgrade() -> None:
    op.drop_index("ix_vendas_cliente", "vendas")
    op.drop_table("movimentos_pontos")
    op.drop_column("vendas", "desconto_pontos")
    op.drop_column("vendas", "pontos_resgatados")
    op.drop_column("vendas", "pontos_ganhos")
    op.drop_constraint("ck_farmacias_fidelidade", "farmacias")
    for coluna in ("pontos_validade_meses", "pontos_minimo_resgate", "valor_ponto", "pontos_por_real",
                   "fidelidade_ativa"):
        op.drop_column("farmacias", coluna)
