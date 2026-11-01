"""Pedidos de compra guardados por fornecedor, conferidos quando a nota chega

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from migrations.helpers import FARMACIA_ATUAL, ativar_rls, conceder_app

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def _base() -> list:
    return [
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farmacia_id", UUID(as_uuid=True), sa.ForeignKey("farmacias.id"), nullable=False,
                  server_default=sa.text(FARMACIA_ATUAL)),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    op.create_table(
        "pedidos_compra",
        *_base(),
        sa.Column("numero", sa.Integer, nullable=False),
        sa.Column("loja_id", UUID(as_uuid=True), nullable=False),
        sa.Column("fornecedor_id", UUID(as_uuid=True), nullable=False),
        sa.Column("usuario_id", UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="aberto"),
        sa.Column("enviado_em", sa.DateTime(timezone=True)),
        sa.Column("observacao", sa.String(500)),
        sa.UniqueConstraint("farmacia_id", "id"),
        sa.UniqueConstraint("farmacia_id", "numero", name="uq_pedidos_compra_numero"),
        sa.ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "fornecedor_id"], ["fornecedores.farmacia_id", "fornecedores.id"]),
        sa.CheckConstraint(
            "status IN ('aberto', 'enviado', 'parcial', 'recebido', 'cancelado')", name="ck_pedidos_compra_status"
        ),
    )
    op.create_index("ix_pedidos_compra_fornecedor", "pedidos_compra", ["farmacia_id", "fornecedor_id", "status"])
    ativar_rls("pedidos_compra")
    conceder_app("pedidos_compra", "SELECT, INSERT, UPDATE")

    op.create_table(
        "pedidos_compra_itens",
        *_base(),
        sa.Column("pedido_id", UUID(as_uuid=True), nullable=False),
        sa.Column("produto_id", UUID(as_uuid=True), nullable=False),
        sa.Column("quantidade", sa.Numeric(12, 3), nullable=False),
        sa.Column("custo_estimado", sa.Numeric(14, 4)),
        sa.Column("recebido", sa.Numeric(12, 3), nullable=False, server_default="0"),
        sa.UniqueConstraint("farmacia_id", "pedido_id", "produto_id", name="uq_pedidos_compra_itens_produto"),
        sa.ForeignKeyConstraint(
            ["farmacia_id", "pedido_id"], ["pedidos_compra.farmacia_id", "pedidos_compra.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["farmacia_id", "produto_id"], ["produtos.farmacia_id", "produtos.id"]),
        sa.CheckConstraint("quantidade > 0", name="ck_pedidos_compra_itens_quantidade"),
        sa.CheckConstraint("recebido >= 0", name="ck_pedidos_compra_itens_recebido"),
    )
    ativar_rls("pedidos_compra_itens")
    conceder_app("pedidos_compra_itens", "SELECT, INSERT, UPDATE, DELETE")

    # A nota que chega fica ligada ao pedido que ela atende.
    op.add_column("notas_entrada", sa.Column("pedido_id", UUID(as_uuid=True)))
    op.create_foreign_key(
        "fk_notas_entrada_pedido", "notas_entrada", "pedidos_compra",
        ["farmacia_id", "pedido_id"], ["farmacia_id", "id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_notas_entrada_pedido", "notas_entrada", type_="foreignkey")
    op.drop_column("notas_entrada", "pedido_id")
    op.drop_table("pedidos_compra_itens")
    op.drop_table("pedidos_compra")
