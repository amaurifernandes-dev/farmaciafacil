"""Farmácias, usuários e produtos, com isolamento por farmácia (RLS)

Revision ID: 0001
Revises:
Create Date: 2026-10-29
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.core.config import get_settings
from migrations.helpers import FARMACIA_ATUAL, ativar_rls, conceder_app

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _datas() -> list[sa.Column]:
    return [
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def _tenant() -> list[sa.Column]:
    return [
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "farmacia_id",
            UUID(as_uuid=True),
            sa.ForeignKey("farmacias.id"),
            nullable=False,
            server_default=sa.text(FARMACIA_ATUAL),
        ),
    ]


def upgrade() -> None:
    app_role = get_settings().app_db_role
    op.execute(f"GRANT USAGE ON SCHEMA public TO {app_role}")

    # --- farmacias: o próprio tenant. A política usa a coluna id. ---
    op.create_table(
        "farmacias",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("razao_social", sa.String(200), nullable=False),
        sa.Column("nome_fantasia", sa.String(200), nullable=False),
        sa.Column("cnpj", sa.String(14), nullable=False, unique=True),
        sa.Column("uf", sa.String(2), nullable=False),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        *_datas(),
    )
    ativar_rls("farmacias", coluna="id")
    conceder_app("farmacias", "SELECT, UPDATE")

    # --- usuarios ---
    op.create_table(
        "usuarios",
        *_tenant(),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("senha_hash", sa.String(100), nullable=False),
        sa.Column("papel", sa.String(20), nullable=False),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        *_datas(),
        sa.CheckConstraint("papel IN ('admin', 'gerente', 'caixa')", name="ck_usuarios_papel"),
        sa.CheckConstraint("email = lower(email)", name="ck_usuarios_email_minusculo"),
    )
    ativar_rls("usuarios")
    conceder_app("usuarios")

    # Login: busca o usuário pelo e-mail antes de sabermos a farmácia.
    # SECURITY DEFINER roda como dono da tabela (sem RLS) e devolve só uma linha.
    op.execute(
        """
        CREATE FUNCTION auth_buscar_usuario(p_email text)
        RETURNS TABLE (id uuid, farmacia_id uuid, nome text, senha_hash text, papel text, ativo boolean)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public
        AS $$
            SELECT u.id, u.farmacia_id, u.nome, u.senha_hash, u.papel, u.ativo AND f.ativo
            FROM usuarios u JOIN farmacias f ON f.id = u.farmacia_id
            WHERE u.email = lower(p_email)
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION auth_buscar_usuario(text) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION auth_buscar_usuario(text) TO {app_role}")

    # --- produtos ---
    op.create_table(
        "produtos",
        *_tenant(),
        sa.Column("ean", sa.String(14)),
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("apresentacao", sa.String(200)),
        sa.Column("fabricante", sa.String(120)),
        sa.Column("ncm", sa.String(8)),
        sa.Column("cest", sa.String(7)),
        sa.Column("unidade", sa.String(6), nullable=False, server_default="UN"),
        sa.Column("preco_venda", sa.Numeric(12, 2), nullable=False),
        sa.Column("preco_custo", sa.Numeric(12, 2)),
        sa.Column("estoque_minimo", sa.Numeric(12, 3), nullable=False, server_default="0"),
        sa.Column("controla_lote", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("tipo", sa.String(20), nullable=False, server_default="outros"),
        sa.Column("registro_ms", sa.String(20)),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        *_datas(),
        sa.UniqueConstraint("farmacia_id", "ean"),
        sa.UniqueConstraint("farmacia_id", "id"),
        sa.CheckConstraint("tipo IN ('medicamento', 'perfumaria', 'outros')", name="ck_produtos_tipo"),
        sa.CheckConstraint("preco_venda >= 0", name="ck_produtos_preco_venda"),
    )
    op.execute("CREATE INDEX ix_produtos_nome ON produtos (farmacia_id, lower(nome))")
    ativar_rls("produtos")
    conceder_app("produtos")

    # --- produto_codigos ---
    op.create_table(
        "produto_codigos",
        *_tenant(),
        sa.Column("produto_id", UUID(as_uuid=True), nullable=False),
        sa.Column("ean", sa.String(14), nullable=False),
        *_datas(),
        sa.UniqueConstraint("farmacia_id", "ean"),
        sa.ForeignKeyConstraint(
            ["farmacia_id", "produto_id"],
            ["produtos.farmacia_id", "produtos.id"],
            ondelete="CASCADE",
        ),
    )
    ativar_rls("produto_codigos")
    conceder_app("produto_codigos")


def downgrade() -> None:
    op.drop_table("produto_codigos")
    op.drop_table("produtos")
    op.execute("DROP FUNCTION auth_buscar_usuario(text)")
    op.drop_table("usuarios")
    op.drop_table("farmacias")
