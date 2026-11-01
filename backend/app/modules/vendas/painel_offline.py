"""Painel do gerente para o que foi feito no caixa sem internet.

O PDV avisa aqui quando um envio é recusado (POST /pdv/recusas); o gerente vê as vendas que
entraram depois, as recusadas e o que foi vendido sem saldo no sistema.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert

from app.core.deps import DB, Gerente, Operador
from app.modules.auth.models import Usuario
from app.modules.lojas.deps import TerminalAtual
from app.modules.lojas.models import Terminal
from app.modules.produtos.models import Produto
from app.modules.vendas.models import Caixa, EnvioRecusado, Venda, VendaItem
from app.modules.vendas.service import _agora, _exigir_terminal, conferir_acesso_offline
from app.shared.datas import FUSO, hoje
from app.shared.erros import NaoEncontrado

LIMITE = 200


class RecusaCriar(BaseModel):
    chave: str = Field(min_length=1, max_length=80)
    tipo: Literal["venda", "abrir", "fechar"]
    offline_em: datetime
    total: Decimal = Decimal(0)
    motivo: str = Field(min_length=1, max_length=2000)
    corpo: dict


class VendaOffline(BaseModel):
    id: UUID
    numero: int
    feita_em: datetime
    chegou_em: datetime
    operador: str
    terminal: str | None
    total: Decimal
    status: str


class ItemSemEstoque(BaseModel):
    venda_id: UUID
    numero: int
    feita_em: datetime
    produto: str
    quantidade: Decimal


class Recusa(BaseModel):
    id: UUID
    tipo: str
    feito_em: datetime
    avisado_em: datetime
    operador: str
    terminal: str | None
    total: Decimal
    motivo: str
    resolvido_em: datetime | None
    resolucao: str | None


class ResumoOffline(BaseModel):
    vendas: int
    total: Decimal
    caixas: int  # abertos ou fechados sem internet
    itens_sem_estoque: int
    recusas_pendentes: int


class PainelOffline(BaseModel):
    de: date
    ate: date
    resumo: ResumoOffline
    vendas: list[VendaOffline]
    sem_estoque: list[ItemSemEstoque]
    recusas: list[Recusa]


pdv = APIRouter(prefix="/pdv", tags=["caixa"])
painel = APIRouter(prefix="/vendas-offline", tags=["caixa"])


@pdv.post("/recusas", status_code=204, summary="O PDV avisa que um envio feito sem internet foi recusado")
def avisar_recusa(db: DB, usuario: Operador, terminal: TerminalAtual, dados: RecusaCriar) -> None:
    terminal = _exigir_terminal(terminal)
    conferir_acesso_offline(db, usuario, terminal.id, dados.offline_em)
    valores = {
        "terminal_id": terminal.id,
        "usuario_id": usuario.usuario_id,
        "chave": dados.chave,
        "tipo": dados.tipo,
        "feito_em": dados.offline_em,
        "total": dados.total,
        "motivo": dados.motivo,
        "corpo": dados.corpo,
    }
    # Avisado de novo (tentou outra vez e foi recusado de novo): atualiza o motivo e reabre.
    db.execute(
        insert(EnvioRecusado)
        .values(**valores)
        .on_conflict_do_update(
            constraint="uq_envios_recusados_chave",
            set_={"motivo": dados.motivo, "resolvido_em": None, "resolucao": None, "resolvido_por": None,
                  "atualizado_em": func.now()},
        )
    )
    db.commit()


def _periodo(de: date | None, ate: date | None) -> tuple[date, date, datetime, datetime]:
    ate = ate or hoje()
    de = de or ate - timedelta(days=30)
    inicio = datetime.combine(de, time.min, tzinfo=FUSO)
    fim = datetime.combine(ate + timedelta(days=1), time.min, tzinfo=FUSO)
    return de, ate, inicio, fim


@painel.get("", summary="Vendas feitas sem internet, recusadas e vendidas sem estoque")
def ver(db: DB, _: Gerente, de: date | None = None, ate: date | None = None) -> PainelOffline:
    de, ate, inicio, fim = _periodo(de, ate)
    nomes = dict(db.execute(select(Usuario.id, Usuario.nome)).all())
    terminais = dict(db.execute(select(Terminal.id, Terminal.nome)).all())
    no_periodo = (Venda.offline.is_(True), Venda.finalizada_em >= inicio, Venda.finalizada_em < fim)

    linhas = db.execute(
        select(Venda, Caixa.terminal_id).join(Caixa, Caixa.id == Venda.caixa_id)
        .where(*no_periodo).order_by(Venda.finalizada_em.desc()).limit(LIMITE)
    ).all()
    vendas = [
        VendaOffline(
            id=v.id, numero=v.numero, feita_em=v.finalizada_em, chegou_em=v.criado_em,
            operador=nomes.get(v.usuario_id, "?"), terminal=terminais.get(t), total=v.total, status=v.status,
        )
        for v, t in linhas
    ]
    quantidade, total = db.execute(
        select(func.count(), func.coalesce(func.sum(Venda.total), 0)).where(*no_periodo, Venda.status == "finalizada")
    ).one()

    faltas = db.execute(
        select(Venda.id, Venda.numero, Venda.finalizada_em, Produto.nome, VendaItem.sem_estoque)
        .join(VendaItem, VendaItem.venda_id == Venda.id).join(Produto, Produto.id == VendaItem.produto_id)
        .where(*no_periodo, VendaItem.sem_estoque > 0).order_by(Venda.finalizada_em.desc()).limit(LIMITE)
    ).all()

    caixas = db.scalar(
        select(func.count()).select_from(Caixa).where(
            or_(Caixa.aberto_offline.is_(True), Caixa.fechado_offline.is_(True)),
            Caixa.aberto_em < fim, func.coalesce(Caixa.fechado_em, Caixa.aberto_em) >= inicio,
        )
    )

    # Recusas: todas as pendentes, e as resolvidas no período.
    recusas = db.scalars(
        select(EnvioRecusado).where(or_(
            EnvioRecusado.resolvido_em.is_(None),
            (EnvioRecusado.resolvido_em >= inicio) & (EnvioRecusado.resolvido_em < fim),
        )).order_by(EnvioRecusado.resolvido_em.is_not(None), EnvioRecusado.feito_em.desc()).limit(LIMITE)
    ).all()
    pendentes = db.scalar(select(func.count()).select_from(EnvioRecusado).where(EnvioRecusado.resolvido_em.is_(None)))

    return PainelOffline(
        de=de,
        ate=ate,
        resumo=ResumoOffline(
            vendas=quantidade, total=total, caixas=caixas, itens_sem_estoque=len(faltas), recusas_pendentes=pendentes,
        ),
        vendas=vendas,
        sem_estoque=[
            ItemSemEstoque(venda_id=i, numero=n, feita_em=f, produto=p, quantidade=q) for i, n, f, p, q in faltas
        ],
        recusas=[
            Recusa(
                id=r.id, tipo=r.tipo, feito_em=r.feito_em, avisado_em=r.atualizado_em,
                operador=nomes.get(r.usuario_id, "?"), terminal=terminais.get(r.terminal_id), total=r.total,
                motivo=r.motivo, resolvido_em=r.resolvido_em, resolucao=r.resolucao,
            )
            for r in recusas
        ],
    )


@painel.post("/recusas/{recusa_id}/resolver", status_code=204, summary="Marcar recusa como resolvida à mão")
def resolver(db: DB, usuario: Gerente, recusa_id: UUID) -> None:
    recusa = db.get(EnvioRecusado, recusa_id)
    if recusa is None:
        raise NaoEncontrado("Envio recusado não encontrado")
    if recusa.resolvido_em is None:
        recusa.resolvido_em = _agora()
        recusa.resolucao = "manual"
        recusa.resolvido_por = usuario.usuario_id
        db.commit()
