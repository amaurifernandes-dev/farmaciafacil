"""Remédios controlados: lista da Portaria 344 no produto, receita na venda e motivo de perda do SNGPC

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from migrations.helpers import FARMACIA_ATUAL, ativar_rls, conceder_app

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

LISTAS = "('A1', 'A2', 'A3', 'B1', 'B2', 'C1', 'C2', 'C3', 'C4', 'C5', 'ATB')"


def upgrade() -> None:
    op.add_column("produtos", sa.Column("controle", sa.String(3)))
    op.add_column("produtos", sa.Column("embalagem_sngpc", sa.String(6), nullable=False, server_default="caixa"))
    op.create_check_constraint("ck_produtos_controle", "produtos", f"controle IS NULL OR controle IN {LISTAS}")
    op.create_check_constraint("ck_produtos_embalagem_sngpc", "produtos", "embalagem_sngpc IN ('caixa', 'frasco')")

    op.add_column("lojas", sa.Column("responsavel_cpf", sa.String(11)))
    op.add_column("movimentos_estoque", sa.Column("motivo_sngpc", sa.SmallInteger))

    op.create_table(
        "receitas",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farmacia_id", UUID(as_uuid=True), sa.ForeignKey("farmacias.id"), nullable=False,
                  server_default=sa.text(FARMACIA_ATUAL)),
        sa.Column("venda_id", UUID(as_uuid=True), nullable=False),
        sa.Column("tipo_receituario", sa.SmallInteger, nullable=False),
        sa.Column("numero_notificacao", sa.String(20)),
        sa.Column("data_prescricao", sa.Date, nullable=False),
        sa.Column("prescritor_nome", sa.String(120), nullable=False),
        sa.Column("prescritor_conselho", sa.String(4), nullable=False),
        sa.Column("prescritor_numero", sa.String(20), nullable=False),
        sa.Column("prescritor_uf", sa.String(2), nullable=False),
        sa.Column("uso", sa.SmallInteger, nullable=False, server_default="1"),
        sa.Column("uso_prolongado", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("comprador_nome", sa.String(120)),
        sa.Column("comprador_tipo_documento", sa.SmallInteger),
        sa.Column("comprador_documento", sa.String(30)),
        sa.Column("comprador_orgao", sa.String(10)),
        sa.Column("comprador_uf", sa.String(2)),
        sa.Column("paciente_nome", sa.String(120)),
        sa.Column("paciente_idade", sa.SmallInteger),
        sa.Column("paciente_unidade_idade", sa.SmallInteger),
        sa.Column("paciente_sexo", sa.SmallInteger),
        sa.Column("cid", sa.String(8)),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("farmacia_id", "id"),
        sa.UniqueConstraint("farmacia_id", "venda_id", name="uq_receitas_venda"),
        sa.ForeignKeyConstraint(["farmacia_id", "venda_id"], ["vendas.farmacia_id", "vendas.id"]),
        sa.CheckConstraint("tipo_receituario BETWEEN 1 AND 5", name="ck_receitas_tipo"),
        sa.CheckConstraint("prescritor_conselho IN ('CRM', 'CRMV', 'CRO', 'CRF', 'RMS')", name="ck_receitas_conselho"),
        sa.CheckConstraint("uso IN (1, 2)", name="ck_receitas_uso"),
    )
    ativar_rls("receitas")
    conceder_app("receitas", "SELECT, INSERT")


def downgrade() -> None:
    op.drop_table("receitas")
    op.drop_column("movimentos_estoque", "motivo_sngpc")
    op.drop_column("lojas", "responsavel_cpf")
    op.drop_constraint("ck_produtos_embalagem_sngpc", "produtos")
    op.drop_constraint("ck_produtos_controle", "produtos")
    op.drop_column("produtos", "embalagem_sngpc")
    op.drop_column("produtos", "controle")
