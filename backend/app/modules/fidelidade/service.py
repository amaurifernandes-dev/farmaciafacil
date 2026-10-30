"""Fidelidade: o cliente identificado na venda ganha pontos e troca por desconto numa compra seguinte."""

from datetime import date, datetime
from decimal import ROUND_DOWN, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import TokenDados
from app.modules.clientes.models import Cliente
from app.modules.farmacias.models import Farmacia
from app.modules.fidelidade.models import MovimentoPontos
from app.modules.fidelidade.schemas import MovimentoSaida, Pontos
from app.modules.vendas.models import Venda
from app.shared.datas import FUSO, hoje, mais_meses
from app.shared.erros import ErroDeNegocio, NaoEncontrado

CENTAVO = Decimal("0.01")
# Movimentos que contam como "o cliente usou o programa" para a validade.
ATIVIDADE = ("ganho", "resgate")


def saldo(db: Session, cliente_id: UUID) -> int:
    return db.scalar(
        select(func.coalesce(func.sum(MovimentoPontos.pontos), 0)).where(MovimentoPontos.cliente_id == cliente_id)
    )


def _expiram_em(db: Session, farmacia: Farmacia, cliente_id: UUID) -> date | None:
    if farmacia.pontos_validade_meses is None:
        return None
    ultima: datetime | None = db.scalar(
        select(func.max(MovimentoPontos.criado_em)).where(
            MovimentoPontos.cliente_id == cliente_id, MovimentoPontos.tipo.in_(ATIVIDADE)
        )
    )
    if ultima is None:
        return None
    return mais_meses(ultima.astimezone(FUSO).date(), farmacia.pontos_validade_meses)


def _expirar(db: Session, farmacia: Farmacia, cliente_id: UUID) -> int:
    """Zera os pontos de quem passou da validade sem comprar. Devolve o saldo que fica. Não faz commit."""
    atual = saldo(db, cliente_id)
    vence = _expiram_em(db, farmacia, cliente_id)
    if atual > 0 and vence is not None and vence <= hoje():
        db.add(MovimentoPontos(cliente_id=cliente_id, tipo="expirado", pontos=-atual,
                               observacao=f"Venceram em {vence:%d/%m/%Y}, sem compras no período"))
        db.flush()
        return 0
    return atual


def _travar_cliente(db: Session, cliente_id: UUID) -> Cliente:
    cliente = db.scalar(select(Cliente).where(Cliente.id == cliente_id).with_for_update())
    if cliente is None:
        raise NaoEncontrado("Cliente não encontrado")
    return cliente


def valor_dos_pontos(farmacia: Farmacia, pontos: int) -> Decimal:
    return (farmacia.valor_ponto * pontos).quantize(CENTAVO, ROUND_DOWN)


def pontos(db: Session, farmacia: Farmacia, cliente_id: UUID, movimentos: int = 0) -> Pontos:
    if db.get(Cliente, cliente_id) is None:
        raise NaoEncontrado("Cliente não encontrado")
    atual = saldo(db, cliente_id)
    vence = _expiram_em(db, farmacia, cliente_id) if atual > 0 else None
    if vence is not None and vence <= hoje():
        atual, vence = 0, None  # ainda não gravado: o próximo uso registra a expiração
    saida = Pontos(
        ativo=farmacia.fidelidade_ativa,
        saldo=atual,
        valor=valor_dos_pontos(farmacia, max(atual, 0)),
        valor_ponto=farmacia.valor_ponto,
        minimo_resgate=farmacia.pontos_minimo_resgate,
        pode_resgatar=farmacia.fidelidade_ativa and atual >= farmacia.pontos_minimo_resgate,
        expiram_em=vence,
    )
    if movimentos:
        saida.movimentos = extrato(db, cliente_id, movimentos)
    return saida


