"""Convênios: limite e desconto do funcionário, compra no caixa e fatura mensal para a empresa."""

import csv
import io
from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import TokenDados
from app.modules.clientes.models import Cliente
from app.modules.convenios.models import CompraConvenio, Convenio
from app.modules.convenios.schemas import (
    CompraSaida,
    ConvenioAtualizar,
    ConvenioCriar,
    ConvenioDetalhe,
    ConvenioDoCliente,
    ConvenioResumo,
    ConvenioSaida,
    FaturaSaida,
    Funcionario,
)
from app.modules.financeiro.models import Conta
from app.modules.lojas.service import matriz
from app.modules.vendas.models import Venda
from app.shared.datas import hoje
from app.shared.erros import Conflito, ErroDeNegocio, NaoEncontrado

ZERO = Decimal(0)
CENTAVO = Decimal("0.01")


# --- Cadastro ---

def obter(db: Session, convenio_id: UUID) -> Convenio:
    convenio = db.get(Convenio, convenio_id)
    if convenio is None:
        raise NaoEncontrado("Convênio não encontrado")
    return convenio


def criar(db: Session, dados: ConvenioCriar) -> Convenio:
    convenio = Convenio(**dados.model_dump())
    db.add(convenio)
    db.commit()
    db.refresh(convenio)
    return convenio


def atualizar(db: Session, convenio_id: UUID, dados: ConvenioAtualizar) -> Convenio:
    convenio = obter(db, convenio_id)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        if valor is None and campo in ("nome", "desconto", "limite_padrao", "dia_fechamento", "dias_para_pagar", "ativo"):
            continue
        setattr(convenio, campo, valor)
    db.commit()
    db.refresh(convenio)
    return convenio


def fechamento_previsto(convenio: Convenio, dia: date) -> date:
    """O último dia de fechamento que já chegou (deste mês ou do anterior)."""
    if dia.day >= convenio.dia_fechamento:
        return dia.replace(day=convenio.dia_fechamento)
    anterior = dia.replace(day=1) - timedelta(days=1)
    return anterior.replace(day=convenio.dia_fechamento)


def _usado_por_cliente(db: Session, clientes: list[UUID]) -> dict[UUID, Decimal]:
    if not clientes:
        return {}
    return dict(
        db.execute(
            select(CompraConvenio.cliente_id, func.sum(CompraConvenio.valor))
            .where(CompraConvenio.cliente_id.in_(clientes), CompraConvenio.status == "aberta")
            .group_by(CompraConvenio.cliente_id)
        ).all()
    )


def _resumos(db: Session, convenios: list[Convenio]) -> list[ConvenioResumo]:
    ids = [c.id for c in convenios]
    funcionarios: dict[UUID, int] = {}
    em_aberto: dict[UUID, Decimal] = {}
    a_receber: dict[UUID, Decimal] = {}
    mais_antiga: dict[UUID, date] = {}
    if ids:
        funcionarios = dict(db.execute(
            select(Cliente.convenio_id, func.count()).where(Cliente.convenio_id.in_(ids), Cliente.ativo.is_(True))
            .group_by(Cliente.convenio_id)
        ).all())
        for convenio_id, total, primeira in db.execute(
            select(CompraConvenio.convenio_id, func.sum(CompraConvenio.valor), func.min(CompraConvenio.data))
            .where(CompraConvenio.convenio_id.in_(ids), CompraConvenio.status == "aberta")
            .group_by(CompraConvenio.convenio_id)
        ):
            em_aberto[convenio_id] = total
            mais_antiga[convenio_id] = primeira
        a_receber = dict(db.execute(
            select(Conta.convenio_id, func.sum(Conta.valor)).where(Conta.convenio_id.in_(ids), Conta.status == "aberta")
            .group_by(Conta.convenio_id)
        ).all())
    dia = hoje()
    resumos = []
    for convenio in convenios:
        previsto = fechamento_previsto(convenio, dia)
        resumos.append(ConvenioResumo(
            **ConvenioSaida.model_validate(convenio).model_dump(),
            funcionarios=funcionarios.get(convenio.id, 0),
            em_aberto=em_aberto.get(convenio.id, ZERO),
            a_receber=a_receber.get(convenio.id, ZERO),
            fechamento=previsto,
            pronto_para_fechar=convenio.id in mais_antiga and mais_antiga[convenio.id] <= previsto,
        ))
    return resumos


