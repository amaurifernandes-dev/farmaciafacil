from datetime import UTC, datetime, timedelta
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
    # "offline": acesso guardado no PDV para trocar de operador sem internet. Só serve para enviar
    # vendas, aberturas e fechamentos feitos sem internet, e só daquele PDV.
    escopo: str = "completo"
    terminal_id: UUID | None = None
    emitido_em: datetime | None = None


OFFLINE_DIAS = 7


def gerar_hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def verificar_senha(senha: str, senha_hash: str) -> bool:
    return bcrypt.checkpw(senha.encode(), senha_hash.encode())


def criar_token(dados: TokenDados) -> str:
    settings = get_settings()
    expira = datetime.now(UTC) + timedelta(hours=settings.jwt_expira_horas)
    payload = {
        "sub": str(dados.usuario_id),
        "farmacia_id": str(dados.farmacia_id),
        "papel": dados.papel,
        "exp": expira,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITMO)


def criar_token_offline(dados: TokenDados, terminal_id: UUID) -> tuple[str, datetime]:
    agora = datetime.now(UTC)
    expira = agora + timedelta(days=OFFLINE_DIAS)
    payload = {
        "sub": str(dados.usuario_id),
        "farmacia_id": str(dados.farmacia_id),
        "papel": dados.papel,
        "escopo": "offline",
        "terminal_id": str(terminal_id),
        "iat": agora,
        "exp": expira,
    }
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=ALGORITMO), expira


def ler_token(token: str) -> TokenDados:
    """Lança jwt.InvalidTokenError se o token for inválido ou estiver expirado."""
    payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITMO])
    emitido = payload.get("iat")
    return TokenDados(
        usuario_id=payload["sub"],
        farmacia_id=payload["farmacia_id"],
        papel=payload["papel"],
        escopo=payload.get("escopo", "completo"),
        terminal_id=payload.get("terminal_id"),
        emitido_em=datetime.fromtimestamp(emitido, UTC) if emitido else None,
    )
