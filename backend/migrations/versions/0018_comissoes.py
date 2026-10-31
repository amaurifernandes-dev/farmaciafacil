"""Comissão dos vendedores: quem vendeu e o percentual de cada item

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("farmacias", sa.Column("comissao_padrao", sa.Numeric(5, 2), nullable=False, server_default="0"))
    op.create_check_constraint("ck_farmacias_comissao", "farmacias", "comissao_padrao BETWEEN 0 AND 100")
    op.add_column("produtos", sa.Column("comissao", sa.Numeric(5, 2)))
    op.create_check_constraint("ck_produtos_comissao", "produtos", "comissao IS NULL OR comissao BETWEEN 0 AND 100")
    op.add_column("usuarios", sa.Column("recebe_comissao", sa.Boolean, nullable=False, server_default=sa.true()))

    # Quem vendeu: o balconista que fez a pré-venda, ou quem passou no caixa.
    op.add_column("vendas", sa.Column("vendedor_id", sa.dialects.postgresql.UUID(as_uuid=True)))
    op.execute(
        """
        UPDATE vendas v SET vendedor_id = COALESCE(
            (SELECT p.usuario_id FROM pre_vendas p WHERE p.venda_id = v.id AND p.farmacia_id = v.farmacia_id LIMIT 1),
            v.usuario_id)
        """
    )
    op.alter_column("vendas", "vendedor_id", nullable=False)
    op.create_index("ix_vendas_vendedor", "vendas", ["farmacia_id", "vendedor_id", "finalizada_em"])

    # Percentual da comissão no dia da venda. Vazio nas vendas de antes: vale a regra de hoje.
    op.add_column("venda_itens", sa.Column("comissao", sa.Numeric(5, 2)))


def downgrade() -> None:
    op.drop_column("venda_itens", "comissao")
    op.drop_index("ix_vendas_vendedor", "vendas")
    op.drop_column("vendas", "vendedor_id")
    op.drop_column("usuarios", "recebe_comissao")
    op.drop_constraint("ck_produtos_comissao", "produtos")
    op.drop_column("produtos", "comissao")
    op.drop_constraint("ck_farmacias_comissao", "farmacias")
    op.drop_column("farmacias", "comissao_padrao")
