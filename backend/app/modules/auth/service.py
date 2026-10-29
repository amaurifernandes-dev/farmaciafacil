from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import TokenDados, criar_token, verificar_senha
from app.modules.auth.schemas import LoginSaida


def autenticar(db: Session, email: str, senha: str) -> LoginSaida | None:
    # Antes do login ainda não sabemos a farmácia, então o RLS esconderia o
    # usuário. A função auth_buscar_usuario (SECURITY DEFINER) faz só essa busca.
    linha = db.execute(
        text("SELECT * FROM auth_buscar_usuario(:email)"), {"email": email.lower()}
    ).mappings().first()

    if linha is None or not linha["ativo"] or not verificar_senha(senha, linha["senha_hash"]):
        return None

    dados = TokenDados(
        usuario_id=linha["id"], farmacia_id=linha["farmacia_id"], papel=linha["papel"]
    )
    return LoginSaida(
        access_token=criar_token(dados),
        usuario_id=linha["id"],
        farmacia_id=linha["farmacia_id"],
        nome=linha["nome"],
        papel=linha["papel"],
    )
