from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import extract, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.clientes.models import Cliente
from app.modules.convenios.models import Convenio
from app.modules.clientes.schemas import (
    ClienteAtualizar,
    ClienteCriar,
    ClienteLista,
    ClienteSaida,
    CompraCliente,
    FichaCliente,
    ProdutoFrequente,
    ResumoCompras,
)
from app.modules.farmacias.models import Farmacia
from app.modules.fidelidade import service as fidelidade
from app.modules.fidelidade.models import MovimentoPontos
from app.modules.financeiro.service import credito_do_cliente
from app.modules.vendas.models import Venda, VendaItem
from app.shared.datas import FUSO, hoje
from app.shared.erros import Conflito, NaoEncontrado

DIAS_SUMIDO = 60


def _ultima_compra():
    return (
        select(Venda.cliente_id, func.max(Venda.finalizada_em).label("ultima"))
        .where(Venda.cliente_id.is_not(None), Venda.status == "finalizada")
        .group_by(Venda.cliente_id)
        .subquery()
    )


def listar(
    db: Session, busca: str | None, pagina: int, por_pagina: int, incluir_inativos: bool, filtro_extra: str | None = None
) -> tuple[list[ClienteLista], int]:
    filtro = select(Cliente)
    ordem = [Cliente.nome]
    if not incluir_inativos:
        filtro = filtro.where(Cliente.ativo.is_(True))
    if filtro_extra == "aniversariantes":
        filtro = filtro.where(extract("month", Cliente.data_nascimento) == hoje().month)
        ordem = [extract("day", Cliente.data_nascimento), Cliente.nome]
    elif filtro_extra == "sumidos":
        # Já compraram, mas não voltam há um tempo: bons para uma ligação ou oferta.
        ultima = _ultima_compra()
        limite = datetime.now(FUSO) - timedelta(days=DIAS_SUMIDO)
        filtro = filtro.join(ultima, ultima.c.cliente_id == Cliente.id).where(ultima.c.ultima < limite)
        ordem = [ultima.c.ultima.desc()]
    if busca and busca.strip():
        termo = busca.strip()
        digitos = "".join(c for c in termo if c.isdigit())
        condicoes = [Cliente.nome.ilike(f"%{termo}%")]
        if digitos:
            condicoes += [Cliente.cpf == digitos, Cliente.telefone.like(f"%{digitos}%")]
        filtro = filtro.where(or_(*condicoes))
    total = db.scalar(select(func.count()).select_from(filtro.subquery()))
    clientes = db.scalars(filtro.order_by(*ordem).offset((pagina - 1) * por_pagina).limit(por_pagina)).all()

    ids = [c.id for c in clientes]
    pontos = dict(
        db.execute(
            select(MovimentoPontos.cliente_id, func.sum(MovimentoPontos.pontos))
            .where(MovimentoPontos.cliente_id.in_(ids))
            .group_by(MovimentoPontos.cliente_id)
        ).all()
    ) if ids else {}
    ultimas = dict(
        db.execute(
            select(Venda.cliente_id, func.max(Venda.finalizada_em))
            .where(Venda.cliente_id.in_(ids), Venda.status == "finalizada")
            .group_by(Venda.cliente_id)
        ).all()
    ) if ids else {}
    itens = [
        ClienteLista.model_validate(
            {**ClienteSaida.model_validate(c).model_dump(), "pontos": pontos.get(c.id, 0), "ultima_compra": ultimas.get(c.id)}
        )
        for c in clientes
    ]
    return itens, total


def obter(db: Session, cliente_id: UUID) -> Cliente:
    cliente = db.get(Cliente, cliente_id)
    if cliente is None:
        raise NaoEncontrado("Cliente não encontrado")
    return cliente


def _registrar_consentimento(cliente: Cliente, aceita: bool) -> None:
    # Guarda quando o cliente autorizou; ao retirar a autorização, o registro é limpo.
    if aceita and not cliente.aceita_ofertas:
        cliente.consentimento_em = datetime.now(timezone.utc)
    if not aceita:
        cliente.consentimento_em = None
    cliente.aceita_ofertas = aceita


