from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from app.core.security import TokenDados
from app.modules.clientes.models import Cliente
from app.modules.compras.models import NotaEntrada, PedidoCompra
from app.modules.compras.pedidos import ABERTOS as PEDIDOS_ABERTOS
from app.modules.controlados.models import Receita
from app.modules.devolucoes.models import Devolucao
from app.modules.estoque.service import alertas
from app.modules.faltas.models import Falta
from app.modules.faltas.service import quantas_chegaram
from app.modules.farmacias.models import Farmacia
from app.modules.financeiro.models import Conta
from app.modules.metas import service as metas
from app.modules.pedidos.service import quantos_novos
from app.modules.produtos.models import Produto
from app.modules.servicos.models import AtendimentoServico
from app.modules.vendas.models import Caixa, EnvioRecusado, PreVenda, Venda
from app.shared.datas import FUSO, hoje

CENTAVO = Decimal("0.01")
LIMITE_LISTA = 6

ATENDEM = {"admin", "gerente", "farmaceutico", "caixa", "atendente"}
ESTOQUE = {"admin", "gerente", "farmaceutico", "estoque"}
FARMACIA = {"admin", "gerente", "farmaceutico"}
GERENCIA = {"admin", "gerente"}


def _soma(db: Session, filtro) -> dict:
    quantidade, total = db.execute(filtro).one()
    return {"quantidade": quantidade or 0, "total": total or Decimal(0)}


def _balcao(db: Session, usuario: TokenDados, dia_local) -> dict:
    caixa = db.scalar(select(Caixa).where(Caixa.status == "aberto", Caixa.usuario_id == usuario.usuario_id))
    meu_caixa = None
    if caixa is not None:
        vendas, total = db.execute(
            select(func.count(), func.coalesce(func.sum(Venda.total), 0))
            .where(Venda.caixa_id == caixa.id, Venda.status == "finalizada")
        ).one()
        meu_caixa = {"aberto_em": caixa.aberto_em, "vendas": vendas, "total": total}
    abertas = select(PreVenda).where(PreVenda.status == "aberta")
    return {
        "meu_caixa": meu_caixa,
        "pre_vendas_abertas": db.scalar(select(func.count()).select_from(abertas.subquery())),
        "pre_vendas": [
            {"id": p.id, "numero": p.numero, "total": p.total, "criado_em": p.criado_em, "entrega": p.entrega}
            for p in db.scalars(abertas.order_by(PreVenda.criado_em).limit(LIMITE_LISTA))
        ],
        "minhas_vendas_hoje": _soma(db, select(func.count(), func.sum(Venda.total)).where(
            Venda.vendedor_id == usuario.usuario_id, Venda.status == "finalizada", dia_local == hoje()
        )),
    }


def _estoque(db: Session, do_estoque) -> dict:
    # O que mais falta (em proporção do mínimo) aparece primeiro.
    repor = sorted(do_estoque.abaixo_do_minimo, key=lambda p: p.saldo / p.estoque_minimo)[:LIMITE_LISTA]
    return {
        "repor": [
            {"produto_id": p.produto_id, "nome": p.nome, "loja_nome": p.loja_nome, "saldo": p.saldo,
             "estoque_minimo": p.estoque_minimo}
            for p in repor
        ],
        "vencendo": [
            {"produto_id": lote.produto_id, "produto_nome": lote.produto_nome, "numero_lote": lote.numero_lote,
             "loja_nome": lote.loja_nome, "quantidade": lote.quantidade, "validade": lote.validade,
             "dias_para_vencer": lote.dias_para_vencer or 0}
            for lote in do_estoque.vencendo[:LIMITE_LISTA]
        ],
        "notas_para_conferir": db.scalar(
            select(func.count()).select_from(NotaEntrada).where(NotaEntrada.status == "pendente")
        ),
        "pedidos_compra_abertos": db.scalar(
            select(func.count()).select_from(PedidoCompra).where(PedidoCompra.status.in_(PEDIDOS_ABERTOS))
        ),
        "encomendas_pendentes": db.scalar(select(func.count()).select_from(Falta).where(Falta.status == "aberta")),
    }


def _farmacia(db: Session) -> dict:
    criado_hoje = cast(func.timezone(FUSO.key, Receita.criado_em), Date) == hoje()
    atendido_hoje = cast(func.timezone(FUSO.key, AtendimentoServico.criado_em), Date) == hoje()
    return {
        "controlados_hoje": db.scalar(
            select(func.count()).select_from(Receita).join(Venda, Venda.id == Receita.venda_id)
            .where(criado_hoje, Venda.status == "finalizada")
        ),
        "atendimentos_hoje": db.scalar(
            select(func.count()).select_from(AtendimentoServico)
            .where(atendido_hoje, AtendimentoServico.status == "registrado")
        ),
    }


def _gestao(db: Session) -> dict:
    def contas(tipo: str, condicao):
        return _soma(db, select(func.count(), func.sum(Conta.valor)).where(
            Conta.tipo == tipo, Conta.status == "aberta", condicao
        ))

    return {
        "pagar_vencidas": contas("pagar", Conta.vencimento < hoje()),
        "pagar_hoje": contas("pagar", Conta.vencimento == hoje()),
        "receber_vencidas": contas("receber", Conta.vencimento < hoje()),
        "envios_recusados": db.scalar(
            select(func.count()).select_from(EnvioRecusado).where(EnvioRecusado.resolvido_em.is_(None))
        ),
    }


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

    # Itens devolvidos saem do dia da venda.
    for dia, valor in db.execute(
        select(dia_local, func.sum(Devolucao.valor_total))
        .join(Devolucao, Devolucao.venda_id == Venda.id)
        .where(Venda.status == "finalizada", dia_local >= inicio - timedelta(days=1))
        .group_by(dia_local)
    ):
        if dia in por_dia:
            linha = por_dia[dia]
            por_dia[dia] = SimpleNamespace(total=linha.total - valor, quantidade=linha.quantidade)

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
    do_estoque = alertas(db, farmacia.dias_alerta_vencimento)

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
        "dias_alerta_vencimento": farmacia.dias_alerta_vencimento,
        "clientes": db.scalar(select(func.count()).select_from(Cliente).where(Cliente.ativo.is_(True))),
        "abaixo_do_minimo": len(do_estoque.abaixo_do_minimo),
        "encomendas_chegaram": quantas_chegaram(db),
        "pedidos_novos": quantos_novos(db),
        "meta_farmacia": metas.da_farmacia(db),
        "minha_meta": metas.do_vendedor(db, usuario.usuario_id),
        "balcao": _balcao(db, usuario, dia_local) if usuario.papel in ATENDEM else None,
        "estoque": _estoque(db, do_estoque) if usuario.papel in ESTOQUE else None,
        "farmacia_bloco": _farmacia(db) if usuario.papel in FARMACIA else None,
        "gestao": _gestao(db) if usuario.papel in GERENCIA else None,
    }
