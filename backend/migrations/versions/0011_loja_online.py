"""Loja online e pedidos de outros canais (site, WhatsApp, telefone)

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-30
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.core.config import get_settings
from migrations.helpers import FARMACIA_ATUAL, ativar_rls, conceder_app

revision = "0011"
down_revision = "0010"
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
    app_role = get_settings().app_db_role

    op.add_column("farmacias", sa.Column("loja_online_ativa", sa.Boolean, nullable=False, server_default="false"))
    op.add_column("farmacias", sa.Column("loja_online_endereco", sa.String(40), unique=True))
    op.add_column("farmacias", sa.Column("loja_online_loja_id", UUID(as_uuid=True)))
    op.add_column("farmacias", sa.Column("loja_online_mensagem", sa.String(300)))
    op.add_column("farmacias", sa.Column("whatsapp", sa.String(20)))
    op.add_column("farmacias", sa.Column("entrega_ativa", sa.Boolean, nullable=False, server_default="false"))
    op.add_column("farmacias", sa.Column("entrega_minimo", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("farmacias", sa.Column("entrega_area", sa.String(200)))
    op.create_check_constraint(
        "ck_farmacias_loja_online_endereco", "farmacias", "loja_online_endereco ~ '^[a-z0-9]+(-[a-z0-9]+)*$'"
    )

    # Remédio com receita não vai para o site: só o que a farmácia marcar.
    op.add_column("produtos", sa.Column("vende_online", sa.Boolean, nullable=False, server_default="true"))
    op.execute("UPDATE produtos SET vende_online = false WHERE tipo = 'medicamento'")

    # A loja online é pública: acha a farmácia pelo endereço antes de saber quem é.
    # SECURITY DEFINER roda sem RLS e devolve só o id de uma farmácia com a loja ligada.
    op.execute(
        """
        CREATE FUNCTION loja_online_farmacia(p_endereco text) RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
        AS $$
            SELECT id FROM farmacias
            WHERE loja_online_endereco = lower(p_endereco) AND loja_online_ativa AND ativo
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION loja_online_farmacia(text) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION loja_online_farmacia(text) TO {app_role}")

    op.create_foreign_key("fk_farmacias_loja_online_loja", "farmacias", "lojas",
                          ["id", "loja_online_loja_id"], ["farmacia_id", "id"])
    op.create_unique_constraint("uq_pre_vendas_farmacia_id", "pre_vendas", ["farmacia_id", "id"])

    op.create_table(
        "pedidos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        _farmacia(),
        sa.Column("numero", sa.Integer, nullable=False),
        sa.Column("codigo", sa.String(16), nullable=False),
        sa.Column("canal", sa.String(10), nullable=False),
        sa.Column("loja_id", UUID(as_uuid=True), nullable=False),
        sa.Column("cliente_id", UUID(as_uuid=True)),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("telefone", sa.String(20), nullable=False),
        sa.Column("entrega", sa.Boolean, nullable=False),
        sa.Column("endereco", sa.String(300)),
        sa.Column("forma_pagamento", sa.String(10), nullable=False),
        sa.Column("troco_para", sa.Numeric(12, 2)),
        sa.Column("observacao", sa.String(300)),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="novo"),
        sa.Column("motivo_cancelamento", sa.String(200)),
        sa.Column("pre_venda_id", UUID(as_uuid=True)),
        sa.Column("usuario_id", UUID(as_uuid=True), sa.ForeignKey("usuarios.id")),
        *_datas(),
        sa.UniqueConstraint("farmacia_id", "id"),
        sa.UniqueConstraint("farmacia_id", "numero"),
        sa.UniqueConstraint("codigo"),
        sa.ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "cliente_id"], ["clientes.farmacia_id", "clientes.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "pre_venda_id"], ["pre_vendas.farmacia_id", "pre_vendas.id"]),
        sa.CheckConstraint("canal IN ('site', 'whatsapp', 'telefone')", name="ck_pedidos_canal"),
        sa.CheckConstraint(
            "status IN ('novo', 'separando', 'pronto', 'saiu', 'entregue', 'cancelado')", name="ck_pedidos_status"
        ),
        sa.CheckConstraint("forma_pagamento IN ('dinheiro', 'cartao', 'pix')", name="ck_pedidos_pagamento"),
        sa.CheckConstraint("NOT entrega OR endereco IS NOT NULL", name="ck_pedidos_endereco"),
    )
    op.create_index("ix_pedidos_status", "pedidos", ["farmacia_id", "status"])
    ativar_rls("pedidos")
    conceder_app("pedidos", "SELECT, INSERT, UPDATE")

    op.create_table(
        "pedido_itens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        _farmacia(),
        sa.Column("pedido_id", UUID(as_uuid=True), nullable=False),
        sa.Column("produto_id", UUID(as_uuid=True), nullable=False),
        sa.Column("descricao", sa.String(400), nullable=False),
        sa.Column("quantidade", sa.Numeric(12, 3), nullable=False),
        sa.Column("preco_unitario", sa.Numeric(12, 2), nullable=False),
        sa.Column("desconto", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        *_datas(),
        sa.ForeignKeyConstraint(["farmacia_id", "pedido_id"], ["pedidos.farmacia_id", "pedidos.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["farmacia_id", "produto_id"], ["produtos.farmacia_id", "produtos.id"]),
        sa.CheckConstraint("quantidade > 0", name="ck_pedido_itens_quantidade"),
    )
    op.create_index("ix_pedido_itens_pedido", "pedido_itens", ["farmacia_id", "pedido_id"])
    ativar_rls("pedido_itens")
    conceder_app("pedido_itens", "SELECT, INSERT")


def downgrade() -> None:
    op.drop_table("pedido_itens")
    op.drop_table("pedidos")
    op.drop_constraint("uq_pre_vendas_farmacia_id", "pre_vendas")
    op.drop_constraint("fk_farmacias_loja_online_loja", "farmacias")
    op.execute("DROP FUNCTION loja_online_farmacia(text)")
    op.drop_column("produtos", "vende_online")
    op.drop_constraint("ck_farmacias_loja_online_endereco", "farmacias")
    for coluna in ("entrega_area", "entrega_minimo", "entrega_ativa", "whatsapp", "loja_online_mensagem",
                   "loja_online_loja_id", "loja_online_endereco", "loja_online_ativa"):
        op.drop_column("farmacias", coluna)