def listar(db: Session, incluir_inativos: bool = False) -> list[ConvenioResumo]:
    filtro = select(Convenio)
    if not incluir_inativos:
        filtro = filtro.where(Convenio.ativo.is_(True))
    return _resumos(db, db.scalars(filtro.order_by(Convenio.nome)).all())


def _limite(convenio: Convenio, cliente: Cliente) -> Decimal:
    return cliente.convenio_limite if cliente.convenio_limite is not None else convenio.limite_padrao


def _compras_saida(db: Session, compras: list[CompraConvenio]) -> list[CompraSaida]:
    clientes = {c.cliente_id for c in compras}
    vendas = {c.venda_id for c in compras}
    pessoas = {
        c.id: c for c in db.scalars(select(Cliente).where(Cliente.id.in_(clientes)))
    } if clientes else {}
    numeros = dict(db.execute(select(Venda.id, Venda.numero).where(Venda.id.in_(vendas))).all()) if vendas else {}
    return [
        CompraSaida(
            id=c.id,
            venda_id=c.venda_id,
            venda_numero=numeros.get(c.venda_id, 0),
            cliente_id=c.cliente_id,
            nome=pessoas[c.cliente_id].nome,
            matricula=pessoas[c.cliente_id].convenio_matricula,
            data=c.data,
            valor=c.valor,
            status=c.status,
            conta_id=c.conta_id,
        )
        for c in compras
    ]


def detalhe(db: Session, convenio_id: UUID) -> ConvenioDetalhe:
    convenio = obter(db, convenio_id)
    clientes = db.scalars(select(Cliente).where(Cliente.convenio_id == convenio.id).order_by(Cliente.nome)).all()
    usado = _usado_por_cliente(db, [c.id for c in clientes])
    funcionarios = []
    for cliente in clientes:
        limite = _limite(convenio, cliente)
        gasto = usado.get(cliente.id, ZERO)
        funcionarios.append(Funcionario(
            cliente_id=cliente.id, nome=cliente.nome, cpf=cliente.cpf, matricula=cliente.convenio_matricula,
            limite=limite, usado=gasto, disponivel=max(limite - gasto, ZERO), ativo=cliente.ativo,
        ))
    abertas = db.scalars(
        select(CompraConvenio)
        .where(CompraConvenio.convenio_id == convenio.id, CompraConvenio.status == "aberta")
        .order_by(CompraConvenio.data, CompraConvenio.criado_em)
    ).all()
    contas = db.scalars(
        select(Conta).where(Conta.convenio_id == convenio.id, Conta.status != "cancelada")
        .order_by(Conta.vencimento.desc()).limit(24)
    ).all()
    quantidades = dict(db.execute(
        select(CompraConvenio.conta_id, func.count()).where(CompraConvenio.conta_id.in_([c.id for c in contas]))
        .group_by(CompraConvenio.conta_id)
    ).all()) if contas else {}
    dia = hoje()
    faturas = [
        FaturaSaida(
            conta_id=c.id, descricao=c.descricao, valor=c.valor, vencimento=c.vencimento, status=c.status,
            vencida=c.status == "aberta" and c.vencimento < dia, pago_em=c.pago_em, compras=quantidades.get(c.id, 0),
        )
        for c in contas
    ]
    return ConvenioDetalhe(
        convenio=_resumos(db, [convenio])[0],
        funcionarios=funcionarios,
        compras_abertas=_compras_saida(db, abertas),
        faturas=faturas,
    )


