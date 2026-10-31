"""Comissão dos vendedores: quanto cada um vendeu no período e quanto ganha."""

import csv
import io
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import Date, cast, func, literal_column, select
from sqlalchemy.orm import Session

from app.modules.auth.models import Usuario
from app.modules.comissoes.schemas import (
    DetalheVendedor,
    ProdutoDoVendedor,
    RelatorioComissoes,
    VendaDoVendedor,
    Vendedor,
)
from app.modules.farmacias.models import Farmacia
from app.modules.produtos.models import Produto
from app.modules.vendas.models import Caixa, PreVenda, Venda
from app.shared.datas import FUSO
from app.shared.erros import NaoEncontrado

ZERO = Decimal(0)
CENTAVO = Decimal("0.01")


@dataclass
class _Conta:
    vendas: int = 0
    vendido: Decimal = ZERO
    comissao: Decimal = ZERO
    lista: list[VendaDoVendedor] = field(default_factory=list)
    produtos: dict = field(default_factory=dict)


def _dia_local():
    return cast(func.timezone(literal_column(f"'{FUSO.key}'"), Venda.finalizada_em), Date)


def _vendas(db: Session, inicio: date, fim: date, loja_id: UUID | None, vendedor_id: UUID | None) -> list[Venda]:
    consulta = select(Venda).where(Venda.status == "finalizada", _dia_local().between(inicio, fim))
    if loja_id is not None:
        consulta = consulta.join(Caixa, Caixa.id == Venda.caixa_id).where(Caixa.loja_id == loja_id)
    if vendedor_id is not None:
        consulta = consulta.where(Venda.vendedor_id == vendedor_id)
    return db.scalars(consulta.order_by(Venda.finalizada_em)).all()


def _calcular(db: Session, farmacia: Farmacia, vendas: list[Venda]) -> dict[UUID, _Conta]:
    """Comissão de cada item sobre o que o cliente pagou por ele.

    Descontos da venda inteira (manual, pontos, convênio) são divididos entre os itens; a taxa de
    entrega não entra. O percentual é o gravado na venda; nas vendas antigas, a regra de hoje.
    """
    ids = {i.produto_id for v in vendas for i in v.itens}
    regra_atual = dict(db.execute(select(Produto.id, Produto.comissao).where(Produto.id.in_(ids))).all()) if ids else {}
    recebem = dict(db.execute(select(Usuario.id, Usuario.recebe_comissao)).all())
    de_pre_venda = set(
        db.scalars(select(PreVenda.venda_id).where(PreVenda.venda_id.in_([v.id for v in vendas])))
    ) if vendas else set()

    contas: dict[UUID, _Conta] = defaultdict(_Conta)
    for venda in vendas:
        soma_itens = sum((i.total for i in venda.itens), ZERO)
        pago_itens = venda.total - venda.taxa_entrega
        fator = min(pago_itens / soma_itens, Decimal(1)) if soma_itens > 0 else ZERO
        conta = contas[venda.vendedor_id]
        vendido_venda = comissao_venda = ZERO
        for item in venda.itens:
            base = (item.total * fator).quantize(CENTAVO, ROUND_HALF_UP)
            percentual = item.comissao
            if percentual is None:
                atual = regra_atual.get(item.produto_id)
                percentual = atual if atual is not None else farmacia.comissao_padrao
            if not recebem.get(venda.vendedor_id, True):
                percentual = ZERO
            valor = (base * percentual / 100).quantize(CENTAVO, ROUND_HALF_UP)
            vendido_venda += base
            comissao_venda += valor
            produto = conta.produtos.setdefault(
                item.produto_id,
                {"descricao": item.descricao, "quantidade": ZERO, "vendido": ZERO, "comissao": ZERO, "percentuais": set()},
            )
            produto["percentuais"].add(percentual)
            produto["quantidade"] += item.quantidade
            produto["vendido"] += base
            produto["comissao"] += valor
        conta.vendas += 1
        conta.vendido += vendido_venda
        conta.comissao += comissao_venda
        conta.lista.append(VendaDoVendedor(
            venda_id=venda.id, numero=venda.numero, finalizada_em=venda.finalizada_em,
            vendido=vendido_venda, comissao=comissao_venda, pre_venda=venda.id in de_pre_venda,
        ))
    return contas


