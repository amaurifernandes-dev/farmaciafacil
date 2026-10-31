"""Inventário: contagem do estoque de uma loja e ajuste das diferenças

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from migrations.helpers import FARMACIA_ATUAL, ativar_rls, conceder_app

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


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
        "inventarios",
        *_comuns(),
        sa.Column("loja_id", UUID(as_uuid=True), nullable=False),
        sa.Column("descricao", sa.String(80), nullable=False),
        # geral: o que não foi contado fica com zero; parcial: só mexe no que foi contado.
        sa.Column("escopo", sa.String(10), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="aberto"),
        sa.Column("aberto_por", UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("finalizado_por", UUID(as_uuid=True), sa.ForeignKey("usuarios.id")),
        sa.Column("finalizado_em", sa.DateTime(timezone=True)),
        sa.Column("produtos_ajustados", sa.Integer),
        sa.Column("valor_sobra", sa.Numeric(12, 2)),
        sa.Column("valor_falta", sa.Numeric(12, 2)),
        sa.UniqueConstraint("farmacia_id", "id"),
        sa.ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
        sa.CheckConstraint("escopo IN ('geral', 'parcial')", name="ck_inventarios_escopo"),
        sa.CheckConstraint("status IN ('aberto', 'finalizado', 'cancelado')", name="ck_inventarios_status"),
    )
    # Uma contagem aberta por loja de cada vez.
    op.create_index("uq_inventarios_aberto", "inventarios", ["farmacia_id", "loja_id"], unique=True,
                    postgresql_where=sa.text("status = 'aberto'"))
    ativar_rls("inventarios")
    conceder_app("inventarios", "SELECT, INSERT, UPDATE")

    op.create_table(
        "inventario_itens",
        *_comuns(),
        sa.Column("inventario_id", UUID(as_uuid=True), nullable=False),
        sa.Column("produto_id", UUID(as_uuid=True), nullable=False),
        sa.Column("quantidade", sa.Numeric(12, 3), nullable=False),
        # Saldo do sistema na hora da contagem: a venda feita depois não vira diferença.
        sa.Column("saldo_sistema", sa.Numeric(12, 3), nullable=False),
        sa.Column("custo_unitario", sa.Numeric(12, 2)),
        sa.Column("contado", sa.Boolean, nullable=False, server_default=sa.true()),  # false: geral, ficou sem contar
        sa.Column("usuario_id", UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.UniqueConstraint("farmacia_id", "inventario_id", "produto_id", name="uq_inventario_itens_produto"),
        sa.ForeignKeyConstraint(["farmacia_id", "inventario_id"], ["inventarios.farmacia_id", "inventarios.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "produto_id"], ["produtos.farmacia_id", "produtos.id"]),
        sa.CheckConstraint("quantidade >= 0", name="ck_inventario_itens_quantidade"),
    )
    ativar_rls("inventario_itens")
    conceder_app("inventario_itens")


def downgrade() -> None:
    op.drop_table("inventario_itens")
    op.drop_table("inventarios")