def _salvar(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflito("Já existe cliente com este CPF")


def _conferir_convenio(db: Session, convenio_id: UUID | None) -> None:
    if convenio_id is not None and db.get(Convenio, convenio_id) is None:
        raise NaoEncontrado("Convênio não encontrado")


def criar(db: Session, dados: ClienteCriar) -> Cliente:
    _conferir_convenio(db, dados.convenio_id)
    cliente = Cliente(**dados.model_dump(exclude={"aceita_ofertas"}), aceita_ofertas=False)
    _registrar_consentimento(cliente, dados.aceita_ofertas)
    db.add(cliente)
    _salvar(db)
    return cliente


def atualizar(db: Session, cliente_id: UUID, dados: ClienteAtualizar) -> Cliente:
    cliente = obter(db, cliente_id)
    alteracoes = dados.model_dump(exclude_unset=True)
    _conferir_convenio(db, alteracoes.get("convenio_id"))
    aceita = alteracoes.pop("aceita_ofertas", None)
    if aceita is not None:
        _registrar_consentimento(cliente, aceita)
    for campo, valor in alteracoes.items():
        if campo in ("nome", "ativo") and valor is None:
            continue
        setattr(cliente, campo, valor)
    _salvar(db)
    db.refresh(cliente)
    return cliente


# --- Ficha ---

def ficha(db: Session, farmacia_id: UUID, cliente_id: UUID) -> FichaCliente:
    cliente = obter(db, cliente_id)
    farmacia = db.get(Farmacia, farmacia_id)
    finalizadas = select(Venda.id).where(Venda.cliente_id == cliente_id, Venda.status == "finalizada")

    quantidade, total, primeira, ultima = db.execute(
        select(func.count(), func.coalesce(func.sum(Venda.total), 0), func.min(Venda.finalizada_em),
               func.max(Venda.finalizada_em))
        .where(Venda.id.in_(finalizadas))
    ).one()
    compras = ResumoCompras(
        quantidade=quantidade,
        total=total,
        ticket_medio=(total / quantidade).quantize(Decimal("0.01")) if quantidade else Decimal(0),
        primeira=primeira,
        ultima=ultima,
        dias_sem_comprar=(hoje() - ultima.astimezone(FUSO).date()).days if ultima else None,
    )

    frequentes = db.execute(
        select(
            VendaItem.produto_id,
            func.max(VendaItem.descricao),
            func.count(func.distinct(VendaItem.venda_id)).label("vezes"),
            func.sum(VendaItem.quantidade),
            func.max(Venda.finalizada_em),
        )
        .join(Venda, Venda.id == VendaItem.venda_id)
        .where(VendaItem.venda_id.in_(finalizadas))
        .group_by(VendaItem.produto_id)
        .order_by(func.count(func.distinct(VendaItem.venda_id)).desc(), func.max(Venda.finalizada_em).desc())
        .limit(8)
    ).all()

    vendas = db.scalars(
        select(Venda).where(Venda.cliente_id == cliente_id).order_by(Venda.finalizada_em.desc()).limit(20)
    ).all()
    credito = credito_do_cliente(db, cliente_id)
    return FichaCliente(
        cliente=ClienteSaida.model_validate(cliente),
        compras=compras,
        pontos=fidelidade.pontos(db, farmacia, cliente_id, movimentos=30),
        fiado_em_aberto=credito.em_aberto,
        fiado_vencido=credito.vencido,
        produtos_frequentes=[
            ProdutoFrequente(produto_id=p, descricao=d, vezes=v, quantidade=q, ultima=u)
            for p, d, v, q, u in frequentes
        ],
        ultimas_compras=[
            CompraCliente(
                id=v.id,
                numero=v.numero,
                finalizada_em=v.finalizada_em,
                status=v.status,
                total=v.total,
                itens=len(v.itens),
                formas=sorted({p.forma for p in v.pagamentos}),
                pontos_ganhos=v.pontos_ganhos,
                pontos_resgatados=v.pontos_resgatados,
            )
            for v in vendas
        ],
    )
