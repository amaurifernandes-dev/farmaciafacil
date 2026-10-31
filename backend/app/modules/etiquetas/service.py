"""Etiquetas de gôndola: o que imprimir e o que trocar quando o preço ou a promoção muda."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import TokenDados
from app.modules.estoque.models import Lote
from app.modules.estoque.service import loja_ou_matriz
from app.modules.etiquetas.models import Etiqueta
from app.modules.etiquetas.schemas import (
    EtiquetaItem,
    Impressa,
    ListaEtiquetas,
    MarcarImpressas,
    Situacao,
)
from app.modules.produtos.models import Produto
from app.modules.promocoes.models import Promocao
from app.modules.promocoes.service import desconto, resumo, vigentes_por_produto
from app.shared.erros import NaoEncontrado

ZERO = Decimal(0)
UM = Decimal(1)


def conteudo(produto: Produto, promocoes: list[Promocao]) -> tuple[Decimal | None, str | None, object]:
    """O que vai na etiqueta além do preço: (preço de 1 unidade na promoção, texto da promoção, a promoção).

    Promoção só para cliente identificado não vai na gôndola, porque não vale para todo mundo.
    """
    para_todos = [p for p in promocoes if not p.so_clientes]
    por_unidade = [(desconto(p, produto.preco_venda, UM), p) for p in para_todos if p.tipo != "leve_pague"]
    por_unidade = [(d, p) for d, p in por_unidade if d > 0]
    if por_unidade:
        maior, promocao = max(por_unidade, key=lambda par: par[0])
        return produto.preco_venda - maior, resumo(promocao)[:120], promocao
    leve = [p for p in para_todos if p.tipo == "leve_pague"]
    if leve:
        return None, resumo(leve[0])[:120], leve[0]
    return None, None, None


def _motivo(produto: Produto, preco_promocional, promocao: str | None, impressa: Etiqueta | None) -> str | None:
    if impressa is None:
        return "nunca_impressa"
    if produto.preco_venda != impressa.preco:
        return "preco_subiu" if produto.preco_venda > impressa.preco else "preco_baixou"
    if promocao and not impressa.promocao:
        return "promocao_comecou"
    if impressa.promocao and not promocao:
        return "promocao_acabou"
    if promocao != impressa.promocao or preco_promocional != impressa.preco_promocional:
        return "promocao_mudou"
    return None


def listar(
    db: Session, loja_id: UUID | None, situacao: Situacao, busca: str | None, so_com_estoque: bool
) -> ListaEtiquetas:
    loja = loja_ou_matriz(db, loja_id)
    consulta = select(Produto).where(Produto.ativo.is_(True))
    if busca and busca.strip():
        termo = busca.strip()
        consulta = consulta.where(Produto.ean == termo if termo.isdigit() else Produto.nome.ilike(f"%{termo}%"))
    produtos = db.scalars(consulta.order_by(Produto.nome)).all()
    saldos = dict(
        db.execute(
            select(Lote.produto_id, func.sum(Lote.quantidade)).where(Lote.loja_id == loja.id).group_by(Lote.produto_id)
        ).all()
    )
    impressas = {e.produto_id: e for e in db.scalars(select(Etiqueta).where(Etiqueta.loja_id == loja.id))}
    if so_com_estoque:
        produtos = [p for p in produtos if saldos.get(p.id, ZERO) > 0 or p.id in impressas]
    promocoes = vigentes_por_produto(db, [p.id for p in produtos], loja.id)

    itens = []
    for produto in produtos:
        preco_promocional, texto, promocao = conteudo(produto, promocoes.get(produto.id, []))
        impressa = impressas.get(produto.id)
        itens.append(EtiquetaItem(
            produto_id=produto.id,
            nome=produto.nome,
            apresentacao=produto.apresentacao,
            fabricante=produto.fabricante,
            ean=produto.ean,
            unidade=produto.unidade,
            preco=produto.preco_venda,
            preco_promocional=preco_promocional,
            promocao=texto,
            promocao_fim=promocao.fim if promocao is not None else None,
            saldo=saldos.get(produto.id, ZERO),
            impressa=Impressa(
                preco=impressa.preco, preco_promocional=impressa.preco_promocional,
                promocao=impressa.promocao, impressa_em=impressa.impressa_em,
            ) if impressa else None,
            motivo=_motivo(produto, preco_promocional, texto, impressa),
        ))

    trocar = [i for i in itens if i.motivo]
    return ListaEtiquetas(
        loja_id=loja.id,
        itens=trocar if situacao == "trocar" else itens,
        para_trocar=len(trocar),
        nunca_impressas=sum(1 for i in trocar if i.motivo == "nunca_impressa"),
        preco_mudou=sum(1 for i in trocar if i.motivo in ("preco_subiu", "preco_baixou")),
        promocao=sum(1 for i in trocar if i.motivo and i.motivo.startswith("promocao")),
    )


def marcar_impressas(db: Session, usuario: TokenDados, dados: MarcarImpressas) -> int:
    """Guarda o que foi impresso agora: a partir daqui, só uma mudança de preço ou promoção pede troca."""
    loja = loja_ou_matriz(db, dados.loja_id)
    ids = set(dados.produto_ids)
    produtos = db.scalars(select(Produto).where(Produto.id.in_(ids))).all()
    if len(produtos) != len(ids):
        raise NaoEncontrado("Produto não encontrado")
    promocoes = vigentes_por_produto(db, list(ids), loja.id)
    existentes = {
        e.produto_id: e
        for e in db.scalars(select(Etiqueta).where(Etiqueta.loja_id == loja.id, Etiqueta.produto_id.in_(ids)))
    }
    agora = datetime.now(UTC)
    for produto in produtos:
        preco_promocional, texto, _ = conteudo(produto, promocoes.get(produto.id, []))
        etiqueta = existentes.get(produto.id)
        if etiqueta is None:
            etiqueta = Etiqueta(loja_id=loja.id, produto_id=produto.id)
            db.add(etiqueta)
        etiqueta.preco = produto.preco_venda
        etiqueta.preco_promocional = preco_promocional
        etiqueta.promocao = texto
        etiqueta.impressa_em = agora
        etiqueta.usuario_id = usuario.usuario_id
    db.commit()
    return len(produtos)
