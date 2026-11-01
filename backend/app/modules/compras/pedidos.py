"""Pedidos de compra: o que foi pedido a cada fornecedor e quanto já chegou pelas notas."""

import re
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import TokenDados
from app.modules.auth.models import Usuario
from app.modules.compras.models import NotaEntrada, PedidoCompra, PedidoCompraItem
from app.modules.compras.schemas import (
    ConferenciaPedido,
    ItemPedidoSaida,
    LinhaConferencia,
    NotaResumo,
    PedidoCompraCriar,
    PedidoCompraResumo,
    PedidoCompraSaida,
)
from app.modules.estoque.service import loja_ou_matriz
from app.modules.farmacias.models import Farmacia
from app.modules.fornecedores.models import Fornecedor
from app.modules.lojas.models import Loja
from app.modules.produtos.models import Produto
from app.shared.erros import Conflito, ErroDeNegocio, NaoEncontrado

ABERTOS = ("aberto", "enviado", "parcial")
CENTAVO = Decimal("0.01")


def _agora() -> datetime:
    return datetime.now(UTC)


def whatsapp(telefone: str | None) -> str | None:
    """Número no formato do wa.me: só dígitos, com o 55 do Brasil."""
    digitos = re.sub(r"\D", "", telefone or "")
    if len(digitos) in (10, 11):
        digitos = "55" + digitos
    return digitos if len(digitos) in (12, 13) else None


def nome_fornecedor(fornecedor: Fornecedor) -> str:
    return fornecedor.nome_fantasia or fornecedor.razao_social


def nome_produto(produto: Produto) -> str:
    return f"{produto.nome} {produto.apresentacao}" if produto.apresentacao else produto.nome


def _qtd(valor: Decimal) -> str:
    return f"{Decimal(valor).normalize():f}".replace(".", ",")


def texto_do_pedido(
    farmacia: str, loja: str | None, contato: str | None, data: datetime, linhas: list[tuple[Decimal, str, str | None]],
    numero: int | None = None,
) -> str:
    """Mensagem para o fornecedor. `linhas` = (quantidade, nome, ean)."""
    cabecalho = f"Olá{', ' + contato if contato else ''}! Pedido de compra"
    cabecalho += f" nº {numero}" if numero else ""
    cabecalho += f" da {farmacia}" + (f" ({loja})" if loja else "") + f", {data:%d/%m/%Y}:"
    corpo = [f"- {_qtd(q)} x {nome}" + (f" (EAN {ean})" if ean else "") for q, nome, ean in linhas]
    return "\n".join([cabecalho, "", *corpo, "", "Por favor, confirme preço e prazo de entrega. Obrigado!"])


def criar(db: Session, usuario: TokenDados, dados: PedidoCompraCriar) -> PedidoCompra:
    fornecedor = db.get(Fornecedor, dados.fornecedor_id)
    if fornecedor is None:
        raise NaoEncontrado("Fornecedor não encontrado")
    loja = loja_ou_matriz(db, dados.loja_id)
    ids = [i.produto_id for i in dados.itens]
    if len(set(ids)) != len(ids):
        raise ErroDeNegocio("O mesmo produto aparece duas vezes no pedido: junte as quantidades")
    achados = set(db.scalars(select(Produto.id).where(Produto.id.in_(ids))))
    if faltam := [str(i) for i in ids if i not in achados]:
        raise NaoEncontrado(f"Produto não encontrado: {', '.join(faltam)}")
    pedido = PedidoCompra(
        numero=db.scalar(select(func.coalesce(func.max(PedidoCompra.numero), 0) + 1)),
        loja_id=loja.id,
        fornecedor_id=fornecedor.id,
        usuario_id=usuario.usuario_id,
        observacao=dados.observacao,
        itens=[
            PedidoCompraItem(produto_id=i.produto_id, quantidade=i.quantidade, custo_estimado=i.custo_estimado)
            for i in dados.itens
        ],
    )
    db.add(pedido)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflito("Outro pedido foi salvo ao mesmo tempo. Tente de novo.")
    return pedido


def obter(db: Session, pedido_id: UUID, travar: bool = False) -> PedidoCompra:
    filtro = select(PedidoCompra).where(PedidoCompra.id == pedido_id)
    if travar:
        filtro = filtro.with_for_update(of=PedidoCompra)
    pedido = db.scalar(filtro)
    if pedido is None:
        raise NaoEncontrado("Pedido de compra não encontrado")
    return pedido


