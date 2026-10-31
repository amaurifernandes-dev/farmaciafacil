"""Troca e devolução de itens da venda, com vale-troca

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from migrations.helpers import FARMACIA_ATUAL, ativar_rls, conceder_app

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

FORMAS_ANTIGAS = "'dinheiro', 'debito', 'credito', 'pix', 'prazo', 'convenio', 'popular'"
FORMAS = "'dinheiro', 'debito', 'credito', 'pix', 'prazo', 'convenio', 'popular', 'vale'"


def _comuns():
    return [
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farmacia_id", UUID(as_uuid=True), sa.ForeignKey("farmacias.id"), nullable=False,
                  server_default=sa.text(FARMACIA_ATUAL)),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    op.create_table(
        "vales_troca",
        *_comuns(),
        sa.Column("codigo", sa.String(10), nullable=False),
        sa.Column("cliente_id", UUID(as_uuid=True)),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("saldo", sa.Numeric(12, 2), nullable=False),
        sa.Column("validade", sa.Date, nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="ativo"),
        sa.UniqueConstraint("farmacia_id", "id"),
        sa.UniqueConstraint("farmacia_id", "codigo", name="uq_vales_troca_codigo"),
        sa.ForeignKeyConstraint(["farmacia_id", "cliente_id"], ["clientes.farmacia_id", "clientes.id"]),
        sa.CheckConstraint("valor > 0 AND saldo >= 0 AND saldo <= valor", name="ck_vales_troca_saldo"),
        sa.CheckConstraint("status IN ('ativo', 'usado', 'cancelado')", name="ck_vales_troca_status"),
    )
    ativar_rls("vales_troca")
    conceder_app("vales_troca", "SELECT, INSERT, UPDATE")

    op.create_table(
        "devolucoes",
        *_comuns(),
        sa.Column("numero", sa.Integer, nullable=False),
        sa.Column("venda_id", UUID(as_uuid=True), nullable=False),
        sa.Column("loja_id", UUID(as_uuid=True), nullable=False),
        sa.Column("usuario_id", UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("destino", sa.String(10), nullable=False),
        sa.Column("caixa_id", UUID(as_uuid=True)),  # o dinheiro saiu da gaveta deste caixa
        sa.Column("vale_id", UUID(as_uuid=True)),
        sa.Column("valor_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("motivo", sa.String(200), nullable=False),
        sa.UniqueConstraint("farmacia_id", "id"),
        sa.UniqueConstraint("farmacia_id", "numero", name="uq_devolucoes_numero"),
        sa.ForeignKeyConstraint(["farmacia_id", "venda_id"], ["vendas.farmacia_id", "vendas.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "caixa_id"], ["caixas.farmacia_id", "caixas.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "vale_id"], ["vales_troca.farmacia_id", "vales_troca.id"]),
        sa.CheckConstraint("destino IN ('dinheiro', 'vale')", name="ck_devolucoes_destino"),
        sa.CheckConstraint("valor_total >= 0", name="ck_devolucoes_valor"),
        sa.CheckConstraint("(destino = 'vale') = (vale_id IS NOT NULL)", name="ck_devolucoes_vale"),
    )
    op.create_index("ix_devolucoes_venda", "devolucoes", ["farmacia_id", "venda_id"])
    op.create_index("ix_devolucoes_caixa", "devolucoes", ["caixa_id"])
    ativar_rls("devolucoes")
    conceder_app("devolucoes", "SELECT, INSERT")

    op.create_table(
        "devolucao_itens",
        *_comuns(),
        sa.Column("devolucao_id", UUID(as_uuid=True), nullable=False),
        sa.Column("venda_item_id", UUID(as_uuid=True), nullable=False),
        sa.Column("produto_id", UUID(as_uuid=True), nullable=False),
        sa.Column("descricao", sa.String(200), nullable=False),
        sa.Column("quantidade", sa.Numeric(12, 3), nullable=False),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("volta_estoque", sa.Boolean, nullable=False),
        sa.ForeignKeyConstraint(["farmacia_id", "devolucao_id"], ["devolucoes.farmacia_id", "devolucoes.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["farmacia_id", "produto_id"], ["produtos.farmacia_id", "produtos.id"]),
        sa.ForeignKeyConstraint(["venda_item_id"], ["venda_itens.id"]),
        sa.CheckConstraint("quantidade > 0", name="ck_devolucao_itens_quantidade"),
        sa.CheckConstraint("valor >= 0", name="ck_devolucao_itens_valor"),
    )
    op.create_index("ix_devolucao_itens_venda_item", "devolucao_itens", ["venda_item_id"])
    ativar_rls("devolucao_itens")
    conceder_app("devolucao_itens", "SELECT, INSERT")

    # O vale-troca vira forma de pagamento no PDV.
    op.add_column("venda_pagamentos", sa.Column("vale_id", UUID(as_uuid=True)))
    op.create_foreign_key("fk_venda_pagamentos_vale", "venda_pagamentos", "vales_troca",
                          ["farmacia_id", "vale_id"], ["farmacia_id", "id"])
    op.drop_constraint("ck_pagamentos_forma", "venda_pagamentos")
    op.create_check_constraint("ck_pagamentos_forma", "venda_pagamentos", f"forma IN ({FORMAS})")


def downgrade() -> None:
    op.drop_constraint("ck_pagamentos_forma", "venda_pagamentos")
    op.create_check_constraint("ck_pagamentos_forma", "venda_pagamentos", f"forma IN ({FORMAS_ANTIGAS})")
    op.drop_constraint("fk_venda_pagamentos_vale", "venda_pagamentos")
    op.drop_column("venda_pagamentos", "vale_id")
    op.drop_table("devolucao_itens")
    op.drop_table("devolucoes")
    op.drop_table("vales_troca")
