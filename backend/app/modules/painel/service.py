from datetime import timedelta
from decimal import Decimal

from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from app.core.security import TokenDados
from app.modules.estoque.service import alertas
from app.modules.farmacias.models import Farmacia
from app.modules.produtos.models import Produto
from app.modules.vendas.models import Caixa, Venda
from app.shared.datas import FUSO, hoje

DIAS_VENCENDO = 30
CENTAVO = Decimal("0.01")


def painel(db: Session, usuario: TokenDados) -> dict:
    dia_hoje = hoje()
    inicio = dia_hoje - timedelta(days=6)

    # Agrupa pela data local da venda, não pela data UTC.
    dia_local = cast(func.timezone(FUSO.key, Venda.finalizada_em), Date)
    por_dia = {
        linha.dia: linha
        for linha in db.execute(
            select(dia_local.label("dia"), func.sum(Venda.total).label("total"), func.count().label("quantidade"))
            .where(Venda.status == "finalizada", dia_local >= inicio - timedelta(days=1))
            .group_by(dia_local)
        )
    }

    def total(dia):
        linha = por_dia.get(dia)
        return linha.total if linha else Decimal(0)

    def quantidade(dia):
        linha = por_dia.get(dia)
        return linha.quantidade if linha else 0

    quantidade_hoje = quantidade(dia_hoje)
    ticket = (total(dia_hoje) / quantidade_hoje).quantize(CENTAVO) if quantidade_hoje else Decimal(0)

    farmacia = db.get(Farmacia, usuario.farmacia_id)
    caixas_abertos = db.scalars(select(Caixa.usuario_id).where(Caixa.status == "aberto")).all()
    do_estoque = alertas(db, DIAS_VENCENDO)

    return {
        "farmacia": farmacia.nome_fantasia,
        "uf": farmacia.uf,
        "hoje": dia_hoje,
        "vendas_hoje": total(dia_hoje),
        "quantidade_vendas_hoje": quantidade_hoje,
        "ticket_medio_hoje": ticket,
        "vendas_ontem": total(dia_hoje - timedelta(days=1)),
        "semana": [
            {"data": dia, "total": total(dia), "quantidade": quantidade(dia)}
            for dia in (inicio + timedelta(days=i) for i in range(7))
        ],
        "caixas_abertos": len(caixas_abertos),
        "meu_caixa_aberto": usuario.usuario_id in caixas_abertos,
        "produtos_ativos": db.scalar(select(func.count()).select_from(Produto).where(Produto.ativo.is_(True))),
        "lotes_vencidos": len(do_estoque.vencidos),
        "lotes_vencendo": len(do_estoque.vencendo),
        "abaixo_do_minimo": len(do_estoque.abaixo_do_minimo),
    }