def extrato(db: Session, cliente_id: UUID, limite: int) -> list[MovimentoSaida]:
    linhas = db.execute(
        select(MovimentoPontos, Venda.numero)
        .outerjoin(Venda, Venda.id == MovimentoPontos.venda_id)
        .where(MovimentoPontos.cliente_id == cliente_id)
        .order_by(MovimentoPontos.criado_em.desc(), MovimentoPontos.id.desc())
        .limit(limite)
    ).all()
    return [
        MovimentoSaida.model_validate({**MovimentoSaida.model_validate(m).model_dump(), "venda_numero": numero})
        for m, numero in linhas
    ]


# --- Na venda (sem commit: fazem parte da transação da venda) ---

def desconto_do_resgate(db: Session, farmacia: Farmacia, cliente_id: UUID | None, quantidade: int) -> Decimal:
    """Confere se o cliente pode trocar esses pontos e devolve o desconto em reais."""
    if not farmacia.fidelidade_ativa:
        raise ErroDeNegocio("O programa de pontos não está ativo. Ligue em Configurações.")
    if cliente_id is None:
        raise ErroDeNegocio("Escolha o cliente para usar os pontos")
    cliente = _travar_cliente(db, cliente_id)
    if quantidade < farmacia.pontos_minimo_resgate:
        raise ErroDeNegocio(f"O mínimo para trocar é {farmacia.pontos_minimo_resgate} pontos")
    disponivel = _expirar(db, farmacia, cliente.id)
    if quantidade > disponivel:
        raise ErroDeNegocio(f"{cliente.nome} tem só {max(disponivel, 0)} pontos")
    return valor_dos_pontos(farmacia, quantidade)


def pontuar_venda(db: Session, farmacia: Farmacia, usuario_id: UUID, venda: Venda) -> None:
    """Grava a troca de pontos da venda (se houve) e os pontos ganhos com ela."""
    if venda.cliente_id is None or not farmacia.fidelidade_ativa:
        return
    _travar_cliente(db, venda.cliente_id)
    _expirar(db, farmacia, venda.cliente_id)
    if venda.pontos_resgatados:
        db.add(MovimentoPontos(cliente_id=venda.cliente_id, tipo="resgate", pontos=-venda.pontos_resgatados,
                               venda_id=venda.id, usuario_id=usuario_id,
                               observacao=f"Desconto de R$ {venda.desconto_pontos:.2f}"))
    # Ganha sobre o que pagou de fato, depois dos descontos.
    ganhos = int((venda.total * farmacia.pontos_por_real).to_integral_value(ROUND_DOWN))
    if ganhos > 0:
        venda.pontos_ganhos = ganhos
        db.add(MovimentoPontos(cliente_id=venda.cliente_id, tipo="ganho", pontos=ganhos,
                               venda_id=venda.id, usuario_id=usuario_id))


def estornar_da_venda(db: Session, usuario_id: UUID, venda: Venda) -> None:
    """Venda cancelada: tira os pontos ganhos e devolve os trocados. O saldo pode ficar negativo."""
    if venda.cliente_id is None or not (venda.pontos_ganhos or venda.pontos_resgatados):
        return
    _travar_cliente(db, venda.cliente_id)
    diferenca = venda.pontos_resgatados - venda.pontos_ganhos
    if diferenca:
        db.add(MovimentoPontos(cliente_id=venda.cliente_id, tipo="estorno", pontos=diferenca, venda_id=venda.id,
                               usuario_id=usuario_id, observacao=f"Cancelamento da venda nº {venda.numero}"))


def ajustar(db: Session, usuario: TokenDados, farmacia: Farmacia, cliente_id: UUID, quantidade: int,
            observacao: str) -> Pontos:
    if quantidade == 0:
        raise ErroDeNegocio("Informe quantos pontos somar ou tirar")
    _travar_cliente(db, cliente_id)
    db.add(MovimentoPontos(cliente_id=cliente_id, tipo="ajuste", pontos=quantidade, usuario_id=usuario.usuario_id,
                           observacao=observacao))
    db.commit()
    return pontos(db, farmacia, cliente_id, movimentos=50)
