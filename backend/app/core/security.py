from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
import jwt
from pydantic import BaseModel

from app.core.config import get_settings

ALGORITMO = "HS256"


class TokenDados(BaseModel):
    usuario_id: UUID
    farmacia_id: UUID
    papel: str


def gerar_hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def verificar_senha(senha: str, senha_hash: str) -> bool:
    return bcrypt.checkpw(senha.encode(), senha_hash.encode())


def criar_token(dados: TokenDados) -> str:
    settings = get_settings()
    expira = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expira_horas)
    payload = {
        "sub": str(dados.usuario_id),
        "farmacia_id": str(dados.farmacia_id),
        "papel": dados.papel,
        "exp": expira,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITMO)


def ler_token(token: str) -> TokenDados:
    """Lança jwt.InvalidTokenError se o token for inválido ou estiver expirado."""
    payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITMO])
    return TokenDados(
        usuario_id=payload["sub"],
        farmacia_id=payload["farmacia_id"],
        papel=payload["papel"],
    )
