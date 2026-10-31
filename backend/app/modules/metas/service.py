"""Metas de vendas do mês, de cada loja e de cada vendedor, e o andamento de cada uma."""

import calendar
from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import Date, cast, delete, func, literal_column, select
from sqlalchemy.orm import Session

from app.modules.auth.models import Usuario
from app.modules.lojas.models import Loja
from app.modules.metas.models import Meta
from app.modules.metas.schemas import Andamento, MetasDoMes, SalvarMetas
from app.modules.vendas.models import Caixa, Venda
from app.shared.datas import FUSO, hoje
from app.shared.erros import ErroDeNegocio, NaoEncontrado

ZERO = Decimal(0)
CENTAVO = Decimal("0.01")
NOMES_PAPEIS = {"admin": "Administrador", "gerente": "Gerente", "farmaceutico": "Farmacêutico",
                "caixa": "Caixa", "atendente": "Atendente"}
VENDEDORES = ("caixa", "atendente", "farmaceutico")


def primeiro_dia(dia: date) -> date:
    return dia.replace(day=1)


def _ultimo_dia(mes: date) -> date:
    return mes.replace(day=calendar.monthrange(mes.year, mes.month)[1])


def _dias(mes: date, dia_hoje: date) -> tuple[int, int, int]:
    """Dias no mês, dias que já passaram (contando hoje) e dias que faltam (contando hoje)."""
    total = calendar.monthrange(mes.year, mes.month)[1]
    if primeiro_dia(dia_hoje) == mes:
        return total, dia_hoje.day, total - dia_hoje.day + 1
    if mes < dia_hoje:
        return total, total, 0
    return total, 0, total


def _somas(db: Session, inicio: date, fim: date, dia_hoje: date):
    """Vendido (sem a taxa de entrega) por loja e por vendedor no período, e o de hoje."""
    dia = cast(func.timezone(literal_column(f"'{FUSO.key}'"), Venda.finalizada_em), Date)
    linhas = db.execute(
        select(Caixa.loja_id, Venda.vendedor_id, (dia == dia_hoje).label("hoje"),
               func.sum(Venda.total - Venda.taxa_entrega), func.count())
        .join(Caixa, Caixa.id == Venda.caixa_id)
        .where(Venda.status == "finalizada", dia.between(inicio, fim))
        .group_by(Caixa.loja_id, Venda.vendedor_id, "hoje")
    ).all()
    por_loja: dict = defaultdict(lambda: [ZERO, 0, ZERO])
    por_vendedor: dict = defaultdict(lambda: [ZERO, 0, ZERO])
    for loja_id, vendedor_id, de_hoje, valor, quantas in linhas:
        for conta in (por_loja[loja_id], por_vendedor[vendedor_id]):
            conta[0] += valor
            conta[1] += quantas
            if de_hoje:
                conta[2] += valor
    return por_loja, por_vendedor


def _andamento(id_, nome, detalhe, meta, conta, passado, dias) -> Andamento:
    vendido, vendas, vendido_hoje = conta
    no_mes, passados, restantes = dias
    base = {"id": id_, "nome": nome, "detalhe": detalhe, "meta": meta, "vendido": vendido, "vendas": vendas,
            "vendido_hoje": vendido_hoje, "vendido_mes_passado": passado}
    if meta is None:
        return Andamento(**base, percentual=None, esperado_ate_hoje=None, projecao=None, falta=None,
                         por_dia=None, situacao="sem_meta")
    falta = max(meta - vendido, ZERO)
    projecao = (vendido * no_mes / passados).quantize(CENTAVO, ROUND_HALF_UP) if passados else ZERO
    if vendido >= meta:
        situacao = "batida"
    elif restantes == 0:
        situacao = "nao_batida"
    elif passados == 0:
        situacao = "nao_comecou"
    else:
        situacao = "no_ritmo" if projecao >= meta else "abaixo"
    return Andamento(
        **base,
        percentual=(vendido * 100 / meta).quantize(Decimal("0.1"), ROUND_HALF_UP),
        esperado_ate_hoje=(meta * passados / no_mes).quantize(CENTAVO, ROUND_HALF_UP),
        projecao=projecao if passados else None,
        falta=falta,
        por_dia=(falta / restantes).quantize(CENTAVO, ROUND_HALF_UP) if restantes and falta else None,
        situacao=situacao,
    )