def _total(pedido: PedidoCompra) -> Decimal:
    return sum(((i.custo_estimado or 0) * i.quantidade for i in pedido.itens), Decimal(0)).quantize(CENTAVO)


def _resumo(pedido: PedidoCompra, lojas: dict[UUID, str]) -> dict:
    return {
        "id": pedido.id,
        "numero": pedido.numero,
        "loja_id": pedido.loja_id,
        "loja_nome": lojas.get(pedido.loja_id, ""),
        "fornecedor_id": pedido.fornecedor_id,
        "fornecedor_nome": nome_fornecedor(pedido.fornecedor),
        "status": pedido.status,
        "criado_em": pedido.criado_em,
        "enviado_em": pedido.enviado_em,
        "quantidade_itens": len(pedido.itens),
        "total_estimado": _total(pedido),
    }


def _lojas(db: Session) -> dict[UUID, str]:
    return dict(db.execute(select(Loja.id, Loja.nome)).all())


def listar(db: Session, status: str | None, fornecedor_id: UUID | None) -> list[PedidoCompraResumo]:
    filtro = select(PedidoCompra)
    if status == "abertos":
        filtro = filtro.where(PedidoCompra.status.in_(ABERTOS))
    elif status:
        filtro = filtro.where(PedidoCompra.status == status)
    if fornecedor_id:
        filtro = filtro.where(PedidoCompra.fornecedor_id == fornecedor_id)
    pedidos = db.scalars(filtro.order_by(PedidoCompra.numero.desc()).limit(200)).all()
    lojas = _lojas(db)
    return [PedidoCompraResumo(**_resumo(p, lojas)) for p in pedidos]


def saida(db: Session, pedido: PedidoCompra) -> PedidoCompraSaida:
    from app.modules.compras.service import _resumo as resumo_nota

    produtos = {p.id: p for p in db.scalars(select(Produto).where(Produto.id.in_([i.produto_id for i in pedido.itens])))}
    lojas = _lojas(db)
    farmacia = db.get(Farmacia, pedido.farmacia_id)
    criado_por = db.get(Usuario, pedido.usuario_id)
    itens = [
        ItemPedidoSaida(
            produto_id=i.produto_id,
            nome=nome_produto(produtos[i.produto_id]),
            ean=produtos[i.produto_id].ean,
            quantidade=i.quantidade,
            recebido=i.recebido,
            falta_receber=max(i.quantidade - i.recebido, Decimal(0)),
            custo_estimado=i.custo_estimado,
        )
        for i in pedido.itens
    ]
    notas = db.scalars(
        select(NotaEntrada).where(NotaEntrada.pedido_id == pedido.id, NotaEntrada.status != "cancelada")
        .order_by(NotaEntrada.criado_em)
    ).all()
    texto = texto_do_pedido(
        farmacia.nome_fantasia or farmacia.razao_social if farmacia else "farmácia",
        lojas.get(pedido.loja_id),
        pedido.fornecedor.contato,
        pedido.criado_em,
        [(i.quantidade, i.nome, i.ean) for i in itens],
        pedido.numero,
    )
    return PedidoCompraSaida(
        **_resumo(pedido, lojas),
        observacao=pedido.observacao,
        criado_por=criado_por.nome if criado_por else "",
        itens=itens,
        notas=[NotaResumo(**resumo_nota(n)) for n in notas],
        texto=texto,
        whatsapp=whatsapp(pedido.fornecedor.telefone),
        email=pedido.fornecedor.email,
    )


def marcar_enviado(db: Session, pedido_id: UUID) -> PedidoCompra:
    pedido = obter(db, pedido_id, travar=True)
    if pedido.status not in ("aberto", "enviado"):
        raise Conflito(f"Este pedido já está {pedido.status}")
    pedido.status = "enviado"
    pedido.enviado_em = pedido.enviado_em or _agora()
    db.commit()
    return pedido