# --- No caixa ---

def _convenio_ativo(db: Session, cliente: Cliente | None) -> Convenio | None:
    if cliente is None or cliente.convenio_id is None or not cliente.ativo:
        return None
    convenio = db.get(Convenio, cliente.convenio_id)
    return convenio if convenio is not None and convenio.ativo else None


def do_cliente(db: Session, cliente_id: UUID) -> ConvenioDoCliente:
    cliente = db.get(Cliente, cliente_id)
    convenio = _convenio_ativo(db, cliente)
    if convenio is None:
        raise NaoEncontrado("Este cliente não é de nenhum convênio ativo")
    limite = _limite(convenio, cliente)
    usado = _usado_por_cliente(db, [cliente.id]).get(cliente.id, ZERO)
    return ConvenioDoCliente(
        convenio_id=convenio.id, nome=convenio.nome, desconto=convenio.desconto,
        limite=limite, usado=usado, disponivel=max(limite - usado, ZERO),
    )


def desconto_do_cliente(db: Session, cliente_id: UUID | None, base: Decimal) -> Decimal:
    """Desconto da empresa conveniada sobre `base` (já sem as promoções). Zero se não for conveniado."""
    if cliente_id is None or base <= 0:
        return ZERO
    convenio = _convenio_ativo(db, db.get(Cliente, cliente_id))
    if convenio is None or not convenio.desconto:
        return ZERO
    return (base * convenio.desconto / 100).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def lancar_compra(db: Session, venda: Venda, loja_id: UUID, valor: Decimal) -> CompraConvenio:
    """Confere o limite do funcionário e guarda a compra para a próxima fatura. Não faz commit."""
    if venda.cliente_id is None:
        raise ErroDeNegocio("Escolha o cliente (funcionário da empresa) para vender no convênio")
    # Trava o cliente: duas vendas ao mesmo tempo não passam juntas do limite.
    cliente = db.scalar(select(Cliente).where(Cliente.id == venda.cliente_id).with_for_update())
    convenio = _convenio_ativo(db, cliente)
    if convenio is None:
        raise ErroDeNegocio(f"{cliente.nome if cliente else 'Este cliente'} não é de nenhum convênio ativo")
    disponivel = _limite(convenio, cliente) - _usado_por_cliente(db, [cliente.id]).get(cliente.id, ZERO)
    if valor > disponivel:
        raise ErroDeNegocio(
            f"Limite de {cliente.nome} no convênio {convenio.nome} insuficiente: disponível R$ {max(disponivel, ZERO):.2f}"
        )
    compra = CompraConvenio(
        convenio_id=convenio.id, cliente_id=cliente.id, venda_id=venda.id, loja_id=loja_id, valor=valor, data=hoje()
    )
    db.add(compra)
    return compra


def cancelar_da_venda(db: Session, venda: Venda) -> None:
    compra = db.scalar(select(CompraConvenio).where(CompraConvenio.venda_id == venda.id))
    if compra is None or compra.status == "cancelada":
        return
    if compra.status == "faturada":
        raise Conflito(
            "Esta compra já está na fatura do convênio. Desfaça a fatura em Convênios antes de cancelar a venda."
        )
    compra.status = "cancelada"


# --- Fatura ---

