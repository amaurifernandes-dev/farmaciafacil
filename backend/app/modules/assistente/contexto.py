"""O que toda ferramenta do assistente recebe: banco, usuário, PDV e os cartões para a tela."""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.security import TokenDados
from app.modules.lojas.models import Terminal

GERENCIA = ("admin", "gerente")


@dataclass
class Contexto:
    db: Session
    usuario: TokenDados
    terminal: Terminal | None
    cartoes: list[dict] = field(default_factory=list)  # o que a tela mostra junto da resposta

    @property
    def gerente(self) -> bool:
        return self.usuario.papel in GERENCIA


class ErroDaFerramenta(Exception):
    """Volta para o modelo como tool_result com is_error."""
