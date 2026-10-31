"""Serviços farmacêuticos: catálogo e atendimentos (pressão, glicemia, injetáveis)

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

from migrations.helpers import FARMACIA_ATUAL, ativar_rls, conceder_app

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

TIPOS = "('pressao', 'glicemia', 'temperatura', 'injetavel', 'outro')"


def _comuns():
    return [
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farmacia_id", UUID(as_uuid=True), sa.ForeignKey("farmacias.id"), nullable=False,
                  server_default=sa.text(FARMACIA_ATUAL)),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    # O CRF de quem é farmacêutico vai na declaração do serviço.
    op.add_column("usuarios", sa.Column("crf", sa.String(20)))

    op.create_table(
        "servicos",
        *_comuns(),
        sa.Column("nome", sa.String(80), nullable=False),
        sa.Column("tipo", sa.String(12), nullable=False),
        sa.Column("preco", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("farmacia_id", "id"),
        sa.UniqueConstraint("farmacia_id", "nome", name="uq_servicos_nome"),
        sa.CheckConstraint(f"tipo IN {TIPOS}", name="ck_servicos_tipo"),
        sa.CheckConstraint("preco >= 0", name="ck_servicos_preco"),
    )
    ativar_rls("servicos")
    conceder_app("servicos", "SELECT, INSERT, UPDATE")

    op.create_table(
        "atendimentos_servico",
        *_comuns(),
        sa.Column("numero", sa.Integer, nullable=False),
        sa.Column("loja_id", UUID(as_uuid=True), nullable=False),
        sa.Column("servico_id", UUID(as_uuid=True), nullable=False),
        sa.Column("servico_nome", sa.String(80), nullable=False),
        sa.Column("tipo", sa.String(12), nullable=False),
        sa.Column("cliente_id", UUID(as_uuid=True)),
        sa.Column("paciente_nome", sa.String(120), nullable=False),
        sa.Column("paciente_cpf", sa.String(11)),
        sa.Column("paciente_nascimento", sa.Date),
        sa.Column("farmaceutico_id", UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("resultados", JSONB, nullable=False, server_default="{}"),
        sa.Column("orientacao", sa.Text),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False, server_default="0"),
        # dinheiro, pix, debito, credito ou cortesia (sem cobrança).
        sa.Column("forma_pagamento", sa.String(10), nullable=False),
        sa.Column("caixa_id", UUID(as_uuid=True)),  # o dinheiro entrou na gaveta deste caixa
        sa.Column("status", sa.String(12), nullable=False, server_default="registrado"),
        sa.Column("motivo_cancelamento", sa.String(200)),
        sa.UniqueConstraint("farmacia_id", "numero", name="uq_atendimentos_servico_numero"),
        sa.ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "servico_id"], ["servicos.farmacia_id", "servicos.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "cliente_id"], ["clientes.farmacia_id", "clientes.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "caixa_id"], ["caixas.farmacia_id", "caixas.id"]),
        sa.CheckConstraint(f"tipo IN {TIPOS}", name="ck_atendimentos_servico_tipo"),
        sa.CheckConstraint("status IN ('registrado', 'cancelado')", name="ck_atendimentos_servico_status"),
        sa.CheckConstraint("forma_pagamento IN ('dinheiro', 'pix', 'debito', 'credito', 'cortesia')",
                           name="ck_atendimentos_servico_forma"),
    )
    op.create_index("ix_atendimentos_servico_cliente", "atendimentos_servico", ["farmacia_id", "cliente_id"])
    op.create_index("ix_atendimentos_servico_caixa", "atendimentos_servico", ["caixa_id"])
    ativar_rls("atendimentos_servico")
    conceder_app("atendimentos_servico", "SELECT, INSERT, UPDATE")


def downgrade() -> None:
    op.drop_table("atendimentos_servico")
    op.drop_table("servicos")
    op.drop_column("usuarios", "crf")
