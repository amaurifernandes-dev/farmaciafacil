"""Cadastros e configurações: lojas, terminais (PDVs), clientes, fornecedores, pré-vendas

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-30
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

from migrations.helpers import FARMACIA_ATUAL, ativar_rls, conceder_app

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

PAPEIS_ANTIGOS = "'admin', 'gerente', 'caixa'"
PAPEIS = "'admin', 'gerente', 'farmaceutico', 'caixa', 'atendente', 'estoque'"


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


def _endereco() -> list[sa.Column]:
    return [
        sa.Column("telefone", sa.String(20)),
        sa.Column("email", sa.String(254)),
        sa.Column("cep", sa.String(8)),
        sa.Column("endereco", sa.String(200)),
        sa.Column("bairro", sa.String(100)),
        sa.Column("cidade", sa.String(100)),
    ]


def upgrade() -> None:
    # --- Configurações gerais da farmácia ---
    op.add_column("farmacias", sa.Column("desconto_maximo_caixa", sa.Numeric(5, 2), nullable=False, server_default="10"))
    op.add_column("farmacias", sa.Column("dias_alerta_vencimento", sa.Integer, nullable=False, server_default="30"))
    op.create_check_constraint(
        "ck_farmacias_desconto_maximo", "farmacias", "desconto_maximo_caixa BETWEEN 0 AND 100"
    )

    # --- Novos perfis de usuário ---
    op.drop_constraint("ck_usuarios_papel", "usuarios")
    op.create_check_constraint("ck_usuarios_papel", "usuarios", f"papel IN ({PAPEIS})")

    # --- Lojas: a matriz e as filiais da farmácia ---
    op.create_table(
        "lojas",
        *_base(),
        sa.Column("nome", sa.String(60), nullable=False),
        sa.Column("matriz", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("razao_social", sa.String(200), nullable=False),
        sa.Column("nome_fantasia", sa.String(200), nullable=False),
        sa.Column("cnpj", sa.String(14), nullable=False),
        sa.Column("inscricao_estadual", sa.String(20)),
        *_endereco(),
        sa.Column("uf", sa.String(2), nullable=False),
        sa.Column("responsavel_tecnico", sa.String(120)),
        sa.Column("crf", sa.String(20)),
        sa.Column("modo_caixa", sa.String(10), nullable=False, server_default="mono"),
        sa.Column("terminal_central_id", UUID(as_uuid=True)),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        *_datas(),
        sa.UniqueConstraint("farmacia_id", "id"),
        sa.UniqueConstraint("farmacia_id", "cnpj"),
        sa.CheckConstraint("modo_caixa IN ('mono', 'multi')", name="ck_lojas_modo_caixa"),
    )
    op.create_index(
        "ux_lojas_uma_matriz", "lojas", ["farmacia_id"], unique=True, postgresql_where=sa.text("matriz")
    )
    ativar_rls("lojas")
    conceder_app("lojas", "SELECT, INSERT, UPDATE")

    # Cada farmácia que já existe ganha a sua matriz com os dados atuais.
    op.execute(
        """
        INSERT INTO lojas (id, farmacia_id, nome, matriz, razao_social, nome_fantasia, cnpj, uf)
        SELECT gen_random_uuid(), id, 'Matriz', true, razao_social, nome_fantasia, cnpj, uf FROM farmacias
        """
    )

    # --- Terminais: computadores registrados como PDV ---
    op.create_table(
        "terminais",
        *_base(),
        sa.Column("loja_id", UUID(as_uuid=True), nullable=False),
        sa.Column("nome", sa.String(40), nullable=False),
        # Hash da chave guardada no navegador do computador. Nulo = nenhum computador vinculado.
        sa.Column("chave_hash", sa.String(64), unique=True),
        sa.Column("vinculado_em", sa.DateTime(timezone=True)),
        sa.Column("ultimo_uso_em", sa.DateTime(timezone=True)),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        *_datas(),
        sa.UniqueConstraint("farmacia_id", "id"),
        sa.UniqueConstraint("farmacia_id", "loja_id", "nome"),
        sa.ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
    )
    ativar_rls("terminais")
    conceder_app("terminais", "SELECT, INSERT, UPDATE")
    op.create_foreign_key(
        "fk_lojas_terminal_central", "lojas", "terminais",
        ["farmacia_id", "terminal_central_id"], ["farmacia_id", "id"],
    )

    # --- Caixa passa a pertencer a um terminal e a uma loja ---
    op.add_column("caixas", sa.Column("terminal_id", UUID(as_uuid=True)))
    op.add_column("caixas", sa.Column("loja_id", UUID(as_uuid=True)))
    op.create_foreign_key(
        "fk_caixas_terminal", "caixas", "terminais", ["farmacia_id", "terminal_id"], ["farmacia_id", "id"]
    )
    op.create_foreign_key("fk_caixas_loja", "caixas", "lojas", ["farmacia_id", "loja_id"], ["farmacia_id", "id"])
    op.execute(
        "UPDATE caixas c SET loja_id = l.id FROM lojas l WHERE l.farmacia_id = c.farmacia_id AND l.matriz"
    )
    # Um terminal só pode ter um caixa aberto por vez.
    op.create_index(
        "ux_caixas_um_aberto_por_terminal", "caixas", ["terminal_id"],
        unique=True, postgresql_where=sa.text("status = 'aberto'"),
    )

    # --- Clientes (cadastro opcional; ofertas só com consentimento) ---
    op.create_table(
        "clientes",
        *_base(),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("cpf", sa.String(11)),
        sa.Column("data_nascimento", sa.Date),
        *_endereco(),
        sa.Column("uf", sa.String(2)),
        sa.Column("aceita_ofertas", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("consentimento_em", sa.DateTime(timezone=True)),
        sa.Column("observacoes", sa.String(500)),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        *_datas(),
        sa.UniqueConstraint("farmacia_id", "cpf"),
    )
    op.execute("CREATE INDEX ix_clientes_nome ON clientes (farmacia_id, lower(nome))")
    ativar_rls("clientes")
    conceder_app("clientes", "SELECT, INSERT, UPDATE")

    # --- Fornecedores ---
    op.create_table(
        "fornecedores",
        *_base(),
        sa.Column("razao_social", sa.String(200), nullable=False),
        sa.Column("nome_fantasia", sa.String(200)),
        sa.Column("cnpj", sa.String(14)),
        sa.Column("inscricao_estadual", sa.String(20)),
        sa.Column("contato", sa.String(120)),
        *_endereco(),
        sa.Column("uf", sa.String(2)),
        sa.Column("observacoes", sa.String(500)),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        *_datas(),
        sa.UniqueConstraint("farmacia_id", "cnpj"),
    )
    op.execute("CREATE INDEX ix_fornecedores_nome ON fornecedores (farmacia_id, lower(razao_social))")
    ativar_rls("fornecedores")
    conceder_app("fornecedores", "SELECT, INSERT, UPDATE")

    # --- Pré-vendas: o balconista monta, o caixa recebe ---
    op.create_table(
        "pre_vendas",
        *_base(),
        sa.Column("loja_id", UUID(as_uuid=True), nullable=False),
        sa.Column("numero", sa.Integer, nullable=False),
        sa.Column("usuario_id", UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="aberta"),
        sa.Column("itens", JSONB, nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("cliente_cpf", sa.String(11)),
        sa.Column("venda_id", UUID(as_uuid=True)),
        sa.Column("finalizada_em", sa.DateTime(timezone=True)),
        *_datas(),
        sa.UniqueConstraint("farmacia_id", "numero"),
        sa.ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
        sa.ForeignKeyConstraint(["farmacia_id", "venda_id"], ["vendas.farmacia_id", "vendas.id"]),
        sa.CheckConstraint("status IN ('aberta', 'recebida', 'cancelada')", name="ck_pre_vendas_status"),
    )
    op.create_index("ix_pre_vendas_abertas", "pre_vendas", ["farmacia_id", "loja_id"],
                    postgresql_where=sa.text("status = 'aberta'"))
    ativar_rls("pre_vendas")
    conceder_app("pre_vendas", "SELECT, INSERT, UPDATE")


def downgrade() -> None:
    op.drop_table("pre_vendas")
    op.drop_table("fornecedores")
    op.drop_table("clientes")
    op.drop_index("ux_caixas_um_aberto_por_terminal", "caixas")
    op.drop_constraint("fk_caixas_loja", "caixas")
    op.drop_constraint("fk_caixas_terminal", "caixas")
    op.drop_column("caixas", "loja_id")
    op.drop_column("caixas", "terminal_id")
    op.drop_constraint("fk_lojas_terminal_central", "lojas")
    op.drop_table("terminais")
    op.drop_table("lojas")
    op.execute(f"UPDATE usuarios SET papel = 'caixa' WHERE papel NOT IN ({PAPEIS_ANTIGOS})")
    op.drop_constraint("ck_usuarios_papel", "usuarios")
    op.create_check_constraint("ck_usuarios_papel", "usuarios", f"papel IN ({PAPEIS_ANTIGOS})")
    op.drop_constraint("ck_farmacias_desconto_maximo", "farmacias")
    op.drop_column("farmacias", "dias_alerta_vencimento")
    op.drop_column("farmacias", "desconto_maximo_caixa")
