"""Cadastra uma farmácia e o usuário administrador dela.

Uso (dentro de backend/):
    python -m app.scripts.criar_farmacia --cnpj 12345678000190 --razao "Farmácia Exemplo LTDA" \
        --fantasia "Farmácia Exemplo" --uf SP --admin-nome "Maria" --admin-email maria@exemplo.com

A senha é pedida no terminal. Roda com MIGRATION_DATABASE_URL (dono das tabelas),
porque ainda não existe farmácia para o RLS liberar o cadastro.
"""

import argparse
import getpass

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import gerar_hash_senha
from app.modules.auth.models import Usuario
from app.modules import todos_os_modelos  # noqa: F401  (registra as tabelas)
from app.modules.farmacias.models import Farmacia
from app.modules.lojas.models import Loja


def criar_farmacia(
    db: Session,
    *,
    cnpj: str,
    razao_social: str,
    nome_fantasia: str,
    uf: str,
    admin_nome: str,
    admin_email: str,
    admin_senha: str,
) -> tuple[Farmacia, Usuario]:
    if get_settings().instalacao == "farmacia" and db.scalar(select(func.count()).select_from(Farmacia)):
        raise SystemExit("Instalado na farmácia, o sistema guarda uma farmácia só, e ela já foi criada.")
    farmacia = Farmacia(cnpj=cnpj, razao_social=razao_social, nome_fantasia=nome_fantasia, uf=uf.upper())
    db.add(farmacia)
    db.flush()
    db.add(
        Loja(
            farmacia_id=farmacia.id,
            nome="Matriz",
            matriz=True,
            razao_social=razao_social,
            nome_fantasia=nome_fantasia,
            cnpj=cnpj,
            uf=uf.upper(),
        )
    )
    admin = Usuario(
        farmacia_id=farmacia.id,
        nome=admin_nome,
        email=admin_email.lower(),
        senha_hash=gerar_hash_senha(admin_senha),
        papel="admin",
    )
    db.add(admin)
    db.commit()
    return farmacia, admin


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cnpj", required=True)
    parser.add_argument("--razao", required=True)
    parser.add_argument("--fantasia", required=True)
    parser.add_argument("--uf", required=True)
    parser.add_argument("--admin-nome", required=True)
    parser.add_argument("--admin-email", required=True)
    args = parser.parse_args()

    senha = getpass.getpass("Senha do administrador: ")
    engine = create_engine(get_settings().migration_database_url)
    with Session(engine, expire_on_commit=False) as db:
        farmacia, admin = criar_farmacia(
            db,
            cnpj=args.cnpj,
            razao_social=args.razao,
            nome_fantasia=args.fantasia,
            uf=args.uf,
            admin_nome=args.admin_nome,
            admin_email=args.admin_email,
            admin_senha=senha,
        )
    print(f"Farmácia {farmacia.nome_fantasia} criada (id {farmacia.id}). Admin: {admin.email}")


if __name__ == "__main__":
    main()
