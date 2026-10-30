"""Financeiro: contas a pagar e a receber, venda a prazo (fiado) e limite de crédito do cliente

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-30
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from migrations.helpers import FARMACIA_ATUAL, ativar_rls, conceder_app

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

FORMAS_ANTIGAS = "'dinheiro', 'debito', 'credito', 'pix'"
FORMAS = "'dinheiro', 'debito', 'credito', 'pix', 'prazo'"


def upgrade() -> None:
    op.add_column("farmacias", sa.Column("dias_prazo_padrao", sa.Integer, nullable=False, server_default="30"))
    op.create_check_constraint("ck_farmacias_dias_prazo", "farmacias", "dias_prazo_padrao BETWEEN 1 AND 180")

    # Sem limite (nulo ou zero), o cliente não compra a prazo.
    op.add_column("clientes", sa.Column("limite_credito", sa.Numeric(12, 2)))
    op.create_unique_constraint("uq_clientes_farmacia_id", "clientes", ["farmacia_id", "id"])

    op.add_column("vendas", sa.Column("cliente_id", UUID(as_uuid=True)))
    op.create_foreign_key(
        "fk_vendas_cliente", "vendas", "clientes", ["farmacia_id", "cliente_id"], ["farmacia_id", "id"]
    )
    op.drop_constraint("ck_pagamentos_forma", "venda_pagamentos")
    op.create_check_constraint("ck_pagamentos_forma", "venda_pagamentos", f"forma IN ({FORMAS})")

    op.create_table(
        "contas",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farmacia_id", UUID(as_uuid=True), sa.ForeignKey("farmacias.id"), nullable=False,
                  server_default=sa.text(FARMACIA_ATUAL)),
        sa.Column("tipo", sa.String(8), nullable=False),
        sa.Column("loja_id", UUID(as_uuid=True), nullable=False),
        sa.Column("descricao", sa.String(200), nullable=False),
        sa.Column("categoria", sa.String(30), nullable=False),
        sa.Column("fornecedor_id", UUID(as_uuid=True)),
        sa.Column("cliente_id", UUID(as_uuid=True)),
        sa.Column("documento", sa.String(60)),
        sa.Column("parcela", sa.Integer, nullable=False, server_default="1"),
        sa.Column("parcelas", sa.Integer, nullable=False, server_default="1"),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("vencimento", sa.Date, nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="aberta"),
        sa.Column("pago_em", sa.Date),
        sa.Column("valor_pago", sa.Numeric(12, 2)),
        sa.Column("forma_pagamento", sa.String(20)),
        # Recebimento em dinheiro feito num caixa aberto entra na conferência daquele caixa.
        sa.Column("caixa_id", UUID(as_uuid=True)),
        sa.Column("nota_entrada_id", UUID(as_uuid=True)),
        sa.Column("venda_id", UUID(as_uuid=True)),
        sa.Column("observacao", sa.String(300)),
        sa.Column("usuario_id", UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("baixada_por", UUID(as_uuid=True), sa.ForeignKey("usuarios.id")),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "fornecedor_id"], ["fornecedores.farmacia_id", "fornecedores.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "cliente_id"], ["clientes.farmacia_id", "clientes.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "caixa_id"], ["caixas.farmacia_id", "caixas.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "nota_entrada_id"], ["notas_entrada.farmacia_id", "notas_entrada.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "venda_id"], ["vendas.farmacia_id", "vendas.id"]),
        sa.CheckConstraint("tipo IN ('pagar', 'receber')", name="ck_contas_tipo"),
        sa.CheckConstraint("status IN ('aberta', 'paga', 'cancelada')", name="ck_contas_status"),
        sa.CheckConstraint("valor > 0", name="ck_contas_valor"),
        sa.CheckConstraint("parcela BETWEEN 1 AND parcelas", name="ck_contas_parcela"),
        sa.CheckConstraint(
            "(status = 'paga') = (pago_em IS NOT NULL AND valor_pago IS NOT NULL)", name="ck_contas_baixa"
        ),
    )
    op.create_index("ix_contas_vencimento", "contas", ["farmacia_id", "tipo", "status", "vencimento"])
    op.create_index("ix_contas_pago_em", "contas", ["farmacia_id", "pago_em"])
    op.create_index("ix_contas_cliente", "contas", ["farmacia_id", "cliente_id"],
                    postgresql_where=sa.text("cliente_id IS NOT NULL"))
    op.create_index("ix_contas_venda", "contas", ["farmacia_id", "venda_id"],
                    postgresql_where=sa.text("venda_id IS NOT NULL"))
    ativar_rls("contas")
    conceder_app("contas", "SELECT, INSERT, UPDATE")


def downgrade() -> None:
    op.drop_table("contas")
    op.execute("UPDATE venda_pagamentos SET forma = 'credito' WHERE forma = 'prazo'")
    op.drop_constraint("ck_pagamentos_forma", "venda_pagamentos")
    op.create_check_constraint("ck_pagamentos_forma", "venda_pagamentos", f"forma IN ({FORMAS_ANTIGAS})")
    op.drop_constraint("fk_vendas_cliente", "vendas")
    op.drop_column("vendas", "cliente_id")
    op.drop_constraint("uq_clientes_farmacia_id", "clientes")
    op.drop_column("clientes", "limite_credito")
    op.drop_constraint("ck_farmacias_dias_prazo", "farmacias")
    op.drop_column("farmacias", "dias_prazo_padrao")
