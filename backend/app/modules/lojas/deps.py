from typing import Annotated

from fastapi import Depends, Header

from app.core.deps import DB
from app.modules.lojas.models import Terminal
from app.modules.lojas.service import terminal_pela_chave


def get_terminal(db: DB, x_terminal: Annotated[str | None, Header()] = None) -> Terminal | None:
    """O computador registrado como PDV manda a sua chave no cabeçalho X-Terminal."""
    if not x_terminal:
        return None
    return terminal_pela_chave(db, x_terminal)


TerminalAtual = Annotated[Terminal | None, Depends(get_terminal)]
