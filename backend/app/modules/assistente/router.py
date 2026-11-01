from typing import Annotated, Any, Literal

import anthropic
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.deps import DB, UsuarioAtual
from app.modules.assistente import service
from app.modules.assistente.ferramentas import Contexto
from app.modules.auth.models import Usuario
from app.modules.lojas.deps import TerminalAtual

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


@router.get("/status")
def status(_: UsuarioAtual) -> dict:
    """A tela pergunta se o assistente está ligado antes de mostrar o botão de falar."""
    return {"ligado": bool(get_settings().anthropic_api_key)}


@router.post("")
def perguntar(db: DB, usuario: UsuarioAtual, terminal: TerminalAtual, cliente: ClienteIA, dados: Pergunta) -> Resposta:
    ctx = Contexto(db=db, usuario=usuario, terminal=terminal)
    eu = db.get(Usuario, usuario.usuario_id)
    historico, resposta = service.conversar(
        cliente, ctx, eu.nome if eu else "", [m.model_dump() for m in dados.historico], dados.mensagem.strip()
    )
    return Resposta(historico=historico, resposta=resposta, cartoes=ctx.cartoes)
