"""PDV: caixas, vendas, itens e pagamentos

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-29
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from migrations.helpers import FARMACIA_ATUAL, ativar_rls, conceder_app

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


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
    op.create_table(
        "caixas",
        *_base(),
        sa.Column("usuario_id", UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="aberto"),
        sa.Column("valor_abertura", sa.Numeric(12, 2), nullable=False),
        sa.Column("aberto_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fechado_em", sa.DateTime(timezone=True)),
        sa.Column("valor_fechamento_informado", sa.Numeric(12, 2)),
        *_datas(),
        sa.UniqueConstraint("farmacia_id", "id"),
        sa.CheckConstraint("status IN ('aberto', 'fechado')", name="ck_caixas_status"),
    )
    # Um operador só pode ter um caixa aberto por vez.
    op.create_index(
        "ux_caixas_um_aberto_por_usuario", "caixas", ["usuario_id"],
        unique=True, postgresql_where=sa.text("status = 'aberto'"),
    )
    ativar_rls("caixas")
    conceder_app("caixas", "SELECT, INSERT, UPDATE")

    op.create_table(
        "vendas",
        *_base(),
        sa.Column("caixa_id", UUID(as_uuid=True), nullable=False),
        sa.Column("usuario_id", UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("numero", sa.Integer, nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="finalizada"),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("desconto", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("troco", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("cliente_cpf", sa.String(11)),
        sa.Column("chave_idempotencia", UUID(as_uuid=True), nullable=False),
        sa.Column("finalizada_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelada_em", sa.DateTime(timezone=True)),
        sa.Column("motivo_cancelamento", sa.String(200)),
        *_datas(),
        sa.UniqueConstraint("farmacia_id", "id"),
        sa.UniqueConstraint("farmacia_id", "numero"),
        sa.UniqueConstraint("farmacia_id", "chave_idempotencia"),
        sa.ForeignKeyConstraint(["farmacia_id", "caixa_id"], ["caixas.farmacia_id", "caixas.id"]),
        sa.CheckConstraint("status IN ('finalizada', 'cancelada')", name="ck_vendas_status"),
        sa.CheckConstraint("total = subtotal - desconto AND total >= 0", name="ck_vendas_total"),
    )
    op.create_index("ix_vendas_caixa", "vendas", ["farmacia_id", "caixa_id"])
    op.create_index("ix_vendas_data", "vendas", ["farmacia_id", "finalizada_em"])
    ativar_rls("vendas")
    conceder_app("vendas", "SELECT, INSERT, UPDATE")

    op.create_table(
        "venda_itens",
        *_base(),
        sa.Column("venda_id", UUID(as_uuid=True), nullable=False),
        sa.Column("ordem", sa.Integer, nullable=False),
        sa.Column("produto_id", UUID(as_uuid=True), nullable=False),
        sa.Column("descricao", sa.String(200), nullable=False),
        sa.Column("quantidade", sa.Numeric(12, 3), nullable=False),
        sa.Column("preco_unitario", sa.Numeric(12, 2), nullable=False),
        sa.Column("desconto", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        *_datas(),
        sa.ForeignKeyConstraint(["farmacia_id", "venda_id"], ["vendas.farmacia_id", "vendas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["farmacia_id", "produto_id"], ["produtos.farmacia_id", "produtos.id"]),
        sa.CheckConstraint("quantidade > 0", name="ck_venda_itens_quantidade"),
    )
    op.create_index("ix_venda_itens_venda", "venda_itens", ["venda_id"])
    ativar_rls("venda_itens")
    conceder_app("venda_itens", "SELECT, INSERT")

    op.create_table(
        "venda_pagamentos",
        *_base(),
        sa.Column("venda_id", UUID(as_uuid=True), nullable=False),
        sa.Column("forma", sa.String(10), nullable=False),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        *_datas(),
        sa.ForeignKeyConstraint(["farmacia_id", "venda_id"], ["vendas.farmacia_id", "vendas.id"], ondelete="CASCADE"),
        sa.CheckConstraint("forma IN ('dinheiro', 'debito', 'credito', 'pix')", name="ck_pagamentos_forma"),
        sa.CheckConstraint("valor > 0", name="ck_pagamentos_valor"),
    )
    op.create_index("ix_venda_pagamentos_venda", "venda_pagamentos", ["venda_id"])
    ativar_rls("venda_pagamentos")
    conceder_app("venda_pagamentos", "SELECT, INSERT")


def downgrade() -> None:
    op.drop_table("venda_pagamentos")
    op.drop_table("venda_itens")
    op.drop_table("vendas")
    op.drop_table("caixas")
