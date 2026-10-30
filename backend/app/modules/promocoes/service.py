"""Promoções: cadastro, desconto de cada item no caixa e o resultado de cada promoção."""

from datetime import date, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import TokenDados
from app.modules.lojas.service import obter_loja
from app.modules.produtos.models import Produto
from app.modules.promocoes.models import Promocao, PromocaoProduto
from app.modules.promocoes.schemas import (
    ProdutoDaPromocao,
    PromocaoAtualizar,
    PromocaoCriar,
    PromocaoPDV,
    PromocaoSaida,
    Resultado,
)
from app.modules.vendas.models import Venda, VendaItem
from app.shared.datas import hoje
from app.shared.erros import ErroDeNegocio, NaoEncontrado

CENTAVO = Decimal("0.01")
ZERO = Decimal(0)


# --- Regra do desconto (o PDV faz a mesma conta em carrinho.ts) ---

def desconto(promocao: Promocao, preco: Decimal, quantidade: Decimal) -> Decimal:
    """Quanto a promoção tira do item. Nunca passa do valor do item."""
    bruto = (preco * quantidade).quantize(CENTAVO, ROUND_HALF_UP)
    if promocao.tipo == "percentual":
        valor = (bruto * promocao.percentual / 100).quantize(CENTAVO, ROUND_HALF_UP)
    elif promocao.tipo == "preco_fixo":
        valor = (max(preco - promocao.preco, ZERO) * quantidade).quantize(CENTAVO, ROUND_HALF_UP)
    else:
        # Leve 3, pague 2: a cada 3 unidades inteiras, uma sai de graça.
        gratis = (quantidade / promocao.leve).to_integral_value(ROUND_DOWN) * (promocao.leve - promocao.pague)
        valor = (preco * gratis).quantize(CENTAVO, ROUND_HALF_UP)
    return min(valor, bruto)


def resumo(promocao: Promocao) -> str:
    if promocao.tipo == "percentual":
        return f"{promocao.percentual.normalize():f}% de desconto".replace(".", ",")
    if promocao.tipo == "preco_fixo":
        return f"Por R$ {promocao.preco:.2f}".replace(".", ",")
    return f"Leve {promocao.leve}, pague {promocao.pague}"


def _vigentes(db: Session, loja_id: UUID | None, dia: date):
    filtro = select(Promocao).where(
        Promocao.ativa.is_(True),
        Promocao.inicio <= dia,
        or_(Promocao.fim.is_(None), Promocao.fim >= dia),
    )
    if loja_id is not None:
        filtro = filtro.where(or_(Promocao.loja_id.is_(None), Promocao.loja_id == loja_id))
    return filtro


def vigentes_por_produto(db: Session, produto_ids: list[UUID], loja_id: UUID | None) -> dict[UUID, list[Promocao]]:
    if not produto_ids:
        return {}
    vigentes = _vigentes(db, loja_id, hoje()).subquery()
    linhas = db.execute(
        select(PromocaoProduto.produto_id, Promocao)
        .join(Promocao, Promocao.id == PromocaoProduto.promocao_id)
        .where(PromocaoProduto.produto_id.in_(produto_ids), Promocao.id.in_(select(vigentes.c.id)))
    ).all()
    resultado: dict[UUID, list[Promocao]] = {}
    for produto_id, promocao in linhas:
        resultado.setdefault(produto_id, []).append(promocao)
    return resultado


def melhor(
    promocoes: list[Promocao], preco: Decimal, quantidade: Decimal, com_cliente: bool
) -> tuple[Promocao | None, Decimal]:
    """A promoção que dá mais desconto neste item. Não acumula promoções."""
    escolhida, maior = None, ZERO
    for promocao in promocoes:
        if promocao.so_clientes and not com_cliente:
            continue
        valor = desconto(promocao, preco, quantidade)
        if valor > maior:
            escolhida, maior = promocao, valor
    return escolhida, maior


def para_pdv(promocoes: list[Promocao]) -> list[PromocaoPDV]:
    return [
        PromocaoPDV(
            id=p.id, nome=p.nome, tipo=p.tipo, percentual=p.percentual, preco=p.preco, leve=p.leve,
            pague=p.pague, so_clientes=p.so_clientes, resumo=resumo(p),
        )
        for p in promocoes
    ]


# --- Cadastro ---

def _situacao(promocao: Promocao) -> str:
    dia = hoje()
    if not promocao.ativa:
        return "pausada"
    if promocao.inicio > dia:
        return "agendada"
    if promocao.fim is not None and promocao.fim < dia:
        return "encerrada"
    return "vigente"


def _resultados(db: Session, ids: list[UUID]) -> dict[UUID, Resultado]:
    if not ids:
        return {}
    linhas = db.execute(
        select(
            VendaItem.promocao_id,
            func.count(func.distinct(VendaItem.venda_id)),
            func.coalesce(func.sum(VendaItem.quantidade), 0),
            func.coalesce(func.sum(VendaItem.total), 0),
            func.coalesce(func.sum(VendaItem.desconto_promocao), 0),
        )
        .join(Venda, Venda.id == VendaItem.venda_id)
        .where(VendaItem.promocao_id.in_(ids), Venda.status == "finalizada")
        .group_by(VendaItem.promocao_id)
    ).all()
    return {
        i: Resultado(vendas=v, unidades=u, faturado=f, desconto=d) for i, v, u, f, d in linhas
    }


