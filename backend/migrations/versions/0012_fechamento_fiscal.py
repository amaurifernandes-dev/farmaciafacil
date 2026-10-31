"""Fechamento fiscal do mês: regime tributário, contador e código do município para o SPED

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-30
"""
import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lojas", sa.Column("codigo_municipio", sa.String(7)))
    op.add_column("configuracoes_fiscais",
                  sa.Column("regime", sa.String(10), nullable=False, server_default="simples"))
    op.add_column("configuracoes_fiscais", sa.Column("perfil_efd", sa.String(1), nullable=False, server_default="A"))
    op.add_column("configuracoes_fiscais", sa.Column("contador_nome", sa.String(120)))
    op.add_column("configuracoes_fiscais", sa.Column("contador_cpf", sa.String(11)))
    op.add_column("configuracoes_fiscais", sa.Column("contador_crc", sa.String(15)))
    op.add_column("configuracoes_fiscais", sa.Column("contador_email", sa.String(254)))
    op.create_check_constraint("ck_configuracoes_fiscais_regime", "configuracoes_fiscais",
                               "regime IN ('simples', 'presumido', 'real')")
    op.create_check_constraint("ck_configuracoes_fiscais_perfil", "configuracoes_fiscais", "perfil_efd IN ('A', 'B', 'C')")


def downgrade() -> None:
    op.drop_constraint("ck_configuracoes_fiscais_perfil", "configuracoes_fiscais")
    op.drop_constraint("ck_configuracoes_fiscais_regime", "configuracoes_fiscais")
    for coluna in ("contador_email", "contador_crc", "contador_cpf", "contador_nome", "perfil_efd", "regime"):
        op.drop_column("configuracoes_fiscais", coluna)
    op.drop_column("lojas", "codigo_municipio")
