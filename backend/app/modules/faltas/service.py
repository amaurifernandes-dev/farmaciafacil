"""Lista de faltas e encomendas: anota o que faltou, mostra quando chegou e quem avisar."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import String, case, cast, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.security import TokenDados
from app.modules.auth.models import Usuario
from app.modules.clientes.models import Cliente
from app.modules.estoque.models import Lote
from app.modules.estoque.service import _lotes_vendaveis, loja_ou_matriz
from app.modules.faltas.models import PENDENTES, Falta
from app.modules.faltas.schemas import (
    FaltaCriar,
    FaltaSaida,
    ListaFaltas,
    MaisPedido,
    ResumoFaltas,
    Situacao,
)
from app.modules.lojas.models import Loja, Terminal
from app.modules.produtos.models import Produto
from app.modules.vendas.models import Venda
from app.shared.erros import ErroDeNegocio, NaoEncontrado


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _texto(valor: str | None) -> str | None:
    valor = (valor or "").strip()
    return valor or None


def _nome_produto(produto: Produto) -> str:
    return produto.nome if not produto.apresentacao else f"{produto.nome} {produto.apresentacao}"


def _saldos(db: Session, faltas: list[Falta]) -> dict[tuple[UUID, UUID], Decimal]:
    """Saldo vendável de cada produto em cada loja que aparece na lista."""
    produtos = {f.produto_id for f in faltas if f.produto_id is not None}
    if not produtos:
        return {}
    vendaveis = _lotes_vendaveis().where(Lote.produto_id.in_(produtos)).subquery()
    return {
        (loja_id, produto_id): saldo
        for loja_id, produto_id, saldo in db.execute(
            select(vendaveis.c.loja_id, vendaveis.c.produto_id, func.sum(vendaveis.c.quantidade))
            .group_by(vendaveis.c.loja_id, vendaveis.c.produto_id)
        )
    }


def _chegou(falta: Falta, saldos: dict) -> bool:
    if falta.status != "aberta" or falta.produto_id is None:
        return False
    return saldos.get((falta.loja_id, falta.produto_id), Decimal(0)) >= falta.quantidade


def saidas(db: Session, faltas: list[Falta]) -> list[FaltaSaida]:
    saldos = _saldos(db, faltas)
    clientes = {
        c.id: c
        for c in db.scalars(select(Cliente).where(Cliente.id.in_({f.cliente_id for f in faltas if f.cliente_id})))
    }
    lojas = dict(db.execute(select(Loja.id, Loja.nome)).all())
    usuarios = dict(
        db.execute(select(Usuario.id, Usuario.nome).where(Usuario.id.in_({f.usuario_id for f in faltas}))).all()
    )
    resultado = []
    for falta in faltas:
        cliente = clientes.get(falta.cliente_id)
        resultado.append(
            FaltaSaida(
                id=falta.id,
                loja_id=falta.loja_id,
                loja_nome=lojas.get(falta.loja_id, ""),
                produto_id=falta.produto_id,
                descricao=falta.descricao,
                quantidade=falta.quantidade,
                cliente_id=falta.cliente_id,
                nome=falta.contato_nome or (cliente.nome if cliente else None),
                telefone=falta.contato_telefone or (cliente.telefone if cliente else None),
                observacao=falta.observacao,
                status=falta.status,
                origem=falta.origem,
                encomenda=falta.status != "registrada",
                saldo=saldos.get((falta.loja_id, falta.produto_id), Decimal(0)) if falta.produto_id else None,
                chegou=_chegou(falta, saldos),
                usuario_nome=usuarios.get(falta.usuario_id, ""),
                criado_em=falta.criado_em,
                avisado_em=falta.avisado_em,
                finalizada_em=falta.finalizada_em,
            )
        )
    return resultado


def _resumo(db: Session, loja_id: UUID | None) -> ResumoFaltas:
    def da_loja(filtro):
        return filtro.where(Falta.loja_id == loja_id) if loja_id is not None else filtro

    abertas = list(db.scalars(da_loja(select(Falta).where(Falta.status == "aberta"))))
    saldos = _saldos(db, abertas)
    avisados = db.scalar(da_loja(select(func.count()).select_from(Falta).where(Falta.status == "avisado")))

    desde = _agora() - timedelta(days=30)
    recentes = da_loja(select(Falta).where(Falta.status != "cancelada", Falta.criado_em >= desde)).subquery()
    # O mesmo produto junta mesmo que o nome tenha mudado; o que não é cadastrado junta pelo texto.
    chave = func.coalesce(cast(recentes.c.produto_id, String), func.lower(func.trim(recentes.c.descricao)))
    mais = db.execute(
        select(
            func.min(cast(recentes.c.produto_id, String)),
            func.min(recentes.c.descricao),
            func.count(),
            func.sum(recentes.c.quantidade),
        )
        .group_by(chave)
        .order_by(func.count().desc(), func.sum(recentes.c.quantidade).desc(), func.min(recentes.c.descricao))
        .limit(5)
    ).all()
    return ResumoFaltas(
        encomendas=len(abertas),
        chegaram=sum(1 for f in abertas if _chegou(f, saldos)),
        avisados=avisados,
        faltas_30_dias=db.scalar(select(func.count()).select_from(recentes)),
        mais_pedidos=[
            MaisPedido(produto_id=UUID(p) if p else None, descricao=d, vezes=v, quantidade=q) for p, d, v, q in mais
        ],
    )


def quantas_chegaram(db: Session) -> int:
    """Para o aviso da tela inicial."""
    abertas = list(db.scalars(select(Falta).where(Falta.status == "aberta")))
    saldos = _saldos(db, abertas)
    return sum(1 for f in abertas if _chegou(f, saldos))


def listar(db: Session, situacao: Situacao, loja_id: UUID | None, busca: str | None) -> ListaFaltas:
    filtro = select(Falta)
    if loja_id is not None:
        filtro = filtro.where(Falta.loja_id == loja_id)
    if situacao in ("encomendas", "chegaram"):
        filtro = filtro.where(Falta.status == "aberta")
    elif situacao == "avisados":
        filtro = filtro.where(Falta.status == "avisado")
    elif situacao == "faltas":
        filtro = filtro.where(Falta.status == "registrada")
    elif situacao == "encerradas":
        filtro = filtro.where(Falta.status.in_(("entregue", "cancelada")))
    busca = _texto(busca)
    if busca:
        termo = f"%{busca}%"
        filtro = filtro.outerjoin(Cliente, Cliente.id == Falta.cliente_id).where(
            or_(Falta.descricao.ilike(termo), Falta.contato_nome.ilike(termo), Cliente.nome.ilike(termo),
                Falta.contato_telefone.ilike(termo))
        )
    faltas = list(db.scalars(filtro.order_by(Falta.criado_em.desc()).limit(300)))
    itens = saidas(db, faltas)
    if situacao == "chegaram":
        itens = [i for i in itens if i.chegou]
    elif situacao == "encomendas":
        itens.sort(key=lambda i: not i.chegou)  # o que já chegou primeiro; o resto segue do mais novo
    return ListaFaltas(resumo=_resumo(db, loja_id), itens=itens)


def criar(db: Session, usuario: TokenDados, terminal: Terminal | None, dados: FaltaCriar) -> FaltaSaida:
    # No caixa, a falta é da loja do caixa.
    loja = loja_ou_matriz(db, terminal.loja_id if terminal is not None else dados.loja_id)
    descricao = _texto(dados.descricao)
    if dados.produto_id is not None:
        produto = db.get(Produto, dados.produto_id)
        if produto is None:
            raise NaoEncontrado("Produto não encontrado")
        descricao = _nome_produto(produto)
    if dados.cliente_id is not None and db.get(Cliente, dados.cliente_id) is None:
        raise NaoEncontrado("Cliente não encontrado")
    nome, telefone = _texto(dados.contato_nome), _texto(dados.contato_telefone)
    falta = Falta(
        loja_id=loja.id,
        produto_id=dados.produto_id,
        descricao=descricao,
        quantidade=dados.quantidade,
        cliente_id=dados.cliente_id,
        contato_nome=nome,
        contato_telefone=telefone,
        observacao=_texto(dados.observacao),
        # Com alguém para avisar, vira encomenda.
        status="aberta" if dados.cliente_id or nome or telefone else "registrada",
        origem=dados.origem,
        usuario_id=usuario.usuario_id,
    )
    db.add(falta)
    db.commit()
    db.refresh(falta)
    return saidas(db, [falta])[0]


def _obter(db: Session, falta_id: UUID) -> Falta:
    falta = db.get(Falta, falta_id)
    if falta is None:
        raise NaoEncontrado("Falta não encontrada")
    return falta


def avisar(db: Session, falta_id: UUID) -> FaltaSaida:
    falta = _obter(db, falta_id)
    if falta.status == "registrada":
        raise ErroDeNegocio("Esta falta não tem ninguém para avisar")
    if falta.status not in PENDENTES:
        raise ErroDeNegocio("Esta encomenda já foi encerrada")
    falta.status = "avisado"
    falta.avisado_em = _agora()
    db.commit()
    return saidas(db, [falta])[0]


def entregar(db: Session, falta_id: UUID) -> FaltaSaida:
    falta = _obter(db, falta_id)
    if falta.status not in PENDENTES:
        raise ErroDeNegocio("Só dá para entregar uma encomenda que está esperando")
    falta.status = "entregue"
    falta.finalizada_em = _agora()
    db.commit()
    return saidas(db, [falta])[0]


def cancelar(db: Session, falta_id: UUID) -> FaltaSaida:
    falta = _obter(db, falta_id)
    if falta.status in ("entregue", "cancelada"):
        raise ErroDeNegocio("Esta falta já foi encerrada")
    falta.status = "cancelada"
    falta.finalizada_em = _agora()
    db.commit()
    return saidas(db, [falta])[0]


# --- Ligação com a venda (sem commit: faz parte da transação da venda) ---

def entregar_da_venda(db: Session, venda: Venda) -> None:
    """O cliente comprou o que tinha encomendado: a encomenda sai da lista sozinha."""
    if venda.cliente_id is None:
        return
    db.execute(
        update(Falta)
        .where(
            Falta.cliente_id == venda.cliente_id,
            Falta.status.in_(PENDENTES),
            Falta.produto_id.in_({item.produto_id for item in venda.itens}),
        )
        .values(status="entregue", finalizada_em=venda.finalizada_em, venda_id=venda.id)
    )


def estornar_da_venda(db: Session, venda: Venda) -> None:
    """Venda cancelada: a encomenda volta para a lista, como estava."""
    db.execute(
        update(Falta)
        .where(Falta.venda_id == venda.id)
        .values(
            status=case((Falta.avisado_em.isnot(None), "avisado"), else_="aberta"),
            finalizada_em=None,
            venda_id=None,
        )
    )