def do_mes(db: Session, mes: date) -> MetasDoMes:
    mes = primeiro_dia(mes)
    dia_hoje = hoje()
    dias = _dias(mes, dia_hoje)
    fim = min(_ultimo_dia(mes), dia_hoje)
    loja_vendido, vend_vendido = _somas(db, mes, fim, dia_hoje) if mes <= dia_hoje else ({}, {})
    anterior = primeiro_dia(mes - timedelta(days=1))
    loja_antes, vend_antes = _somas(db, anterior, _ultimo_dia(anterior), dia_hoje)

    metas = db.scalars(select(Meta).where(Meta.mes == mes)).all()
    meta_loja = {m.loja_id: m.valor for m in metas if m.loja_id}
    meta_vend = {m.usuario_id: m.valor for m in metas if m.usuario_id}

    vazio = (ZERO, 0, ZERO)
    lojas = db.scalars(select(Loja).order_by(Loja.matriz.desc(), Loja.nome)).all()
    lista_lojas = [
        _andamento(l.id, l.nome, "matriz" if l.matriz else None, meta_loja.get(l.id),
                   tuple(loja_vendido.get(l.id, vazio)), loja_antes.get(l.id, vazio)[0], dias)
        for l in lojas
    ]
    usuarios = db.scalars(select(Usuario)).all()
    lista_vend = [
        _andamento(u.id, u.nome, NOMES_PAPEIS.get(u.papel, u.papel), meta_vend.get(u.id),
                   tuple(vend_vendido.get(u.id, vazio)), vend_antes.get(u.id, vazio)[0], dias)
        for u in usuarios
        # Quem tem meta, vendeu neste mês ou no anterior, ou é da equipe de balcão.
        if u.id in meta_vend or u.id in vend_vendido or u.id in vend_antes or (u.ativo and u.papel in VENDEDORES)
    ]
    lista_vend.sort(key=lambda a: (a.meta is None, -(a.percentual or 0), -a.vendido, a.nome))

    soma = lambda campo: sum((getattr(a, campo) for a in lista_lojas), ZERO)
    meta_total = sum(meta_loja.values(), ZERO) or None
    total = _andamento(None, "Farmácia toda", None, meta_total,
                       (soma("vendido"), sum(a.vendas for a in lista_lojas), soma("vendido_hoje")),
                       soma("vendido_mes_passado"), dias)
    return MetasDoMes(mes=mes, dias_no_mes=dias[0], dias_passados=dias[1], dias_restantes=dias[2],
                      total=total, lojas=lista_lojas, vendedores=lista_vend)


def salvar(db: Session, dados: SalvarMetas) -> MetasDoMes:
    mes = primeiro_dia(dados.mes)
    if mes < primeiro_dia(hoje()):
        raise ErroDeNegocio("Não dá para mudar a meta de um mês que já passou")
    lojas = set(db.scalars(select(Loja.id)))
    usuarios = set(db.scalars(select(Usuario.id)))
    if any(item.id not in lojas for item in dados.lojas):
        raise NaoEncontrado("Loja não encontrada")
    if any(item.id not in usuarios for item in dados.vendedores):
        raise NaoEncontrado("Vendedor não encontrado")

    existentes = db.scalars(select(Meta).where(Meta.mes == mes)).all()
    por_loja = {m.loja_id: m for m in existentes if m.loja_id}
    por_vend = {m.usuario_id: m for m in existentes if m.usuario_id}
    for itens, atuais, campo in ((dados.lojas, por_loja, "loja_id"), (dados.vendedores, por_vend, "usuario_id")):
        for item in itens:
            meta = atuais.get(item.id)
            if item.valor is None:
                if meta is not None:
                    db.execute(delete(Meta).where(Meta.id == meta.id))
            elif meta is None:
                db.add(Meta(mes=mes, valor=item.valor, **{campo: item.id}))
            else:
                meta.valor = item.valor
    db.commit()
    return do_mes(db, mes)


def do_vendedor(db: Session, usuario_id: UUID) -> Andamento | None:
    """A meta do mês de quem está usando; nulo se não tem meta."""
    andamento = next((a for a in do_mes(db, hoje()).vendedores if a.id == usuario_id), None)
    return andamento if andamento and andamento.meta is not None else None


def da_farmacia(db: Session) -> Andamento | None:
    total = do_mes(db, hoje()).total
    return total if total.meta is not None else None
