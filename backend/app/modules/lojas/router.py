from uuid import UUID

from fastapi import APIRouter, status

from app.core.deps import DB, Admin, Gerente, UsuarioAtual
from app.modules.licenca.service import conferir_limite
from app.modules.lojas import service
from app.modules.lojas.deps import TerminalAtual
from app.modules.lojas.models import Loja
from app.modules.lojas.schemas import (
    EsteTerminal,
    LojaAtualizar,
    LojaCriar,
    LojaSaida,
    TerminalAtualizar,
    TerminalCriar,
    TerminalSaida,
    TerminalVinculado,
)
from app.shared.erros import NaoEncontrado

lojas = APIRouter(prefix="/lojas", tags=["lojas"])
terminais = APIRouter(prefix="/terminais", tags=["terminais"])


@lojas.get("")
def listar_lojas(db: DB, _: UsuarioAtual) -> list[LojaSaida]:
    return service.listar_lojas(db)


@lojas.post("", status_code=status.HTTP_201_CREATED)
def criar_loja(db: DB, _: Admin, dados: LojaCriar) -> LojaSaida:
    return service.criar_loja(db, dados)


@lojas.patch("/{loja_id}")
def atualizar_loja(db: DB, usuario: Admin, loja_id: UUID, dados: LojaAtualizar) -> LojaSaida:
    return service.atualizar_loja(db, usuario.farmacia_id, loja_id, dados)


@terminais.get("")
def listar_terminais(db: DB, _: Gerente) -> list[TerminalSaida]:
    return service.listar_terminais(db)


@terminais.get("/este")
def este(db: DB, terminal: TerminalAtual) -> EsteTerminal:
    """Diz se este computador é um PDV registrado e se pode abrir caixa."""
    if terminal is None:
        raise NaoEncontrado("Este computador não está registrado como PDV")
    db.commit()  # grava o último uso
    loja = db.get(Loja, terminal.loja_id)
    motivo = service.pode_receber(loja, terminal)
    return EsteTerminal(
        terminal=service.saida_terminal(db, terminal),
        loja=LojaSaida.model_validate(loja),
        pode_receber=motivo is None,
        motivo=motivo,
    )


@terminais.post("", status_code=status.HTTP_201_CREATED)
def criar_terminal(db: DB, eu: Gerente, dados: TerminalCriar) -> TerminalSaida:
    conferir_limite(db, eu.farmacia_id, "caixas")
    return service.saida_terminal(db, service.criar_terminal(db, dados.loja_id, dados.nome))


@terminais.patch("/{terminal_id}")
def atualizar_terminal(db: DB, eu: Gerente, terminal_id: UUID, dados: TerminalAtualizar) -> TerminalSaida:
    if dados.ativo and not service.obter_terminal(db, terminal_id).ativo:
        conferir_limite(db, eu.farmacia_id, "caixas")
    terminal = service.atualizar_terminal(db, terminal_id, dados.nome, dados.ativo)
    return service.saida_terminal(db, terminal)


@terminais.post("/{terminal_id}/vincular")
def vincular(db: DB, _: Gerente, terminal_id: UUID) -> TerminalVinculado:
    """Registra o computador que fez a chamada como este PDV. Guarde a chave no navegador."""
    terminal, chave = service.vincular(db, terminal_id)
    return TerminalVinculado(terminal=service.saida_terminal(db, terminal), chave=chave)


@terminais.post("/{terminal_id}/desvincular")
def desvincular(db: DB, _: Gerente, terminal_id: UUID) -> TerminalSaida:
    return service.saida_terminal(db, service.desvincular(db, terminal_id))