def fechar(db: Session, usuario: TokenDados, convenio_id: UUID, ate: date | None) -> Conta:
    """Junta as compras até `ate` numa conta a receber da empresa."""
    convenio = obter(db, convenio_id)
    dia = hoje()
    ate = ate or fechamento_previsto(convenio, dia)
    if ate > dia:
        raise ErroDeNegocio("Não dá para fechar uma data que ainda não chegou")
    compras = db.scalars(
        select(CompraConvenio)
        .where(CompraConvenio.convenio_id == convenio.id, CompraConvenio.status == "aberta", CompraConvenio.data <= ate)
        .with_for_update()
    ).all()
    if not compras:
        raise ErroDeNegocio(f"Nenhuma compra do convênio {convenio.nome} até {ate:%d/%m/%Y} para faturar")
    inicio = min(c.data for c in compras)
    conta = Conta(
        tipo="receber",
        loja_id=matriz(db).id,
        descricao=f"Convênio {convenio.nome}: compras de {inicio:%d/%m} a {ate:%d/%m/%Y}"[:200],
        categoria="convenio",
        documento=f"{ate:%m/%Y}",
        valor=sum((c.valor for c in compras), ZERO),
        vencimento=max(ate + timedelta(days=convenio.dias_para_pagar), dia),
        convenio_id=convenio.id,
        usuario_id=usuario.usuario_id,
    )
    db.add(conta)
    db.flush()
    for compra in compras:
        compra.status = "faturada"
        compra.conta_id = conta.id
    db.commit()
    return conta


def _fatura(db: Session, conta_id: UUID) -> Conta:
    conta = db.scalar(select(Conta).where(Conta.id == conta_id, Conta.convenio_id.is_not(None)).with_for_update())
    if conta is None:
        raise NaoEncontrado("Fatura não encontrada")
    return conta


def desfazer(db: Session, conta_id: UUID) -> None:
    """Cancela a fatura (ainda não paga) e as compras voltam para o próximo fechamento."""
    conta = _fatura(db, conta_id)
    if conta.status != "aberta":
        raise Conflito("Esta fatura já foi paga ou cancelada. Estorne o recebimento em Financeiro antes.")
    for compra in db.scalars(select(CompraConvenio).where(CompraConvenio.conta_id == conta.id)):
        compra.status = "aberta"
        compra.conta_id = None
    conta.status = "cancelada"
    db.commit()


def extrato_csv(db: Session, convenio_id: UUID, conta_id: UUID | None) -> tuple[str, bytes]:
    """Lista por funcionário para a empresa descontar na folha: da fatura, ou o que está em aberto."""
    convenio = obter(db, convenio_id)
    filtro = select(CompraConvenio).where(CompraConvenio.convenio_id == convenio.id)
    if conta_id is not None:
        conta = _fatura(db, conta_id)
        if conta.convenio_id != convenio.id:
            raise NaoEncontrado("Fatura não encontrada")
        filtro = filtro.where(CompraConvenio.conta_id == conta.id)
        nome = f"convenio-{conta.documento.replace('/', '-')}.csv"
    else:
        filtro = filtro.where(CompraConvenio.status == "aberta")
        nome = f"convenio-em-aberto-{hoje():%Y%m%d}.csv"
    compras = _compras_saida(db, db.scalars(filtro.order_by(CompraConvenio.data)).all())

    por_pessoa: dict[UUID, list[CompraSaida]] = defaultdict(list)
    for compra in compras:
        por_pessoa[compra.cliente_id].append(compra)
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";")
    escritor.writerow([f"Convênio {convenio.nome}"])
    escritor.writerow(["Funcionário", "Matrícula", "Data", "Venda", "Valor"])
    total = ZERO
    for itens in sorted(por_pessoa.values(), key=lambda l: l[0].nome):
        for c in itens:
            escritor.writerow([c.nome, c.matricula or "", f"{c.data:%d/%m/%Y}", c.venda_numero, _br(c.valor)])
        soma = sum((c.valor for c in itens), ZERO)
        total += soma
        escritor.writerow([f"Total de {itens[0].nome}", "", "", "", _br(soma)])
    escritor.writerow(["Total da empresa", "", "", "", _br(total)])
    # Com BOM, o Excel abre os acentos certos.
    return nome.replace(" ", "-"), ("﻿" + saida.getvalue()).encode("utf-8")


def _br(valor: Decimal) -> str:
    return f"{valor:.2f}".replace(".", ",")
