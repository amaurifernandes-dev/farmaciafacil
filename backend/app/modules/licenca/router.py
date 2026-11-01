"""Tela da licença. Instalado na farmácia, abre sem login: é por ela que se ativa um servidor novo ou vencido."""

from datetime import date
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.security import ler_token
from app.licenca.situacao import Situacao
from app.modules.farmacias.models import Farmacia
from app.modules.licenca import service
from app.shared.erros import ErroDeNegocio, NaoEncontrado
from app.shared.modulos import NOMES

router = APIRouter(prefix="/licenca", tags=["licença"])
_bearer = HTTPBearer(auto_error=False)


class Resumo(BaseModel):
    numero: str
    nome: str
    plano: str
    tipo: str
    inicio: date
    vence: date | None
    tolerancia_dias: int
    max_usuarios: int | None
    max_caixas: int | None
    modulos: list[str] | None = Field(description="Nomes dos módulos incluídos. Vazio: todos")


class EstadoLicenca(BaseModel):
    exigida: bool
    situacao: Situacao | None
    licenca: Resumo | None
    codigo_servidor: str | None = Field(description="Instalado na farmácia: o código deste servidor")
    renova_sozinha: bool = Field(description="Tem chave de ativação e endereço da central")
    ultimo_erro: str | None


class Instalar(BaseModel):
    codigo: str | None = Field(None, description="Código da licença (servidor sem internet)")
    chave_ativacao: str | None = Field(None, description="Chave de ativação (servidor com internet)")


def _cnpj(
    request: Request, credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
) -> tuple[Session, str]:
    """Na farmácia: o CNPJ da única farmácia, sem login. Na nuvem: o da farmácia do administrador logado."""
    if get_settings().instalacao == "farmacia":
        db = SessionLocal()
        cnpj = service.cnpj_da_instalacao(db)
        if cnpj is None:
            db.close()
            raise NaoEncontrado("A farmácia ainda não foi cadastrada neste servidor")
        return db, cnpj
    if credenciais is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Não autenticado")
    try:
        usuario = ler_token(credenciais.credentials)
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido ou expirado")
    if request.method != "GET" and usuario.papel != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só o administrador troca a licença")
    db = SessionLocal(info={"farmacia_id": usuario.farmacia_id})
    return db, db.get(Farmacia, usuario.farmacia_id).cnpj


def _sessao(dados: Annotated[tuple[Session, str], Depends(_cnpj)]):
    db, cnpj = dados
    try:
        yield db, cnpj
    finally:
        db.close()


Contexto = Annotated[tuple[Session, str], Depends(_sessao)]


def _estado(db: Session, cnpj: str) -> EstadoLicenca:
    if not service.exigida():
        return EstadoLicenca(
            exigida=False, situacao=None, licenca=None, codigo_servidor=None, renova_sozinha=False, ultimo_erro=None
        )
    service.esquecer_cache()
    sit, licenca = service.avaliar(db, cnpj)
    linha, _ = service.instalada(db, cnpj)
    resumo = None
    if licenca is not None:
        resumo = Resumo(
            numero=licenca.id,
            nome=licenca.nome,
            plano=licenca.plano,
            tipo=licenca.tipo,
            inicio=licenca.inicio,
            vence=licenca.vence,
            tolerancia_dias=licenca.tolerancia_dias,
            max_usuarios=licenca.max_usuarios,
            max_caixas=licenca.max_caixas,
            modulos=None if licenca.modulos is None else [NOMES[m] for m in licenca.modulos if m in NOMES],
        )
    return EstadoLicenca(
        exigida=True,
        situacao=sit,
        licenca=resumo,
        codigo_servidor=service.maquina(db) if get_settings().instalacao == "farmacia" else None,
        renova_sozinha=bool(linha and linha.chave_ativacao and get_settings().licencas_url),
        ultimo_erro=linha.ultimo_erro if linha else None,
    )


@router.get("")
def estado(contexto: Contexto) -> EstadoLicenca:
    return _estado(*contexto)


@router.post("")
def instalar(contexto: Contexto, dados: Instalar) -> EstadoLicenca:
    db, cnpj = contexto
    if not service.exigida():
        raise ErroDeNegocio("Este sistema não confere licença")
    if dados.codigo:
        service.instalar(db, cnpj, dados.codigo)
    elif dados.chave_ativacao:
        service.buscar_na_central(db, cnpj, dados.chave_ativacao.strip().upper())
    else:
        raise ErroDeNegocio("Cole o código da licença ou digite a chave de ativação")
    return _estado(db, cnpj)


@router.post("/renovar")
def renovar(contexto: Contexto) -> EstadoLicenca:
    db, cnpj = contexto
    linha, _ = service.instalada(db, cnpj)
    if linha is None or not linha.chave_ativacao:
        raise ErroDeNegocio("Este servidor não tem chave de ativação. Cole um código novo da licença")
    service.buscar_na_central(db, cnpj, linha.chave_ativacao)
    return _estado(db, cnpj)
