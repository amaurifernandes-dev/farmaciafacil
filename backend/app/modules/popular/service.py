"""Farmácia Popular: a venda com a parte do governo, e o que a farmácia tem a receber em cada mês."""

import calendar
import csv
import io
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import TokenDados
from app.modules.farmacias.models import Farmacia
from app.modules.financeiro.models import Conta
from app.modules.financeiro.service import saidas as contas_saida
from app.modules.lojas.service import matriz
from app.modules.popular.models import VendaPopular
from app.modules.popular.regras import parte_do_governo
from app.modules.popular.schemas import MesPopular, PopularDados, VendaPopularSaida
from app.modules.produtos.models import Produto
from app.modules.vendas.models import Venda, VendaItem
from app.shared.datas import hoje
from app.shared.erros import Conflito, ErroDeNegocio, NaoEncontrado

ZERO = Decimal(0)


# --- No caixa ---

def preparar(
    db: Session,
    farmacia: Farmacia,
    dados: PopularDados | None,
    itens: list[VendaItem],
    produtos: list[Produto],
    no_popular: Decimal,
    dia: date,
) -> tuple[Decimal, list[dict]]:
    """Confere a receita e a autorização e calcula a parte do governo. Devolve (valor, itens do programa)."""
    if dados is None:
        if no_popular:
            raise ErroDeNegocio("Preencha os dados da Farmácia Popular (paciente, receita e autorização)")
        return ZERO, []

    if dados.receita_data > dia:
        raise ErroDeNegocio("A data da receita não pode ser no futuro")
    venceu = dados.receita_data + timedelta(days=farmacia.popular_validade_receita)
    if venceu < dia:
        raise ErroDeNegocio(
            f"A receita é de {dados.receita_data:%d/%m/%Y} e venceu em {venceu:%d/%m/%Y} "
            f"(vale {farmacia.popular_validade_receita} dias). Peça uma receita nova."
        )

    do_programa = []
    for item, produto in zip(itens, produtos):
        governo = parte_do_governo(produto.popular_valor, item.quantidade, item.total)
        if governo > 0:
            do_programa.append({
                "produto_id": str(produto.id),
                "descricao": item.descricao,
                "quantidade": str(item.quantidade),
                "total": str(item.total),
                "governo": str(governo),
            })
    if not do_programa:
        raise ErroDeNegocio("Nenhum remédio desta venda está na Farmácia Popular")
    governo = sum((Decimal(i["governo"]) for i in do_programa), ZERO)

    _conferir_intervalo(db, farmacia, dados.paciente_cpf, do_programa, dia)
    usada = db.scalar(
        select(VendaPopular).where(VendaPopular.autorizacao == dados.autorizacao, VendaPopular.status != "cancelada")
    )
    if usada is not None:
        numero = db.get(Venda, usada.venda_id).numero
        raise Conflito(f"A autorização {dados.autorizacao} já foi usada na venda nº {numero}")
    if no_popular != governo:
        raise ErroDeNegocio(f"A parte do governo nesta venda é R$ {governo:.2f}. Lance esse valor em Farmácia Popular.")
    return governo, do_programa


def _conferir_intervalo(db: Session, farmacia: Farmacia, cpf: str, itens: list[dict], dia: date) -> None:
    """O paciente leva o remédio para um período; antes disso, o governo não paga de novo."""
    if not farmacia.popular_intervalo_dias:
        return
    desde = dia - timedelta(days=farmacia.popular_intervalo_dias - 1)
    anteriores = db.scalars(
        select(VendaPopular)
        .where(VendaPopular.paciente_cpf == cpf, VendaPopular.status != "cancelada", VendaPopular.data >= desde)
        .order_by(VendaPopular.data.desc())
    ).all()
    agora = {i["produto_id"]: i["descricao"] for i in itens}
    for anterior in anteriores:
        for item in anterior.itens:
            if item["produto_id"] in agora:
                volta = anterior.data + timedelta(days=farmacia.popular_intervalo_dias)
                raise ErroDeNegocio(
                    f"Este paciente já levou {item['descricao']} pela Farmácia Popular em {anterior.data:%d/%m/%Y}. "
                    f"Pode levar de novo a partir de {volta:%d/%m/%Y}."
                )


def lancar(
    db: Session, venda: Venda, loja_id: UUID, dados: PopularDados, governo: Decimal, itens: list[dict], dia: date
) -> VendaPopular:
    registro = VendaPopular(
        venda_id=venda.id,
        loja_id=loja_id,
        data=dia,
        valor_governo=governo,
        valor_paciente=venda.total - governo,
        itens=itens,
        **dados.model_dump(),
    )
    db.add(registro)
    return registro


def cancelar_da_venda(db: Session, venda: Venda) -> None:
    registro = db.scalar(select(VendaPopular).where(VendaPopular.venda_id == venda.id).with_for_update())
    if registro is None or registro.status == "cancelada":
        return
    if registro.status == "lancada":
        raise Conflito(
            "A parte do governo desta venda já foi lançada no Financeiro. "
            "Desfaça o lançamento em Farmácia Popular antes de cancelar."
        )
    registro.status = "cancelada"


# --- Consulta ---

def _saidas(db: Session, registros: list[VendaPopular]) -> list[VendaPopularSaida]:
    numeros = dict(db.execute(select(Venda.id, Venda.numero).where(Venda.id.in_([r.venda_id for r in registros]))).all())
    return [
        VendaPopularSaida.model_validate(r).model_copy(update={"numero": numeros.get(r.venda_id, 0)})
        for r in registros
    ]


