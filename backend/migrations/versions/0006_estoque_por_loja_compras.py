"""Estoque por loja, transferências e compras: notas de entrada pelo XML e códigos do fornecedor

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-30
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from migrations.helpers import FARMACIA_ATUAL, ativar_rls, conceder_app

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

TIPOS_ANTIGOS = "'entrada', 'venda', 'ajuste', 'perda', 'devolucao'"
TIPOS = "'entrada', 'venda', 'ajuste', 'perda', 'devolucao', 'transferencia'"


def _base() -> list[sa.Column]:
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
    # --- Lotes passam a ser de uma loja. O estoque que já existe fica na matriz. ---
    op.add_column("lotes", sa.Column("loja_id", UUID(as_uuid=True)))
    op.execute("UPDATE lotes t SET loja_id = l.id FROM lojas l WHERE l.farmacia_id = t.farmacia_id AND l.matriz")
    op.alter_column("lotes", "loja_id", nullable=False)
    op.create_foreign_key("fk_lotes_loja", "lotes", "lojas", ["farmacia_id", "loja_id"], ["farmacia_id", "id"])
    op.drop_constraint("lotes_farmacia_id_produto_id_numero_lote_key", "lotes")
    op.create_unique_constraint(
        "uq_lotes_loja_produto_numero", "lotes", ["farmacia_id", "loja_id", "produto_id", "numero_lote"]
    )

    op.add_column("movimentos_estoque", sa.Column("loja_id", UUID(as_uuid=True)))
    op.execute("UPDATE movimentos_estoque m SET loja_id = t.loja_id FROM lotes t WHERE t.id = m.lote_id")
    op.alter_column("movimentos_estoque", "loja_id", nullable=False)
    op.create_foreign_key(
        "fk_movimentos_loja", "movimentos_estoque", "lojas", ["farmacia_id", "loja_id"], ["farmacia_id", "id"]
    )
    # Usado pela sugestão de compras (quanto saiu por produto e loja num período).
    op.create_index(
        "ix_movimentos_loja_tipo", "movimentos_estoque", ["farmacia_id", "loja_id", "tipo", "criado_em"]
    )
    op.drop_constraint("ck_movimentos_tipo", "movimentos_estoque")
    op.create_check_constraint("ck_movimentos_tipo", "movimentos_estoque", f"tipo IN ({TIPOS})")

    # --- Notas de compra importadas pelo XML da NF-e ---
    op.create_unique_constraint("uq_fornecedores_farmacia_id", "fornecedores", ["farmacia_id", "id"])
    op.create_table(
        "notas_entrada",
        *_base(),
        sa.Column("loja_id", UUID(as_uuid=True), nullable=False),
        sa.Column("fornecedor_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chave", sa.String(44), nullable=False),
        sa.Column("numero", sa.Integer, nullable=False),
        sa.Column("serie", sa.Integer, nullable=False),
        sa.Column("emitida_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valor_produtos", sa.Numeric(12, 2), nullable=False),
        sa.Column("valor_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="pendente"),
        sa.Column("usuario_id", UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("confirmada_em", sa.DateTime(timezone=True)),
        sa.Column("xml", sa.Text, nullable=False),
        *_datas(),
        sa.UniqueConstraint("farmacia_id", "id"),
        sa.ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "fornecedor_id"], ["fornecedores.farmacia_id", "fornecedores.id"]),
        sa.CheckConstraint("status IN ('pendente', 'confirmada', 'cancelada')", name="ck_notas_entrada_status"),
    )
    # A mesma nota não entra duas vezes (a não ser que a primeira tenha sido cancelada).
    op.create_index(
        "ux_notas_entrada_chave", "notas_entrada", ["farmacia_id", "chave"],
        unique=True, postgresql_where=sa.text("status <> 'cancelada'"),
    )
    ativar_rls("notas_entrada")
    conceder_app("notas_entrada", "SELECT, INSERT, UPDATE")

    op.create_table(
        "notas_entrada_itens",
        *_base(),
        sa.Column("nota_id", UUID(as_uuid=True), nullable=False),
        sa.Column("ordem", sa.Integer, nullable=False),
        sa.Column("codigo_fornecedor", sa.String(60), nullable=False),
        sa.Column("ean", sa.String(14)),
        sa.Column("descricao", sa.String(200), nullable=False),
        sa.Column("ncm", sa.String(8)),
        sa.Column("cest", sa.String(7)),
        sa.Column("registro_ms", sa.String(20)),
        sa.Column("unidade", sa.String(6), nullable=False),
        sa.Column("quantidade", sa.Numeric(12, 3), nullable=False),
        sa.Column("valor_unitario", sa.Numeric(14, 4), nullable=False),
        sa.Column("valor_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("numero_lote", sa.String(40)),
        sa.Column("validade", sa.Date),
        sa.Column("produto_id", UUID(as_uuid=True)),
        # Quantas unidades de venda vêm em cada unidade da nota (ex.: caixa com 10).
        sa.Column("fator", sa.Integer, nullable=False, server_default="1"),
        *_datas(),
        sa.ForeignKeyConstraint(
            ["farmacia_id", "nota_id"], ["notas_entrada.farmacia_id", "notas_entrada.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["farmacia_id", "produto_id"], ["produtos.farmacia_id", "produtos.id"]),
        sa.CheckConstraint("fator >= 1", name="ck_notas_entrada_itens_fator"),
    )
    op.create_index("ix_notas_entrada_itens_nota", "notas_entrada_itens", ["farmacia_id", "nota_id"])
    op.create_index("ix_notas_entrada_itens_produto", "notas_entrada_itens", ["farmacia_id", "produto_id"])
    ativar_rls("notas_entrada_itens")
    conceder_app("notas_entrada_itens", "SELECT, INSERT, UPDATE")

    # --- Código que cada fornecedor usa para o produto, aprendido nas notas ---
    op.create_table(
        "produtos_fornecedor",
        *_base(),
        sa.Column("fornecedor_id", UUID(as_uuid=True), nullable=False),
        sa.Column("codigo", sa.String(60), nullable=False),
        sa.Column("produto_id", UUID(as_uuid=True), nullable=False),
        sa.Column("fator", sa.Integer, nullable=False, server_default="1"),
        *_datas(),
        sa.UniqueConstraint("farmacia_id", "fornecedor_id", "codigo"),
        sa.ForeignKeyConstraint(["farmacia_id", "fornecedor_id"], ["fornecedores.farmacia_id", "fornecedores.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "produto_id"], ["produtos.farmacia_id", "produtos.id"]),
        sa.CheckConstraint("fator >= 1", name="ck_produtos_fornecedor_fator"),
    )
    ativar_rls("produtos_fornecedor")
    conceder_app("produtos_fornecedor", "SELECT, INSERT, UPDATE")


def downgrade() -> None:
    op.drop_table("produtos_fornecedor")
    op.drop_table("notas_entrada_itens")
    op.drop_table("notas_entrada")
    op.drop_constraint("uq_fornecedores_farmacia_id", "fornecedores")

    # Junta de volta os lotes de mesmo número que estavam em lojas diferentes não é possível
    # sem perder histórico: o downgrade só funciona se cada lote existir numa loja só.
    op.execute("DELETE FROM movimentos_estoque WHERE tipo = 'transferencia'")
    op.drop_constraint("ck_movimentos_tipo", "movimentos_estoque")
    op.create_check_constraint("ck_movimentos_tipo", "movimentos_estoque", f"tipo IN ({TIPOS_ANTIGOS})")
    op.drop_index("ix_movimentos_loja_tipo", "movimentos_estoque")
    op.drop_constraint("fk_movimentos_loja", "movimentos_estoque")
    op.drop_column("movimentos_estoque", "loja_id")

    op.drop_constraint("uq_lotes_loja_produto_numero", "lotes")
    op.create_unique_constraint(
        "lotes_farmacia_id_produto_id_numero_lote_key", "lotes", ["farmacia_id", "produto_id", "numero_lote"]
    )
    op.drop_constraint("fk_lotes_loja", "lotes")
    op.drop_column("lotes", "loja_id")
