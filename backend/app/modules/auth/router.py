from fastapi import APIRouter, HTTPException, status

from app.core.db import SessionLocal
from app.core.deps import UsuarioAtual
from app.core.security import TokenDados
from app.modules.auth import service
from app.modules.auth.schemas import LoginEntrada, LoginSaida

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
