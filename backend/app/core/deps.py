from collections.abc import Iterator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import TokenDados, ler_token

_bearer = HTTPBearer(auto_error=False)


def get_usuario_atual(
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> TokenDados:
    if credenciais is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Não autenticado")
    try:
        return ler_token(credenciais.credentials)
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido ou expirado")


def get_db(usuario: Annotated[TokenDados, Depends(get_usuario_atual)]) -> Iterator[Session]:
    """Sessão de banco já presa à farmácia do usuário logado."""
    db = SessionLocal(info={"farmacia_id": usuario.farmacia_id})
    try:
        yield db
    finally:
        db.close()


UsuarioAtual = Annotated[TokenDados, Depends(get_usuario_atual)]
DB = Annotated[Session, Depends(get_db)]
