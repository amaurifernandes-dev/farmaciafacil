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
from app.modules.licenca.service import conferir_limite
from app.shared.erros import Conflito, ErroDeNegocio, NaoEncontrado

Papel = Literal["admin", "gerente", "farmaceutico", "caixa", "atendente", "estoque"]
Senha = Annotated[str, Field(min_length=8, max_length=72)]
Nome = Annotated[str, Field(min_length=1, max_length=120)]
Crf = Annotated[str, Field(max_length=20)] | None  # ex.: "SP 12345"


class UsuarioCriar(BaseModel):
    nome: Nome
    email: EmailStr
    papel: Papel
    senha: Senha
    recebe_comissao: bool = True
    crf: Crf = None


class UsuarioAtualizar(BaseModel):
    nome: Nome | None = None
    email: EmailStr | None = None
    papel: Papel | None = None
    ativo: bool | None = None
    senha: Senha | None = None
    recebe_comissao: bool | None = None
    crf: Crf = None  # texto vazio apaga


class UsuarioSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    email: str
    papel: Papel
    ativo: bool
    recebe_comissao: bool = True
    crf: str | None = None
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
def criar(db: DB, eu: Admin, dados: UsuarioCriar) -> UsuarioSaida:
    conferir_limite(db, eu.farmacia_id, "usuarios")
    usuario = Usuario(
        nome=dados.nome.strip(),
        email=dados.email.lower(),
        papel=dados.papel,
        senha_hash=gerar_hash_senha(dados.senha),
        recebe_comissao=dados.recebe_comissao,
        crf=dados.crf or None,
    )
    db.add(usuario)
    _salvar(db)
    return usuario


@router.patch("/{usuario_id}")
def atualizar(db: DB, eu: Admin, usuario_id: UUID, dados: UsuarioAtualizar) -> UsuarioSaida:
    usuario = _obter(db, usuario_id)
    alteracoes = dados.model_dump(exclude_unset=True, exclude_none=True)
    _proteger_proprio_acesso(usuario, eu, alteracoes)
    if alteracoes.get("ativo") and not usuario.ativo:
        conferir_limite(db, eu.farmacia_id, "usuarios")
    if "senha" in alteracoes:
        usuario.senha_hash = gerar_hash_senha(alteracoes.pop("senha"))
    if "email" in alteracoes:
        alteracoes["email"] = alteracoes["email"].lower()
    if "crf" in alteracoes:
        alteracoes["crf"] = alteracoes["crf"] or None
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
