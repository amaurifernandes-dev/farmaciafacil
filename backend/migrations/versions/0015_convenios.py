"""Convênios com empresas: o funcionário compra e a empresa paga uma fatura por mês

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from migrations.helpers import FARMACIA_ATUAL, ativar_rls, conceder_app

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

FORMAS_ANTIGAS = "'dinheiro', 'debito', 'credito', 'pix', 'prazo'"
FORMAS = "'dinheiro', 'debito', 'credito', 'pix', 'prazo', 'convenio'"


def _id_e_farmacia() -> list[sa.Column]:
    return [
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farmacia_id", UUID(as_uuid=True), sa.ForeignKey("farmacias.id"), nullable=False,
                  server_default=sa.text(FARMACIA_ATUAL)),
    ]


def _datas() -> list[sa.Column]:
    return [
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    op.create_table(
        "convenios",
        *_id_e_farmacia(),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("cnpj", sa.String(14)),
        sa.Column("contato", sa.String(120)),
        sa.Column("telefone", sa.String(20)),
        sa.Column("email", sa.String(254)),
        sa.Column("desconto", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("limite_padrao", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("dia_fechamento", sa.SmallInteger, nullable=False, server_default="25"),
        sa.Column("dias_para_pagar", sa.SmallInteger, nullable=False, server_default="10"),
        sa.Column("observacao", sa.String(300)),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        *_datas(),
        sa.UniqueConstraint("farmacia_id", "id"),
        sa.CheckConstraint("desconto BETWEEN 0 AND 100", name="ck_convenios_desconto"),
        sa.CheckConstraint("limite_padrao >= 0", name="ck_convenios_limite"),
        sa.CheckConstraint("dia_fechamento BETWEEN 1 AND 28", name="ck_convenios_dia"),
        sa.CheckConstraint("dias_para_pagar BETWEEN 0 AND 90", name="ck_convenios_dias_pagar"),
    )
    ativar_rls("convenios")
    conceder_app("convenios", "SELECT, INSERT, UPDATE")

    op.add_column("clientes", sa.Column("convenio_id", UUID(as_uuid=True)))
    op.add_column("clientes", sa.Column("convenio_matricula", sa.String(30)))
    op.add_column("clientes", sa.Column("convenio_limite", sa.Numeric(12, 2)))
    op.create_foreign_key(
        "fk_clientes_convenio", "clientes", "convenios", ["farmacia_id", "convenio_id"], ["farmacia_id", "id"]
    )

    op.add_column("contas", sa.Column("convenio_id", UUID(as_uuid=True)))
    op.create_foreign_key(
        "fk_contas_convenio", "contas", "convenios", ["farmacia_id", "convenio_id"], ["farmacia_id", "id"]
    )
    op.create_unique_constraint("uq_contas_farmacia_id", "contas", ["farmacia_id", "id"])

    op.add_column("vendas", sa.Column("desconto_convenio", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.drop_constraint("ck_pagamentos_forma", "venda_pagamentos")
    op.create_check_constraint("ck_pagamentos_forma", "venda_pagamentos", f"forma IN ({FORMAS})")

    op.create_table(
        "convenio_compras",
        *_id_e_farmacia(),
        sa.Column("convenio_id", UUID(as_uuid=True), nullable=False),
        sa.Column("cliente_id", UUID(as_uuid=True), nullable=False),
        sa.Column("venda_id", UUID(as_uuid=True), nullable=False),
        sa.Column("loja_id", UUID(as_uuid=True), nullable=False),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("data", sa.Date, nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="aberta"),
        sa.Column("conta_id", UUID(as_uuid=True)),
        *_datas(),
        sa.UniqueConstraint("farmacia_id", "id"),
        sa.UniqueConstraint("farmacia_id", "venda_id", name="uq_convenio_compras_venda"),
        sa.ForeignKeyConstraint(["farmacia_id", "convenio_id"], ["convenios.farmacia_id", "convenios.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "cliente_id"], ["clientes.farmacia_id", "clientes.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "venda_id"], ["vendas.farmacia_id", "vendas.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "conta_id"], ["contas.farmacia_id", "contas.id"]),
        sa.CheckConstraint("status IN ('aberta', 'faturada', 'cancelada')", name="ck_convenio_compras_status"),
        sa.CheckConstraint("valor > 0", name="ck_convenio_compras_valor"),
    )
    op.create_index("ix_convenio_compras_aberto", "convenio_compras", ["farmacia_id", "convenio_id", "status", "data"])
    op.create_index("ix_convenio_compras_cliente", "convenio_compras", ["farmacia_id", "cliente_id", "status"])
    ativar_rls("convenio_compras")
    conceder_app("convenio_compras", "SELECT, INSERT, UPDATE")


def downgrade() -> None:
    op.drop_table("convenio_compras")
    op.drop_constraint("ck_pagamentos_forma", "venda_pagamentos")
    op.create_check_constraint("ck_pagamentos_forma", "venda_pagamentos", f"forma IN ({FORMAS_ANTIGAS})")
    op.drop_column("vendas", "desconto_convenio")
    op.drop_constraint("uq_contas_farmacia_id", "contas")
    op.drop_constraint("fk_contas_convenio", "contas")
    op.drop_column("contas", "convenio_id")
    op.drop_constraint("fk_clientes_convenio", "clientes")
    for coluna in ("convenio_limite", "convenio_matricula", "convenio_id"):
        op.drop_column("clientes", coluna)
    op.drop_table("convenios")
