"""Promoções por produto e período; custo e promoção gravados no item vendido (para os relatórios)

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-30
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from migrations.helpers import FARMACIA_ATUAL, ativar_rls, conceder_app

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def _farmacia():
    return sa.Column("farmacia_id", UUID(as_uuid=True), sa.ForeignKey("farmacias.id"), nullable=False,
                     server_default=sa.text(FARMACIA_ATUAL))


def _datas():
    return [
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    op.create_table(
        "promocoes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        _farmacia(),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("tipo", sa.String(12), nullable=False),
        sa.Column("percentual", sa.Numeric(5, 2)),
        sa.Column("preco", sa.Numeric(12, 2)),
        sa.Column("leve", sa.Integer),
        sa.Column("pague", sa.Integer),
        sa.Column("inicio", sa.Date, nullable=False),
        sa.Column("fim", sa.Date),
        sa.Column("so_clientes", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("loja_id", UUID(as_uuid=True)),
        sa.Column("ativa", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("usuario_id", UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        *_datas(),
        sa.UniqueConstraint("farmacia_id", "id"),
        sa.ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
        sa.CheckConstraint("tipo IN ('percentual', 'preco_fixo', 'leve_pague')", name="ck_promocoes_tipo"),
        sa.CheckConstraint(
            "(tipo = 'percentual' AND percentual > 0 AND percentual < 100)"
            " OR (tipo = 'preco_fixo' AND preco > 0)"
            " OR (tipo = 'leve_pague' AND pague >= 1 AND leve > pague)",
            name="ck_promocoes_regra",
        ),
        sa.CheckConstraint("fim IS NULL OR fim >= inicio", name="ck_promocoes_periodo"),
    )
    op.create_index("ix_promocoes_periodo", "promocoes", ["farmacia_id", "ativa", "inicio", "fim"])
    ativar_rls("promocoes")
    conceder_app("promocoes", "SELECT, INSERT, UPDATE")

    op.create_table(
        "promocao_produtos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        _farmacia(),
        sa.Column("promocao_id", UUID(as_uuid=True), nullable=False),
        sa.Column("produto_id", UUID(as_uuid=True), nullable=False),
        *_datas(),
        sa.UniqueConstraint("farmacia_id", "promocao_id", "produto_id"),
        sa.ForeignKeyConstraint(["farmacia_id", "promocao_id"], ["promocoes.farmacia_id", "promocoes.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["farmacia_id", "produto_id"], ["produtos.farmacia_id", "produtos.id"]),
    )
    op.create_index("ix_promocao_produtos_produto", "promocao_produtos", ["farmacia_id", "produto_id"])
    ativar_rls("promocao_produtos")
    conceder_app("promocao_produtos", "SELECT, INSERT, DELETE")

    # Custo do produto no momento da venda: o lucro do relatório não muda quando o custo muda depois.
    op.add_column("venda_itens", sa.Column("custo_unitario", sa.Numeric(12, 4)))
    op.add_column("venda_itens", sa.Column("promocao_id", UUID(as_uuid=True)))
    op.add_column("venda_itens", sa.Column("desconto_promocao", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.create_foreign_key("fk_venda_itens_promocao", "venda_itens", "promocoes",
                          ["farmacia_id", "promocao_id"], ["farmacia_id", "id"])
    op.create_index("ix_venda_itens_promocao", "venda_itens", ["farmacia_id", "promocao_id"],
                    postgresql_where=sa.text("promocao_id IS NOT NULL"))
    op.create_index("ix_venda_itens_produto", "venda_itens", ["farmacia_id", "produto_id"])


def downgrade() -> None:
    op.drop_index("ix_venda_itens_produto", "venda_itens")
    op.drop_index("ix_venda_itens_promocao", "venda_itens")
    op.drop_constraint("fk_venda_itens_promocao", "venda_itens")
    op.drop_column("venda_itens", "desconto_promocao")
    op.drop_column("venda_itens", "promocao_id")
    op.drop_column("venda_itens", "custo_unitario")
    op.drop_table("promocao_produtos")
    op.drop_table("promocoes")
