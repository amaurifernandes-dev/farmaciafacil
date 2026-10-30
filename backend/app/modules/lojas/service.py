import hashlib
import secrets
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.farmacias.models import Farmacia
from app.modules.lojas.models import Loja, Terminal
from app.modules.lojas.schemas import LojaAtualizar, LojaCriar, TerminalSaida
from app.shared.erros import Conflito, ErroDeNegocio, NaoEncontrado

# A matriz espelha estes campos na tabela farmacias (nome exibido no sistema e no login).
CAMPOS_DA_FARMACIA = ("razao_social", "nome_fantasia", "cnpj", "uf")


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def hash_chave(chave: str) -> str:
    return hashlib.sha256(chave.encode()).hexdigest()


# --- Lojas ---

def listar_lojas(db: Session) -> list[Loja]:
    return db.scalars(select(Loja).order_by(Loja.matriz.desc(), Loja.nome)).all()


def obter_loja(db: Session, loja_id: UUID) -> Loja:
    loja = db.get(Loja, loja_id)
    if loja is None:
        raise NaoEncontrado("Loja não encontrada")
    return loja


def matriz(db: Session) -> Loja:
    return db.scalar(select(Loja).where(Loja.matriz.is_(True)))


def _salvar(db: Session, mensagem_conflito: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflito(mensagem_conflito)


def criar_loja(db: Session, dados: LojaCriar) -> Loja:
    loja = Loja(**dados.model_dump(), matriz=False)
    db.add(loja)
    _salvar(db, "Já existe uma loja com este CNPJ")
    return loja


def atualizar_loja(db: Session, farmacia_id: UUID, loja_id: UUID, dados: LojaAtualizar) -> Loja:
    loja = obter_loja(db, loja_id)
    alteracoes = dados.model_dump(exclude_unset=True)
    for campo in ("nome", "razao_social", "nome_fantasia", "cnpj", "uf", "modo_caixa", "ativo"):
        if campo in alteracoes and alteracoes[campo] is None:
            raise ErroDeNegocio(f"O campo {campo} é obrigatório")

    if alteracoes.get("terminal_central_id") is not None:
        central = obter_terminal(db, alteracoes["terminal_central_id"])
        if central.loja_id != loja.id:
            raise ErroDeNegocio("O PDV central precisa ser desta loja")
    if loja.matriz and alteracoes.get("ativo") is False:
        raise ErroDeNegocio("A matriz não pode ser desativada")

    for campo, valor in alteracoes.items():
        setattr(loja, campo, valor)
    if loja.modo_caixa == "mono" and loja.terminal_central_id is None:
        # Sem central escolhido, o primeiro PDV ativo da loja assume.
        primeiro = db.scalar(
            select(Terminal.id).where(Terminal.loja_id == loja.id, Terminal.ativo.is_(True)).order_by(Terminal.nome)
        )
        loja.terminal_central_id = primeiro

    if loja.matriz:
        farmacia = db.get(Farmacia, farmacia_id)
        for campo in CAMPOS_DA_FARMACIA:
            setattr(farmacia, campo, getattr(loja, campo))
    _salvar(db, "Já existe uma loja com este CNPJ")
    return loja


# --- Terminais ---

def pode_receber(loja: Loja, terminal: Terminal) -> str | None:
    """Devolve None se o terminal pode abrir caixa, ou o motivo de não poder."""
    if not terminal.ativo:
        return f"O {terminal.nome} está desativado."
    if not loja.ativo:
        return f"A loja {loja.nome} está desativada."
    if loja.modo_caixa == "mono" and loja.terminal_central_id != terminal.id:
        return (
            f"A loja {loja.nome} trabalha com monocaixa: só o PDV central recebe pagamentos. "
            "Neste computador, faça uma pré-venda e envie para o caixa."
        )
    return None


def _caixas_abertos(db: Session) -> dict[UUID, UUID]:
    from app.modules.vendas.models import Caixa

    return dict(db.execute(select(Caixa.terminal_id, Caixa.id).where(Caixa.status == "aberto")).all())


def saida_terminal(db: Session, terminal: Terminal, abertos: dict[UUID, UUID] | None = None) -> TerminalSaida:
    loja = db.get(Loja, terminal.loja_id)
    abertos = _caixas_abertos(db) if abertos is None else abertos
    return TerminalSaida(
        id=terminal.id,
        loja_id=terminal.loja_id,
        nome=terminal.nome,
        ativo=terminal.ativo,
        vinculado=terminal.chave_hash is not None,
        vinculado_em=terminal.vinculado_em,
        ultimo_uso_em=terminal.ultimo_uso_em,
        pode_receber=pode_receber(loja, terminal) is None,
        central=loja.terminal_central_id == terminal.id,
        caixa_aberto_id=abertos.get(terminal.id),
    )


def listar_terminais(db: Session) -> list[TerminalSaida]:
    abertos = _caixas_abertos(db)
    terminais = db.scalars(select(Terminal).order_by(Terminal.nome)).all()
    return [saida_terminal(db, t, abertos) for t in terminais]


def obter_terminal(db: Session, terminal_id: UUID) -> Terminal:
    terminal = db.get(Terminal, terminal_id)
    if terminal is None:
        raise NaoEncontrado("PDV não encontrado")
    return terminal


def criar_terminal(db: Session, loja_id: UUID, nome: str) -> Terminal:
    loja = obter_loja(db, loja_id)
    terminal = Terminal(loja_id=loja.id, nome=nome.strip())
    db.add(terminal)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise Conflito("Já existe um PDV com este nome nesta loja")
    if loja.terminal_central_id is None:
        loja.terminal_central_id = terminal.id
    db.commit()
    return terminal


def atualizar_terminal(db: Session, terminal_id: UUID, nome: str | None, ativo: bool | None) -> Terminal:
    terminal = obter_terminal(db, terminal_id)
    if nome is not None:
        terminal.nome = nome.strip()
    if ativo is not None:
        terminal.ativo = ativo
    _salvar(db, "Já existe um PDV com este nome nesta loja")
    return terminal


def vincular(db: Session, terminal_id: UUID) -> tuple[Terminal, str]:
    """Gera uma nova chave para o computador. Um computador vinculado antes perde o acesso."""
    terminal = obter_terminal(db, terminal_id)
    chave = secrets.token_urlsafe(32)
    terminal.chave_hash = hash_chave(chave)
    terminal.vinculado_em = _agora()
    db.commit()
    return terminal, chave


def desvincular(db: Session, terminal_id: UUID) -> Terminal:
    terminal = obter_terminal(db, terminal_id)
    terminal.chave_hash = None
    terminal.vinculado_em = None
    db.commit()
    return terminal


def terminal_pela_chave(db: Session, chave: str) -> Terminal | None:
    # O RLS garante que só acha terminais da farmácia do usuário logado.
    terminal = db.scalar(select(Terminal).where(Terminal.chave_hash == hash_chave(chave)))
    if terminal is not None:
        terminal.ultimo_uso_em = _agora()
    return terminal