def saidas(db: Session, promocoes: list[Promocao]) -> list[PromocaoSaida]:
    produto_ids = {pp.produto_id for p in promocoes for pp in p.produtos}
    produtos = (
        {p.id: p for p in db.scalars(select(Produto).where(Produto.id.in_(produto_ids)))} if produto_ids else {}
    )
    resultados = _resultados(db, [p.id for p in promocoes])
    vazio = Resultado(vendas=0, unidades=ZERO, faturado=ZERO, desconto=ZERO)
    saida = []
    for promocao in promocoes:
        itens = []
        for pp in promocao.produtos:
            produto = produtos[pp.produto_id]
            preco_promocional = None
            if promocao.tipo != "leve_pague":
                preco_promocional = produto.preco_venda - desconto(promocao, produto.preco_venda, Decimal(1))
            nome = produto.nome if not produto.apresentacao else f"{produto.nome} {produto.apresentacao}"
            itens.append(ProdutoDaPromocao(id=produto.id, nome=nome, preco_venda=produto.preco_venda,
                                           preco_promocional=preco_promocional))
        saida.append(
            PromocaoSaida.model_validate(
                {
                    **{c: getattr(promocao, c) for c in PromocaoSaida.model_fields
                       if c not in ("situacao", "resumo", "produtos", "resultado")},
                    "situacao": _situacao(promocao),
                    "resumo": resumo(promocao),
                    "produtos": sorted(itens, key=lambda i: i.nome),
                    "resultado": resultados.get(promocao.id, vazio),
                }
            )
        )
    return saida


def listar(db: Session, situacao: str | None) -> list[PromocaoSaida]:
    dia = hoje()
    filtro = select(Promocao)
    if situacao == "vigente":
        filtro = _vigentes(db, None, dia)
    elif situacao == "agendada":
        filtro = filtro.where(Promocao.ativa.is_(True), Promocao.inicio > dia)
    elif situacao == "encerrada":
        filtro = filtro.where(or_(Promocao.ativa.is_(False), Promocao.fim < dia))
    promocoes = db.scalars(filtro.order_by(Promocao.inicio.desc(), Promocao.nome).limit(200)).all()
    return saidas(db, list(promocoes))


def obter(db: Session, promocao_id: UUID) -> Promocao:
    promocao = db.get(Promocao, promocao_id)
    if promocao is None:
        raise NaoEncontrado("Promoção não encontrada")
    return promocao


def _aplicar(db: Session, promocao: Promocao, dados: PromocaoCriar | PromocaoAtualizar) -> None:
    if dados.loja_id is not None:
        obter_loja(db, dados.loja_id)
    ids = list(dict.fromkeys(dados.produto_ids))
    produtos = db.scalars(select(Produto).where(Produto.id.in_(ids))).all()
    if len(produtos) != len(ids):
        raise NaoEncontrado("Produto não encontrado")
    if dados.tipo == "preco_fixo":
        caros = [p.nome for p in produtos if dados.preco >= p.preco_venda]
        if caros:
            raise ErroDeNegocio(f"O preço da promoção precisa ser menor que o preço normal de: {', '.join(caros)}")

    for campo in ("nome", "tipo", "inicio", "fim", "so_clientes", "loja_id"):
        setattr(promocao, campo, getattr(dados, campo))
    # Guarda só o campo da regra escolhida.
    promocao.percentual = dados.percentual if dados.tipo == "percentual" else None
    promocao.preco = dados.preco if dados.tipo == "preco_fixo" else None
    promocao.leve = dados.leve if dados.tipo == "leve_pague" else None
    promocao.pague = dados.pague if dados.tipo == "leve_pague" else None

    atuais = {pp.produto_id: pp for pp in promocao.produtos}
    promocao.produtos = [atuais.get(i) or PromocaoProduto(produto_id=i) for i in ids]


def criar(db: Session, usuario: TokenDados, dados: PromocaoCriar) -> PromocaoSaida:
    promocao = Promocao(usuario_id=usuario.usuario_id, ativa=True)
    _aplicar(db, promocao, dados)
    db.add(promocao)
    db.commit()
    return saidas(db, [promocao])[0]


def atualizar(db: Session, promocao_id: UUID, dados: PromocaoAtualizar) -> PromocaoSaida:
    promocao = obter(db, promocao_id)
    _aplicar(db, promocao, dados)
    promocao.ativa = dados.ativa
    db.commit()
    db.refresh(promocao)
    return saidas(db, [promocao])[0]


def encerrar(db: Session, promocao_id: UUID) -> PromocaoSaida:
    """Para de valer já. As vendas já feitas continuam com o desconto que tiveram."""
    promocao = obter(db, promocao_id)
    ontem = hoje() - timedelta(days=1)
    if promocao.inicio > ontem:
        promocao.ativa = False  # nem chegou a valer um dia inteiro: só pausa
    else:
        promocao.fim = min(promocao.fim or ontem, ontem)
    db.commit()
    db.refresh(promocao)
    return saidas(db, [promocao])[0]
