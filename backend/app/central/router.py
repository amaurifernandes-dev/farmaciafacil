from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.central import service
from app.central.config import get_config
from app.central.db import get_db
from app.central.models import LicencaCentral, UsuarioCentral
from app.central.schemas import (
    Ativar,
    CodigoSaida,
    Entrar,
    Evento,
    LicencaAtualizar,
    LicencaCriar,
    LicencaSaida,
    PedirCodigo,
    Token,
)
from app.core.security import verificar_senha
from app.shared.modulos import MODULOS, NOMES

DB = Annotated[Session, Depends(get_db)]
_bearer = HTTPBearer(auto_error=False)
PAGINA = Path(__file__).with_name("pagina.html")

router = APIRouter()


def usuario_central(
    db: DB, credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
) -> UsuarioCentral:
    if credenciais is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Entre com o seu e-mail e senha")
    try:
        dados = jwt.decode(credenciais.credentials, get_config().jwt_secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Entre de novo")
    usuario = db.get(UsuarioCentral, int(dados["sub"]))
    if usuario is None or not usuario.ativo or dados.get("escopo") != "central":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Entre de novo")
    return usuario


Dono = Annotated[UsuarioCentral, Depends(usuario_central)]


def _saida(lic: LicencaCentral) -> LicencaSaida:
    return LicencaSaida.model_validate(
        {**{c: getattr(lic, c) for c in LicencaSaida.model_fields if c != "situacao"},
         "situacao": service.situacao_na_central(lic)}
    )


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def pagina() -> str:
    return PAGINA.read_text(encoding="utf-8")


@router.post("/api/entrar")
def entrar(db: DB, dados: Entrar) -> Token:
    usuario = db.scalar(select(UsuarioCentral).where(UsuarioCentral.email == dados.email.strip().lower()))
    if usuario is None or not usuario.ativo or not verificar_senha(dados.senha, usuario.senha_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha inválidos")
    config = get_config()
    token = jwt.encode(
        {"sub": str(usuario.id), "escopo": "central",
         "exp": datetime.now(UTC) + timedelta(hours=config.jwt_expira_horas)},
        config.jwt_secret,
        algorithm="HS256",
    )
    return Token(access_token=token, nome=usuario.nome)


@router.get("/api/modulos")
def modulos(_: Dono) -> list[dict]:
    return [{"id": m, "nome": NOMES[m]} for m in MODULOS]


@router.get("/api/licencas")
def listar(db: DB, _: Dono, busca: str | None = None) -> list[LicencaSaida]:
    return [_saida(lic) for lic in service.listar(db, busca)]


@router.post("/api/licencas", status_code=status.HTTP_201_CREATED)
def criar(db: DB, eu: Dono, dados: LicencaCriar) -> LicencaSaida:
    return _saida(service.criar(db, dados, eu.nome))


@router.patch("/api/licencas/{licenca_id}")
def atualizar(db: DB, eu: Dono, licenca_id: int, dados: LicencaAtualizar) -> LicencaSaida:
    return _saida(service.atualizar(db, licenca_id, dados, eu.nome))


@router.post("/api/licencas/{licenca_id}/renovar")
def renovar(db: DB, eu: Dono, licenca_id: int) -> LicencaSaida:
    return _saida(service.renovar(db, licenca_id, eu.nome))


@router.post("/api/licencas/{licenca_id}/liberar-troca")
def liberar_troca(db: DB, eu: Dono, licenca_id: int) -> LicencaSaida:
    return _saida(service.liberar_troca(db, licenca_id, eu.nome))


@router.post("/api/licencas/{licenca_id}/suspender")
def suspender(db: DB, eu: Dono, licenca_id: int) -> LicencaSaida:
    return _saida(service.suspender(db, licenca_id, True, eu.nome))


@router.post("/api/licencas/{licenca_id}/reativar")
def reativar(db: DB, eu: Dono, licenca_id: int) -> LicencaSaida:
    return _saida(service.suspender(db, licenca_id, False, eu.nome))


@router.post("/api/licencas/{licenca_id}/codigo")
def codigo(db: DB, eu: Dono, licenca_id: int, dados: PedirCodigo) -> CodigoSaida:
    """Código para colar no servidor que não tem internet."""
    lic, texto = service.gerar_codigo(db, licenca_id, dados.maquina, eu.nome)
    return CodigoSaida(codigo=texto, vence=lic.vence)


@router.get("/api/licencas/{licenca_id}/historico")
def historico(db: DB, _: Dono, licenca_id: int) -> list[Evento]:
    return service.historico(db, licenca_id)


@router.post("/api/ativar")
def ativar(db: DB, dados: Ativar) -> CodigoSaida:
    """Pública: o servidor da farmácia ativa e renova a licença sozinho com a chave de ativação."""
    lic, texto = service.ativar(db, dados.chave_ativacao, dados.maquina)
    return CodigoSaida(codigo=texto, vence=lic.vence)
