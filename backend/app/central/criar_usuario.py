"""Cadastra quem pode entrar na central de licenças.

    python -m app.central.criar_usuario --nome "Amauri" --email amauri@exemplo.com

A senha é pedida no terminal.
"""

import argparse
import getpass

from app.central.db import sessao
from app.central.models import UsuarioCentral
from app.core.security import gerar_hash_senha

if __name__ == "__main__":
    argumentos = argparse.ArgumentParser()
    argumentos.add_argument("--nome", required=True)
    argumentos.add_argument("--email", required=True)
    lidos = argumentos.parse_args()
    senha = getpass.getpass("Senha: ")
    if len(senha) < 8:
        raise SystemExit("Use uma senha com pelo menos 8 letras e números")
    with sessao() as db:
        db.add(UsuarioCentral(nome=lidos.nome, email=lidos.email.strip().lower(), senha_hash=gerar_hash_senha(senha)))
        db.commit()
    print("Pronto.")
