from fastapi import APIRouter, HTTPException, status

from app.core.db import SessionLocal
from app.core.deps import UsuarioAtual
from app.core.security import TokenDados, criar_token_offline
from app.modules.auth import service
from app.modules.auth.schemas import LoginEntrada, LoginSaida, TokenOffline
from app.modules.lojas.deps import TerminalAtual
from app.shared.erros import ErroDeNegocio, SemPermissao

OPERADORES = ("admin", "gerente", "farmaceutico", "caixa")

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(entrada: LoginEntrada) -> LoginSaida:
    with SessionLocal() as db:
        resultado = service.autenticar(db, entrada.email, entrada.senha)
    if resultado is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha inválidos")
    return resultado


@router.get("/eu")
def eu(usuario: UsuarioAtual) -> TokenDados:
    return usuario


@router.post("/token-offline")
def token_offline(usuario: UsuarioAtual, terminal: TerminalAtual) -> TokenOffline:
    """Acesso guardado (cifrado com a senha) no PDV para entrar sem internet nos próximos 7 dias."""
    if terminal is None:
        raise ErroDeNegocio("Só um computador registrado como PDV guarda o acesso sem internet")
    if usuario.papel not in OPERADORES:
        raise SemPermissao("Seu perfil não trabalha no caixa")
    token, expira = criar_token_offline(usuario, terminal.id)
    return TokenOffline(token_offline=token, expira_em=expira)
