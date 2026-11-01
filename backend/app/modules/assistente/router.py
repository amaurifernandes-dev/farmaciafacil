from typing import Annotated, Any, Literal

import anthropic
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.deps import DB, Admin, UsuarioAtual
from app.core.security import TokenDados
from app.modules.assistente import service
from app.modules.assistente.contexto import Contexto
from app.modules.auth.models import Usuario
from app.modules.farmacias.models import Farmacia
from app.modules.lojas.deps import TerminalAtual
from app.shared.erros import SemPermissao

router = APIRouter(prefix="/assistente", tags=["assistente"])



def get_cliente_ia() -> anthropic.Anthropic:
    return service.criar_cliente_ia()


ClienteIA = Annotated[anthropic.Anthropic, Depends(get_cliente_ia)]


class Mensagem(BaseModel):
    role: Literal["user", "assistant"]
    content: list[dict[str, Any]]


class Pergunta(BaseModel):
    historico: list[Mensagem] = []
    mensagem: str = Field(min_length=1, max_length=4000)


class Resposta(BaseModel):
    historico: list[Mensagem]
    resposta: str
    cartoes: list[dict[str, Any]]


class Status(BaseModel):
    ligado: bool = Field(description="O servidor tem a chave da Anthropic")
    permitido: bool = Field(description="O perfil de quem pergunta pode usar o assistente nesta farmácia")
    mensagem: str | None = Field(description="Por que o assistente não aparece, em palavras simples")


class TesteChave(BaseModel):
    ok: bool
    mensagem: str


def _permitido(db: DB, usuario: TokenDados) -> bool:
    farmacia = db.get(Farmacia, usuario.farmacia_id)
    return farmacia is not None and usuario.papel in (farmacia.assistente_perfis or [])


@router.get("/status")
def status(db: DB, usuario: UsuarioAtual) -> Status:
    """A tela pergunta se o assistente está ligado e liberado para o perfil antes de mostrar o botão."""
    ligado = bool(get_settings().anthropic_api_key)
    permitido = _permitido(db, usuario)
    mensagem = None
    if not ligado:
        mensagem = "Falta a chave da Anthropic (ANTHROPIC_API_KEY) no servidor."
    elif not permitido:
        mensagem = "O administrador não liberou o assistente para o seu perfil."
    return Status(ligado=ligado, permitido=permitido, mensagem=mensagem)


@router.post("/testar")
def testar_chave(_: Admin, cliente: ClienteIA) -> TesteChave:
    """Confere com a Anthropic se a chave do servidor funciona e dá acesso ao modelo configurado."""
    return TesteChave(**service.testar_chave(cliente))


@router.post("")
def perguntar(db: DB, usuario: UsuarioAtual, terminal: TerminalAtual, cliente: ClienteIA, dados: Pergunta) -> Resposta:
    if not _permitido(db, usuario):
        raise SemPermissao("O administrador não liberou o assistente para o seu perfil.")
    ctx = Contexto(db=db, usuario=usuario, terminal=terminal)
    eu = db.get(Usuario, usuario.usuario_id)
    historico, resposta = service.conversar(
        cliente, ctx, eu.nome if eu else "", [m.model_dump() for m in dados.historico], dados.mensagem.strip()
    )
    return Resposta(historico=historico, resposta=resposta, cartoes=ctx.cartoes)
