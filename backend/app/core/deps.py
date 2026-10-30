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


def exigir_papel(*papeis: str):
    """Dependência que só deixa passar usuários com um dos papéis informados."""

    def _verificar(usuario: UsuarioAtual) -> TokenDados:
        if usuario.papel not in papeis:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Sem permissão para esta ação")
        return usuario

    return _verificar


Admin = Annotated[TokenDados, Depends(exigir_papel("admin"))]
Gerente = Annotated[TokenDados, Depends(exigir_papel("admin", "gerente"))]
# Cadastra produtos, fornecedores e dá entrada no estoque.
Estoquista = Annotated[TokenDados, Depends(exigir_papel("admin", "gerente", "farmaceutico", "estoque"))]
# Abre caixa e recebe pagamentos.
Operador = Annotated[TokenDados, Depends(exigir_papel("admin", "gerente", "farmaceutico", "caixa"))]
# Monta pré-vendas e atende clientes no balcão.
Atendimento = Annotated[
    TokenDados, Depends(exigir_papel("admin", "gerente", "farmaceutico", "caixa", "atendente"))
]
