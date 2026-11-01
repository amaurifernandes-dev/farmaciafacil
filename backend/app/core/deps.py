import re
from collections.abc import Iterator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import TokenDados, ler_token

_bearer = HTTPBearer(auto_error=False)

# O acesso offline (login sem internet no PDV) só envia o que foi feito sem internet.
ROTAS_OFFLINE = re.compile(r"^/api/v1/(vendas|pdv/recusas|caixas/abrir|caixas/[0-9a-fA-F-]{36}/fechar)/?$")


def get_usuario_atual(
    request: Request,
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> TokenDados:
    if credenciais is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Não autenticado")
    try:
        usuario = ler_token(credenciais.credentials)
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido ou expirado")
    if usuario.escopo != "completo" and (request.method != "POST" or not ROTAS_OFFLINE.match(request.url.path)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "A internet voltou: entre de novo com a sua senha")
    return usuario


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


def exigir_modulo(modulo: str):
    """Dependência das rotas de uma função que o administrador pode desligar no Gerenciamento de telas."""

    def _verificar(db: DB, usuario: UsuarioAtual) -> None:
        from app.modules.farmacias.models import Farmacia
        from app.shared.modulos import NOMES, desligado

        farmacia = db.get(Farmacia, usuario.farmacia_id)
        if farmacia is not None and desligado(farmacia.modulos_desligados, modulo):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"{NOMES[modulo]} está desligado. O administrador pode ligar em Configurações > Gerenciamento de telas",
            )

    return Depends(_verificar)
