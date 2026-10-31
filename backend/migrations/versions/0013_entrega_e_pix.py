"""Taxa de entrega por bairro e Pix na loja online

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def _dinheiro(nome: str) -> sa.Column:
    return sa.Column(nome, sa.Numeric(12, 2), nullable=False, server_default="0")


def upgrade() -> None:
    op.add_column("farmacias", _dinheiro("entrega_taxa"))
    op.add_column("farmacias", sa.Column("entrega_gratis_acima", sa.Numeric(12, 2)))
    op.add_column("farmacias", sa.Column("entrega_bairros", JSONB, nullable=False, server_default="[]"))
    op.add_column("farmacias", sa.Column("pix_chave", sa.String(77)))
    op.add_column("farmacias", sa.Column("pix_nome", sa.String(25)))
    op.add_column("farmacias", sa.Column("pix_cidade", sa.String(15)))
    op.add_column("farmacias", sa.Column("pix_no_site", sa.Boolean, nullable=False, server_default=sa.false()))

    op.add_column("pedidos", sa.Column("bairro", sa.String(60)))
    op.add_column("pedidos", _dinheiro("taxa_entrega"))
    op.add_column("pedidos", sa.Column("pix_txid", sa.String(25)))
    op.add_column("pedidos", sa.Column("pix_pago_em", sa.DateTime(timezone=True)))
    op.add_column("pedidos", sa.Column("pix_confirmado_por", sa.dialects.postgresql.UUID(as_uuid=True)))

    for tabela in ("pre_vendas", "vendas"):
        op.add_column(tabela, sa.Column("entrega", sa.Boolean, nullable=False, server_default=sa.false()))
        op.add_column(tabela, _dinheiro("taxa_entrega"))
    op.add_column("pre_vendas", _dinheiro("pago_antecipado"))
    op.drop_constraint("ck_vendas_total", "vendas")
    op.create_check_constraint("ck_vendas_total", "vendas",
                               "total = subtotal - desconto + taxa_entrega AND total >= 0 AND taxa_entrega >= 0")


def downgrade() -> None:
    op.drop_constraint("ck_vendas_total", "vendas")
    op.create_check_constraint("ck_vendas_total", "vendas", "total = subtotal - desconto AND total >= 0")
    op.drop_column("pre_vendas", "pago_antecipado")
    for tabela in ("vendas", "pre_vendas"):
        op.drop_column(tabela, "taxa_entrega")
        op.drop_column(tabela, "entrega")
    for coluna in ("pix_confirmado_por", "pix_pago_em", "pix_txid", "taxa_entrega", "bairro"):
        op.drop_column("pedidos", coluna)
    for coluna in ("pix_no_site", "pix_cidade", "pix_nome", "pix_chave", "entrega_bairros", "entrega_gratis_acima",
                   "entrega_taxa"):
        op.drop_column("farmacias", coluna)
