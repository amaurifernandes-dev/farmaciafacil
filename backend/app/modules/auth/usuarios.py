"""Cadastro de usuários da farmácia. Só o administrador gerencia."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import DB, Admin
from app.core.security import TokenDados, gerar_hash_senha
from app.modules.auth.models import Usuario
from app.shared.erros import Conflito, ErroDeNegocio, NaoEncontrado

Papel = Literal["admin", "gerente", "farmaceutico", "caixa", "atendente", "estoque"]
Senha = Annotated[str, Field(min_length=8, max_length=72)]
Nome = Annotated[str, Field(min_length=1, max_length=120)]


class UsuarioCriar(BaseModel):
    nome: Nome
    email: EmailStr
    papel: Papel
    senha: Senha
    recebe_comissao: bool = True


class UsuarioAtualizar(BaseModel):
    nome: Nome | None = None
    email: EmailStr | None = None
    papel: Papel | None = None
    ativo: bool | None = None
    senha: Senha | None = None
    recebe_comissao: bool | None = None


class UsuarioSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    email: str
    papel: Papel
    ativo: bool
    recebe_comissao: bool = True
    criado_em: datetime


def _salvar(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # O e-mail é único no sistema todo, porque é o login.
        raise Conflito("Este e-mail já está em uso")


def _obter(db: Session, usuario_id: UUID) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise NaoEncontrado("Usuário não encontrado")
    return usuario


router = APIRouter(prefix="/usuarios", tags=["usuários"])


@router.get("")
def listar(db: DB, _: Admin) -> list[UsuarioSaida]:
    return db.scalars(select(Usuario).order_by(Usuario.ativo.desc(), Usuario.nome)).all()


@router.post("", status_code=status.HTTP_201_CREATED)
def criar(db: DB, _: Admin, dados: UsuarioCriar) -> UsuarioSaida:
    usuario = Usuario(
        nome=dados.nome.strip(),
        email=dados.email.lower(),
        papel=dados.papel,
        senha_hash=gerar_hash_senha(dados.senha),
        recebe_comissao=dados.recebe_comissao,
    )
    db.add(usuario)
    _salvar(db)
    return usuario


@router.patch("/{usuario_id}")
def atualizar(db: DB, eu: Admin, usuario_id: UUID, dados: UsuarioAtualizar) -> UsuarioSaida:
    usuario = _obter(db, usuario_id)
    alteracoes = dados.model_dump(exclude_unset=True, exclude_none=True)
    _proteger_proprio_acesso(usuario, eu, alteracoes)
    if "senha" in alteracoes:
        usuario.senha_hash = gerar_hash_senha(alteracoes.pop("senha"))
    if "email" in alteracoes:
        alteracoes["email"] = alteracoes["email"].lower()
    for campo, valor in alteracoes.items():
        setattr(usuario, campo, valor)
    _salvar(db)
    return usuario


def _proteger_proprio_acesso(usuario: Usuario, eu: TokenDados, alteracoes: dict) -> None:
    """O administrador não pode se trancar para fora do sistema."""
    if usuario.id != eu.usuario_id:
        return
    if alteracoes.get("ativo") is False:
        raise ErroDeNegocio("Você não pode desativar o seu próprio usuário")
    if alteracoes.get("papel", "admin") != "admin":
        raise ErroDeNegocio("Você não pode tirar o seu próprio perfil de administrador")
