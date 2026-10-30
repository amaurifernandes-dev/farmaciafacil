"""Lista de faltas e encomendas: o que o cliente pediu e não tinha

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-30
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from migrations.helpers import FARMACIA_ATUAL, ativar_rls, conceder_app

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "faltas",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farmacia_id", UUID(as_uuid=True), sa.ForeignKey("farmacias.id"), nullable=False,
                  server_default=sa.text(FARMACIA_ATUAL)),
        sa.Column("loja_id", UUID(as_uuid=True), nullable=False),
        sa.Column("produto_id", UUID(as_uuid=True)),
        sa.Column("descricao", sa.String(200), nullable=False),
        sa.Column("quantidade", sa.Numeric(12, 3), nullable=False, server_default="1"),
        sa.Column("cliente_id", UUID(as_uuid=True)),
        sa.Column("contato_nome", sa.String(120)),
        sa.Column("contato_telefone", sa.String(20)),
        sa.Column("observacao", sa.String(300)),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("origem", sa.String(8), nullable=False, server_default="balcao"),
        sa.Column("avisado_em", sa.DateTime(timezone=True)),
        sa.Column("finalizada_em", sa.DateTime(timezone=True)),
        sa.Column("venda_id", UUID(as_uuid=True)),
        sa.Column("usuario_id", UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("farmacia_id", "id"),
        sa.ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "produto_id"], ["produtos.farmacia_id", "produtos.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "cliente_id"], ["clientes.farmacia_id", "clientes.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "venda_id"], ["vendas.farmacia_id", "vendas.id"]),
        sa.CheckConstraint(
            "status IN ('registrada', 'aberta', 'avisado', 'entregue', 'cancelada')", name="ck_faltas_status"
        ),
        sa.CheckConstraint("origem IN ('balcao', 'pdv')", name="ck_faltas_origem"),
        sa.CheckConstraint("quantidade > 0", name="ck_faltas_quantidade"),
    )
    op.create_index("ix_faltas_status", "faltas", ["farmacia_id", "status", "loja_id"])
    op.create_index("ix_faltas_produto", "faltas", ["farmacia_id", "produto_id", "criado_em"])
    ativar_rls("faltas")
    conceder_app("faltas", "SELECT, INSERT, UPDATE")


def downgrade() -> None:
    op.drop_table("faltas")