def da_venda(db: Session, venda_id: UUID) -> VendaPopularSaida:
    registro = db.scalar(select(VendaPopular).where(VendaPopular.venda_id == venda_id))
    if registro is None:
        raise NaoEncontrado("Esta venda não foi pela Farmácia Popular")
    return _saidas(db, [registro])[0]


def _periodo(mes: str) -> tuple[date, date]:
    ano, numero = (int(p) for p in mes.split("-"))
    return date(ano, numero, 1), date(ano, numero, calendar.monthrange(ano, numero)[1])


def _do_mes(db: Session, mes: str, travar: bool = False) -> list[VendaPopular]:
    inicio, fim = _periodo(mes)
    consulta = (
        select(VendaPopular)
        .where(VendaPopular.data.between(inicio, fim), VendaPopular.status != "cancelada")
        .order_by(VendaPopular.data, VendaPopular.criado_em)
    )
    return db.scalars(consulta.with_for_update() if travar else consulta).all()


def resumo_do_mes(db: Session, mes: str) -> MesPopular:
    registros = _do_mes(db, mes)
    contas = sorted({r.conta_id for r in registros if r.conta_id})
    lancamentos = db.scalars(select(Conta).where(Conta.id.in_(contas)).order_by(Conta.criado_em)).all() if contas else []
    em_aberto = sum((r.valor_governo for r in registros if r.status == "aberta"), ZERO)
    return MesPopular(
        mes=mes,
        vendas=_saidas(db, list(reversed(registros))),
        quantidade=len(registros),
        pacientes=len({r.paciente_cpf for r in registros}),
        total_governo=sum((r.valor_governo for r in registros), ZERO),
        total_paciente=sum((r.valor_paciente for r in registros), ZERO),
        em_aberto=em_aberto,
        lancamentos=contas_saida(db, lancamentos),
        pode_lancar=em_aberto > 0,
    )


# --- Lançamento no Financeiro ---

def lancar_mes(db: Session, usuario: TokenDados, mes: str) -> Conta:
    """Junta a parte do governo das vendas do mês numa conta a receber."""
    inicio, fim = _periodo(mes)
    if inicio > hoje():
        raise ErroDeNegocio("Este mês ainda não começou")
    abertas = [r for r in _do_mes(db, mes, travar=True) if r.status == "aberta"]
    if not abertas:
        raise ErroDeNegocio(f"Nada da Farmácia Popular em {inicio:%m/%Y} para lançar")
    # O Ministério paga o mês no mês seguinte.
    proximo = fim + timedelta(days=1)
    vencimento = date(proximo.year, proximo.month, calendar.monthrange(proximo.year, proximo.month)[1])
    conta = Conta(
        tipo="receber",
        loja_id=matriz(db).id,
        descricao=f"Farmácia Popular: vendas de {inicio:%m/%Y} ({len(abertas)} vendas)",
        categoria="popular",
        documento=f"{inicio:%m/%Y}",
        valor=sum((r.valor_governo for r in abertas), ZERO),
        vencimento=vencimento,
        usuario_id=usuario.usuario_id,
    )
    db.add(conta)
    db.flush()
    for registro in abertas:
        registro.status = "lancada"
        registro.conta_id = conta.id
    db.commit()
    return conta


def desfazer(db: Session, conta_id: UUID) -> None:
    """Cancela o lançamento (ainda não recebido) e as vendas voltam a ficar em aberto."""
    conta = db.scalar(select(Conta).where(Conta.id == conta_id, Conta.categoria == "popular").with_for_update())
    if conta is None:
        raise NaoEncontrado("Lançamento não encontrado")
    if conta.status != "aberta":
        raise Conflito("Este lançamento já foi recebido ou cancelado. Estorne o recebimento em Financeiro antes.")
    for registro in db.scalars(select(VendaPopular).where(VendaPopular.conta_id == conta.id)):
        registro.status = "aberta"
        registro.conta_id = None
    conta.status = "cancelada"
    db.commit()


# --- Planilha ---

def planilha_csv(db: Session, mes: str) -> tuple[str, bytes]:
    """As vendas do mês, para conferir com o extrato do Ministério e guardar para a auditoria."""
    registros = _saidas(db, _do_mes(db, mes))
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";")
    escritor.writerow(["Data", "Venda", "Autorização", "Paciente", "CPF", "CRM", "Data da receita", "Remédios",
                       "Governo paga", "Paciente pagou", "Situação"])
    situacoes = {"aberta": "A lançar", "lancada": "Lançada no Financeiro"}
    for r in registros:
        remedios = ", ".join(f"{_qtd(i.quantidade)} {i.descricao}" for i in r.itens)
        escritor.writerow([
            f"{r.data:%d/%m/%Y}", r.numero, r.autorizacao, r.paciente_nome, _cpf(r.paciente_cpf),
            f"{r.prescritor_crm}/{r.prescritor_uf}", f"{r.receita_data:%d/%m/%Y}", remedios,
            _br(r.valor_governo), _br(r.valor_paciente), situacoes.get(r.status, r.status),
        ])
    escritor.writerow(["Total", "", "", "", "", "", "", "",
                       _br(sum((r.valor_governo for r in registros), ZERO)),
                       _br(sum((r.valor_paciente for r in registros), ZERO)), ""])
    return f"farmacia-popular-{mes}.csv", saida.getvalue().encode("utf-8-sig")


def _br(valor: Decimal) -> str:
    return f"{valor:.2f}".replace(".", ",")


def _qtd(valor: Decimal) -> str:
    return f"{valor.normalize():f}".replace(".", ",")


def _cpf(cpf: str) -> str:
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
