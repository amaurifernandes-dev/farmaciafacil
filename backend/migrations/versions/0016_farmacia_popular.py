"""Farmácia Popular: o governo paga parte do remédio e a farmácia recebe no mês seguinte

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

from migrations.helpers import FARMACIA_ATUAL, ativar_rls, conceder_app

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

FORMAS_ANTIGAS = "'dinheiro', 'debito', 'credito', 'pix', 'prazo', 'convenio'"
FORMAS = "'dinheiro', 'debito', 'credito', 'pix', 'prazo', 'convenio', 'popular'"


def upgrade() -> None:
    op.add_column("produtos", sa.Column("popular_valor", sa.Numeric(12, 2)))
    op.create_check_constraint("ck_produtos_popular_valor", "produtos", "popular_valor IS NULL OR popular_valor >= 0")

    op.add_column("farmacias", sa.Column("popular_validade_receita", sa.SmallInteger, nullable=False,
                                         server_default="180"))
    op.add_column("farmacias", sa.Column("popular_intervalo_dias", sa.SmallInteger, nullable=False,
                                         server_default="30"))
    op.create_check_constraint("ck_farmacias_popular_validade", "farmacias", "popular_validade_receita BETWEEN 30 AND 365")
    op.create_check_constraint("ck_farmacias_popular_intervalo", "farmacias", "popular_intervalo_dias BETWEEN 0 AND 90")

    op.drop_constraint("ck_pagamentos_forma", "venda_pagamentos")
    op.create_check_constraint("ck_pagamentos_forma", "venda_pagamentos", f"forma IN ({FORMAS})")

    op.create_table(
        "popular_vendas",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farmacia_id", UUID(as_uuid=True), sa.ForeignKey("farmacias.id"), nullable=False,
                  server_default=sa.text(FARMACIA_ATUAL)),
        sa.Column("venda_id", UUID(as_uuid=True), nullable=False),
        sa.Column("loja_id", UUID(as_uuid=True), nullable=False),
        sa.Column("data", sa.Date, nullable=False),
        sa.Column("paciente_cpf", sa.String(11), nullable=False),
        sa.Column("paciente_nome", sa.String(120), nullable=False),
        sa.Column("prescritor_crm", sa.String(20), nullable=False),
        sa.Column("prescritor_uf", sa.String(2), nullable=False),
        sa.Column("receita_data", sa.Date, nullable=False),
        sa.Column("autorizacao", sa.String(40), nullable=False),
        sa.Column("valor_governo", sa.Numeric(12, 2), nullable=False),
        sa.Column("valor_paciente", sa.Numeric(12, 2), nullable=False),
        # Os remédios do programa e quanto o governo paga de cada um, como foi no dia da venda.
        sa.Column("itens", JSONB, nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="aberta"),
        sa.Column("conta_id", UUID(as_uuid=True)),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("farmacia_id", "id"),
        sa.UniqueConstraint("farmacia_id", "venda_id", name="uq_popular_vendas_venda"),
        sa.ForeignKeyConstraint(["farmacia_id", "venda_id"], ["vendas.farmacia_id", "vendas.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "conta_id"], ["contas.farmacia_id", "contas.id"]),
        sa.CheckConstraint("status IN ('aberta', 'lancada', 'cancelada')", name="ck_popular_vendas_status"),
        sa.CheckConstraint("valor_governo > 0 AND valor_paciente >= 0", name="ck_popular_vendas_valores"),
    )
    # A mesma autorização do governo não vale para duas vendas.
    op.create_index("uq_popular_vendas_autorizacao", "popular_vendas", ["farmacia_id", "autorizacao"], unique=True,
                    postgresql_where=sa.text("status <> 'cancelada'"))
    op.create_index("ix_popular_vendas_data", "popular_vendas", ["farmacia_id", "data", "status"])
    op.create_index("ix_popular_vendas_paciente", "popular_vendas", ["farmacia_id", "paciente_cpf", "data"])
    ativar_rls("popular_vendas")
    conceder_app("popular_vendas", "SELECT, INSERT, UPDATE")


def downgrade() -> None:
    op.drop_table("popular_vendas")
    op.drop_constraint("ck_pagamentos_forma", "venda_pagamentos")
    op.create_check_constraint("ck_pagamentos_forma", "venda_pagamentos", f"forma IN ({FORMAS_ANTIGAS})")
    op.drop_constraint("ck_farmacias_popular_intervalo", "farmacias")
    op.drop_constraint("ck_farmacias_popular_validade", "farmacias")
    op.drop_column("farmacias", "popular_intervalo_dias")
    op.drop_column("farmacias", "popular_validade_receita")
    op.drop_constraint("ck_produtos_popular_valor", "produtos")
    op.drop_column("produtos", "popular_valor")