def cancelar(db: Session, pedido_id: UUID) -> PedidoCompra:
    pedido = obter(db, pedido_id, travar=True)
    if pedido.status not in ABERTOS:
        raise Conflito(f"Este pedido já está {pedido.status}")
    if any(i.recebido > 0 for i in pedido.itens):
        raise ErroDeNegocio("Parte deste pedido já chegou. Ele fica como recebido em parte.")
    pedido.status = "cancelado"
    # Notas ainda não confirmadas deixam de apontar para ele.
    for nota in db.scalars(select(NotaEntrada).where(NotaEntrada.pedido_id == pedido.id,
                                                     NotaEntrada.status == "pendente")):
        nota.pedido_id = None
    db.commit()
    return pedido


# --- Ligação com a nota que chega ---

def pedido_para_nota(db: Session, nota: NotaEntrada) -> UUID | None:
    """O pedido em aberto mais antigo do mesmo fornecedor para a mesma loja."""
    return db.scalar(
        select(PedidoCompra.id)
        .where(PedidoCompra.fornecedor_id == nota.fornecedor_id, PedidoCompra.loja_id == nota.loja_id,
               PedidoCompra.status.in_(ABERTOS))
        .order_by(PedidoCompra.numero)
        .limit(1)
    )


def ligar_nota(db: Session, nota: NotaEntrada, pedido_id: UUID | None) -> None:
    if pedido_id is not None:
        pedido = obter(db, pedido_id)
        if pedido.fornecedor_id != nota.fornecedor_id:
            raise ErroDeNegocio("Este pedido é de outro fornecedor")
        if pedido.status not in ABERTOS:
            raise ErroDeNegocio(f"Este pedido já está {pedido.status}")
    nota.pedido_id = pedido_id


def _unidades_da_nota(nota: NotaEntrada) -> dict[UUID, Decimal]:
    """Quanto de cada produto veio, em unidades de venda (a nota pode vir em caixas)."""
    total: dict[UUID, Decimal] = defaultdict(Decimal)
    for item in nota.itens:
        if item.produto_id:
            total[item.produto_id] += item.quantidade * item.fator
    return total


def conferencia(db: Session, nota: NotaEntrada) -> ConferenciaPedido | None:
    if nota.pedido_id is None:
        return None
    pedido = db.get(PedidoCompra, nota.pedido_id)
    if pedido is None:
        return None
    veio = _unidades_da_nota(nota)
    ja_confirmada = nota.status == "confirmada"
    ids = {i.produto_id for i in pedido.itens} | set(veio)
    produtos = {p.id: p for p in db.scalars(select(Produto).where(Produto.id.in_(ids)))}
    linhas = []
    for item in pedido.itens:
        # Depois de confirmada, o recebido já inclui esta nota: o que faltava era antes dela.
        faltava = item.quantidade - item.recebido + (veio.get(item.produto_id, 0) if ja_confirmada else 0)
        faltava = max(faltava, Decimal(0))
        na_nota = veio.get(item.produto_id, Decimal(0))
        if na_nota == 0:
            situacao = "nao_veio" if faltava > 0 else "ok"
        else:
            situacao = "ok" if na_nota == faltava else "faltou" if na_nota < faltava else "sobrou"
        linhas.append(LinhaConferencia(produto_id=item.produto_id, nome=nome_produto(produtos[item.produto_id]),
                                       pedido=faltava, na_nota=na_nota, situacao=situacao))
    pedidos = {i.produto_id for i in pedido.itens}
    for produto_id, quantidade in veio.items():
        if produto_id not in pedidos:
            linhas.append(LinhaConferencia(produto_id=produto_id, nome=nome_produto(produtos[produto_id]),
                                           pedido=Decimal(0), na_nota=quantidade, situacao="fora_do_pedido"))
    return ConferenciaPedido(
        pedido_id=pedido.id, numero=pedido.numero, status=pedido.status, linhas=linhas,
        tudo_certo=all(linha.situacao == "ok" for linha in linhas),
    )


def dar_baixa(db: Session, nota: NotaEntrada) -> None:
    """Na confirmação da nota: soma o que chegou no pedido e atualiza a situação dele."""
    if nota.pedido_id is None:
        return
    pedido = obter(db, nota.pedido_id, travar=True)
    if pedido.status not in ABERTOS:
        return
    veio = _unidades_da_nota(nota)
    for item in pedido.itens:
        item.recebido += veio.get(item.produto_id, Decimal(0))
    pedido.status = "recebido" if all(i.recebido >= i.quantidade for i in pedido.itens) else "parcial"