def _vendedor(usuario: Usuario, conta: _Conta) -> Vendedor:
    return Vendedor(
        usuario_id=usuario.id,
        nome=usuario.nome,
        papel=usuario.papel,
        recebe_comissao=usuario.recebe_comissao,
        vendas=conta.vendas,
        vendido=conta.vendido,
        comissao=conta.comissao,
        ticket_medio=(conta.vendido / conta.vendas).quantize(CENTAVO, ROUND_HALF_UP) if conta.vendas else ZERO,
        percentual=(conta.comissao * 100 / conta.vendido).quantize(Decimal("0.01"), ROUND_HALF_UP)
        if conta.vendido else ZERO,
    )


def relatorio(db: Session, farmacia_id: UUID, inicio: date, fim: date, loja_id: UUID | None) -> RelatorioComissoes:
    farmacia = db.get(Farmacia, farmacia_id)
    contas = _calcular(db, farmacia, _vendas(db, inicio, fim, loja_id, None))
    usuarios = db.scalars(select(Usuario)).all()
    vendedores = [
        _vendedor(u, contas.get(u.id, _Conta()))
        for u in usuarios
        if u.id in contas or (u.ativo and u.papel in ("caixa", "atendente", "farmaceutico"))
    ]
    vendedores.sort(key=lambda v: (-v.vendido, v.nome))
    return RelatorioComissoes(
        inicio=inicio,
        fim=fim,
        comissao_padrao=farmacia.comissao_padrao,
        vendedores=vendedores,
        total_vendido=sum((v.vendido for v in vendedores), ZERO),
        total_comissao=sum((v.comissao for v in vendedores), ZERO),
    )


def detalhe(
    db: Session, farmacia_id: UUID, usuario_id: UUID, inicio: date, fim: date, loja_id: UUID | None
) -> DetalheVendedor:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise NaoEncontrado("Vendedor não encontrado")
    farmacia = db.get(Farmacia, farmacia_id)
    conta = _calcular(db, farmacia, _vendas(db, inicio, fim, loja_id, usuario_id)).get(usuario_id, _Conta())
    produtos = [
        ProdutoDoVendedor(
            produto_id=produto_id,
            descricao=p["descricao"],
            quantidade=p["quantidade"],
            vendido=p["vendido"],
            comissao=p["comissao"],
            # O percentual da regra; se mudou no meio do período, a média.
            percentual=next(iter(p["percentuais"])) if len(p["percentuais"]) == 1
            else (p["comissao"] * 100 / p["vendido"]).quantize(CENTAVO, ROUND_HALF_UP) if p["vendido"] else ZERO,
        )
        for produto_id, p in conta.produtos.items()
    ]
    produtos.sort(key=lambda p: (-p.comissao, -p.vendido))
    return DetalheVendedor(
        inicio=inicio, fim=fim, vendedor=_vendedor(usuario, conta),
        vendas=list(reversed(conta.lista)), produtos=produtos,
    )


def planilha_csv(db: Session, farmacia_id: UUID, inicio: date, fim: date, loja_id: UUID | None) -> tuple[str, bytes]:
    dados = relatorio(db, farmacia_id, inicio, fim, loja_id)
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";")
    escritor.writerow([f"Comissões de {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}"])
    escritor.writerow(["Vendedor", "Vendas", "Vendido", "Ticket médio", "% médio", "Comissão"])
    for v in dados.vendedores:
        escritor.writerow([
            v.nome + ("" if v.recebe_comissao else " (não recebe comissão)"), v.vendas, _br(v.vendido),
            _br(v.ticket_medio), _br(v.percentual), _br(v.comissao),
        ])
    escritor.writerow(["Total", sum(v.vendas for v in dados.vendedores), _br(dados.total_vendido), "", "",
                       _br(dados.total_comissao)])
    return f"comissoes-{inicio:%Y-%m-%d}-a-{fim:%Y-%m-%d}.csv", saida.getvalue().encode("utf-8-sig")


def _br(valor: Decimal) -> str:
    return f"{valor:.2f}".replace(".", ",")
