"""NFC-e: configuração fiscal, notas das vendas e tributação dos produtos

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-29
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from migrations.helpers import FARMACIA_ATUAL, ativar_rls, conceder_app

revision = "0005"
down_revision = "0004"
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
    op.add_column("produtos", sa.Column("cfop", sa.String(4)))
    op.add_column("produtos", sa.Column("icms_origem", sa.String(1), nullable=False, server_default="0"))
    op.add_column("produtos", sa.Column("icms_situacao_tributaria", sa.String(3)))
    op.add_column("produtos", sa.Column("pis_cofins_situacao_tributaria", sa.String(2)))

    op.create_table(
        "configuracoes_fiscais",
        *_base(),
        sa.Column("ambiente", sa.String(11), nullable=False, server_default="homologacao"),
        sa.Column("emitir_automaticamente", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("cfop_padrao", sa.String(4), nullable=False, server_default="5102"),
        sa.Column("icms_situacao_tributaria_padrao", sa.String(3), nullable=False, server_default="102"),
        sa.Column("pis_cofins_situacao_tributaria_padrao", sa.String(2), nullable=False, server_default="49"),
        *_datas(),
        sa.UniqueConstraint("farmacia_id"),
        sa.CheckConstraint("ambiente IN ('homologacao', 'producao')", name="ck_config_fiscal_ambiente"),
    )
    ativar_rls("configuracoes_fiscais")
    conceder_app("configuracoes_fiscais", "SELECT, INSERT, UPDATE")

    op.create_table(
        "notas_fiscais",
        *_base(),
        sa.Column("venda_id", UUID(as_uuid=True), nullable=False),
        sa.Column("ambiente", sa.String(11), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("tentativas", sa.Integer, nullable=False, server_default="0"),
        sa.Column("numero", sa.String(9)),
        sa.Column("serie", sa.String(3)),
        sa.Column("chave", sa.String(44)),
        sa.Column("status_sefaz", sa.String(4)),
        sa.Column("mensagem", sa.String(500)),
        sa.Column("url_xml", sa.String(500)),
        sa.Column("url_danfe", sa.String(500)),
        sa.Column("url_qrcode", sa.String(1000)),
        sa.Column("url_consulta", sa.String(500)),
        sa.Column("url_xml_cancelamento", sa.String(500)),
        sa.Column("autorizada_em", sa.DateTime(timezone=True)),
        sa.Column("cancelada_em", sa.DateTime(timezone=True)),
        *_datas(),
        sa.UniqueConstraint("farmacia_id", "venda_id"),
        sa.ForeignKeyConstraint(["farmacia_id", "venda_id"], ["vendas.farmacia_id", "vendas.id"]),
        sa.CheckConstraint(
            "status IN ('processando', 'autorizada', 'rejeitada', 'cancelada', 'erro')", name="ck_notas_status"
        ),
    )
    op.create_index("ix_notas_fiscais_status", "notas_fiscais", ["farmacia_id", "status"])
    ativar_rls("notas_fiscais")
    conceder_app("notas_fiscais", "SELECT, INSERT, UPDATE")


def downgrade() -> None:
    op.drop_table("notas_fiscais")
    op.drop_table("configuracoes_fiscais")
    op.drop_column("produtos", "pis_cofins_situacao_tributaria")
    op.drop_column("produtos", "icms_situacao_tributaria")
    op.drop_column("produtos", "icms_origem")
    op.drop_column("produtos", "cfop")
