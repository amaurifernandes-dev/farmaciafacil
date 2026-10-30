"""Pedidos de outros canais: a loja online da farmácia, o WhatsApp e o telefone.

O pedido não baixa estoque nem vira venda sozinho. A farmácia confirma, ele vira pré-venda
e o caixa recebe como qualquer outra (no balcão ou na volta do entregador).
"""

import secrets
from datetime import datetime, time
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import TokenDados
from app.modules.clientes.models import Cliente
from app.modules.estoque.models import Lote
from app.modules.estoque.service import _lotes_vendaveis
from app.modules.farmacias.models import Farmacia
from app.modules.lojas.models import Loja
from app.modules.lojas.service import matriz, obter_loja
from app.modules.pedidos.models import EM_ANDAMENTO, Pedido, PedidoItem
from app.modules.pedidos.schemas import (
    Catalogo,
    ItemPedidoSaida,
    ListaPedidos,
    LojaPublica,
    PedidoBalcaoCriar,
    PedidoCriar,
    PedidoPublico,
    PedidoSaida,
    ProdutoPublico,
    ResumoPedidos,
    Situacao,
)
from app.modules.produtos.models import Produto
from app.modules.promocoes.service import melhor, resumo, vigentes_por_produto
from app.modules.vendas.models import PreVenda
from app.modules.vendas.schemas import ItemPreVendaCriar, PreVendaCriar
from app.modules.vendas.service import cancelar_pre_venda, criar_pre_venda
from app.shared.datas import FUSO, hoje
from app.shared.erros import Conflito, ErroDeNegocio, NaoEncontrado

CENTAVO = Decimal("0.01")
MAXIMO_POR_ITEM = 10


def _nome(produto: Produto) -> str:
    return produto.nome if not produto.apresentacao else f"{produto.nome} {produto.apresentacao}"


def _digitos(telefone: str) -> str:
    return "".join(c for c in telefone if c.isdigit())


def _loja_do_site(db: Session, farmacia: Farmacia) -> Loja:
    if farmacia.loja_online_loja_id is not None:
        return obter_loja(db, farmacia.loja_online_loja_id)
    return matriz(db)


def _saldos(db: Session, loja_id: UUID, produto_ids: list[UUID] | None = None) -> dict[UUID, Decimal]:
    vendaveis = _lotes_vendaveis(loja_id)
    if produto_ids is not None:
        vendaveis = vendaveis.where(Lote.produto_id.in_(produto_ids))
    vendaveis = vendaveis.subquery()
    return dict(
        db.execute(
            select(vendaveis.c.produto_id, func.sum(vendaveis.c.quantidade)).group_by(vendaveis.c.produto_id)
        ).all()
    )


# --- Loja online (público) ---

def loja_publica(db: Session, farmacia: Farmacia) -> LojaPublica:
    loja = _loja_do_site(db, farmacia)
    return LojaPublica(
        nome=farmacia.nome_fantasia,
        mensagem=farmacia.loja_online_mensagem,
        whatsapp=farmacia.whatsapp,
        telefone=loja.telefone,
        endereco=loja.endereco,
        cidade=loja.cidade,
        uf=loja.uf,
        entrega=farmacia.entrega_ativa,
        entrega_minimo=farmacia.entrega_minimo,
        entrega_area=farmacia.entrega_area,
    )


def catalogo(db: Session, farmacia: Farmacia, busca: str | None, pagina: int, por_pagina: int) -> Catalogo:
    """Só o que a farmácia vende pelo site e tem na prateleira da loja do site."""
    loja = _loja_do_site(db, farmacia)
    saldos = _saldos(db, loja.id)
    filtro = select(Produto).where(
        Produto.ativo.is_(True), Produto.vende_online.is_(True), Produto.id.in_([p for p, s in saldos.items() if s >= 1])
    )
    busca = (busca or "").strip()
    if busca:
        termo = f"%{busca}%"
        filtro = filtro.where(or_(Produto.nome.ilike(termo), Produto.apresentacao.ilike(termo),
                                  Produto.fabricante.ilike(termo)))
    total = db.scalar(select(func.count()).select_from(filtro.subquery()))
    produtos = db.scalars(filtro.order_by(Produto.nome).offset((pagina - 1) * por_pagina).limit(por_pagina)).all()

    promocoes = vigentes_por_produto(db, [p.id for p in produtos], loja.id)
    resultado = []
    for produto in produtos:
        # No site o cliente não está identificado: promoção só de clube não vale.
        abertas = [p for p in promocoes.get(produto.id, []) if not p.so_clientes]
        escolhida, valor = melhor(abertas, produto.preco_venda, Decimal(1), com_cliente=False)
        leve_pague = next((p for p in abertas if p.tipo == "leve_pague"), None)
        resultado.append(
            ProdutoPublico(
                id=produto.id,
                nome=produto.nome,
                apresentacao=produto.apresentacao,
                fabricante=produto.fabricante,
                preco=produto.preco_venda,
                preco_promocional=produto.preco_venda - valor if escolhida else None,
                promocao=resumo(escolhida or leve_pague) if escolhida or leve_pague else None,
                maximo=int(min(saldos[produto.id], MAXIMO_POR_ITEM)),
            )
        )
    return Catalogo(produtos=resultado, total=total)


def _itens(db: Session, loja_id: UUID, dados: PedidoCriar, so_online: bool) -> list[PedidoItem]:
    quantidades: dict[UUID, Decimal] = {}
    for item in dados.itens:
        quantidades[item.produto_id] = quantidades.get(item.produto_id, Decimal(0)) + item.quantidade
    produtos = {p.id: p for p in db.scalars(select(Produto).where(Produto.id.in_(quantidades)))}
    saldos = _saldos(db, loja_id, list(quantidades))
    promocoes = vigentes_por_produto(db, list(quantidades), loja_id)

    itens = []
    for produto_id, quantidade in quantidades.items():
        produto = produtos.get(produto_id)
        if produto is None or not produto.ativo or (so_online and not produto.vende_online):
            raise NaoEncontrado("Um dos produtos não está mais à venda. Atualize a página")
        if so_online and quantidade != quantidade.to_integral_value():
            raise ErroDeNegocio("Peça em unidades inteiras")
        saldo = saldos.get(produto_id, Decimal(0))
        if saldo < quantidade:
            disponivel = f"só temos {saldo.normalize():f}" if saldo > 0 else "acabou"
            raise ErroDeNegocio(f"{_nome(produto)}: {disponivel}")
        # O mesmo cálculo que o PDV faz ao receber (sem cliente identificado).
        abertas = [p for p in promocoes.get(produto_id, []) if not p.so_clientes]
        _, valor = melhor(abertas, produto.preco_venda, quantidade, com_cliente=False)
        bruto = (produto.preco_venda * quantidade).quantize(CENTAVO, ROUND_HALF_UP)
        itens.append(
            PedidoItem(
                produto_id=produto_id,
                descricao=_nome(produto),
                quantidade=quantidade,
                preco_unitario=produto.preco_venda,
                desconto=valor,
                total=bruto - valor,
            )
        )
    return itens


def _criar(db: Session, farmacia: Farmacia, loja: Loja, dados: PedidoCriar, canal: str,
           usuario_id: UUID | None) -> Pedido:
    itens = _itens(db, loja.id, dados, so_online=canal == "site")
    total = sum((i.total for i in itens), Decimal(0))
    if dados.entrega:
        if canal == "site" and not farmacia.entrega_ativa:
            raise ErroDeNegocio("Esta farmácia não faz entrega pelo site. Escolha retirar na loja")
        if total < farmacia.entrega_minimo:
            raise ErroDeNegocio(f"Para entrega, o pedido mínimo é R$ {farmacia.entrega_minimo:.2f}".replace(".", ","))
    troco = dados.troco_para if dados.forma_pagamento == "dinheiro" else None
    if troco is not None and troco < total:
        raise ErroDeNegocio("O troco precisa ser para um valor maior que o total")

    # Cliente já cadastrado com o mesmo telefone: o pedido fica na ficha dele.
    telefone = _digitos(dados.telefone)
    cliente_id = db.scalar(
        select(Cliente.id).where(Cliente.ativo.is_(True), func.regexp_replace(Cliente.telefone, r"\D", "", "g") == telefone)
        .limit(1)
    )

    db.execute(text("SELECT pg_advisory_xact_lock(hashtext('pedido:' || current_setting('app.farmacia_id')))"))
    pedido = Pedido(
        numero=db.scalar(select(func.coalesce(func.max(Pedido.numero), 0) + 1)),
        codigo=secrets.token_urlsafe(9),
        canal=canal,
        loja_id=loja.id,
        cliente_id=cliente_id,
        nome=dados.nome.strip(),
        telefone=dados.telefone.strip(),
        entrega=dados.entrega,
        endereco=(dados.endereco or "").strip() or None if dados.entrega else None,
        forma_pagamento=dados.forma_pagamento,
        troco_para=troco,
        observacao=(dados.observacao or "").strip() or None,
        total=total,
        status="novo",
        usuario_id=usuario_id,
        itens=itens,
    )
    db.add(pedido)
    db.commit()
    return pedido


def criar_pelo_site(db: Session, farmacia: Farmacia, dados: PedidoCriar) -> PedidoPublico:
    return publico(_criar(db, farmacia, _loja_do_site(db, farmacia), dados, "site", None))


def publico(pedido: Pedido) -> PedidoPublico:
    return PedidoPublico(
        numero=pedido.numero,
        codigo=pedido.codigo,
        status=pedido.status,
        entrega=pedido.entrega,
        forma_pagamento=pedido.forma_pagamento,
        troco_para=pedido.troco_para,
        total=pedido.total,
        itens=[ItemPedidoSaida.model_validate(i, from_attributes=True) for i in pedido.itens],
        criado_em=pedido.criado_em,
        motivo_cancelamento=pedido.motivo_cancelamento,
    )


def acompanhar(db: Session, codigo: str) -> PedidoPublico:
    pedido = db.scalar(select(Pedido).where(Pedido.codigo == codigo))
    if pedido is None:
        raise NaoEncontrado("Pedido não encontrado")
    return publico(pedido)


# --- Na farmácia ---

def saidas(db: Session, pedidos: list[Pedido]) -> list[PedidoSaida]:
    lojas = dict(db.execute(select(Loja.id, Loja.nome)).all())
    ids = [p.pre_venda_id for p in pedidos if p.pre_venda_id]
    pre_vendas = {pv.id: pv for pv in db.scalars(select(PreVenda).where(PreVenda.id.in_(ids)))} if ids else {}
    resultado = []
    for pedido in pedidos:
        pre_venda = pre_vendas.get(pedido.pre_venda_id)
        resultado.append(
            PedidoSaida.model_validate(
                {
                    **{c: getattr(pedido, c) for c in PedidoSaida.model_fields
                       if c not in ("loja_nome", "pre_venda_numero", "pago", "itens")},
                    "loja_nome": lojas.get(pedido.loja_id, ""),
                    "pre_venda_numero": pre_venda.numero if pre_venda else None,
                    "pago": pre_venda is not None and pre_venda.status == "recebida",
                    "itens": [ItemPedidoSaida.model_validate(i, from_attributes=True) for i in pedido.itens],
                }
            )
        )
    return resultado


def _resumo(db: Session, loja_id: UUID | None) -> ResumoPedidos:
    filtro = select(Pedido.status, func.count()).group_by(Pedido.status)
    if loja_id is not None:
        filtro = filtro.where(Pedido.loja_id == loja_id)
    contagem = dict(db.execute(filtro.where(Pedido.status.in_(EM_ANDAMENTO))).all())
    inicio = datetime.combine(hoje(), time(), FUSO)
    de_hoje = select(func.count(), func.coalesce(func.sum(Pedido.total), 0)).where(
        Pedido.status == "entregue", Pedido.atualizado_em >= inicio
    )
    if loja_id is not None:
        de_hoje = de_hoje.where(Pedido.loja_id == loja_id)
    entregues, total = db.execute(de_hoje).one()
    return ResumoPedidos(
        novo=contagem.get("novo", 0),
        separando=contagem.get("separando", 0),
        pronto=contagem.get("pronto", 0),
        saiu=contagem.get("saiu", 0),
        entregues_hoje=entregues,
        total_hoje=total,
    )


def listar(db: Session, situacao: Situacao, loja_id: UUID | None) -> ListaPedidos:
    filtro = select(Pedido)
    if loja_id is not None:
        filtro = filtro.where(Pedido.loja_id == loja_id)
    if situacao == "abertos":
        filtro = filtro.where(Pedido.status.in_(EM_ANDAMENTO))
    elif situacao != "todos":
        filtro = filtro.where(Pedido.status == situacao)
    pedidos = db.scalars(filtro.order_by(Pedido.numero.desc()).limit(200)).all()
    return ListaPedidos(resumo=_resumo(db, loja_id), pedidos=saidas(db, list(pedidos)))


def quantos_novos(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Pedido).where(Pedido.status == "novo"))


def obter(db: Session, pedido_id: UUID) -> Pedido:
    pedido = db.get(Pedido, pedido_id)
    if pedido is None:
        raise NaoEncontrado("Pedido não encontrado")
    return pedido


def criar_no_balcao(db: Session, usuario: TokenDados, dados: PedidoBalcaoCriar) -> PedidoSaida:
    farmacia = db.get(Farmacia, usuario.farmacia_id)
    loja = obter_loja(db, dados.loja_id) if dados.loja_id else _loja_do_site(db, farmacia)
    try:
        pedido = _criar(db, farmacia, loja, dados, dados.canal, usuario.usuario_id)
    except IntegrityError:  # código repetido: chance desprezível, mas não vira erro 500
        db.rollback()
        raise Conflito("Tente de novo")
    return saidas(db, [pedido])[0]


def _mudar(db: Session, pedido_id: UUID, de: tuple[str, ...], para: str) -> Pedido:
    pedido = db.scalar(select(Pedido).where(Pedido.id == pedido_id).with_for_update())
    if pedido is None:
        raise NaoEncontrado("Pedido não encontrado")
    if pedido.status not in de:
        raise Conflito(f"O pedido nº {pedido.numero} está {pedido.status}")
    pedido.status = para
    return pedido


def confirmar(db: Session, usuario: TokenDados, pedido_id: UUID) -> PedidoSaida:
    """Aceita o pedido: vira pré-venda para o caixa receber, e a equipe separa os produtos."""
    pedido = _mudar(db, pedido_id, ("novo",), "separando")
    cliente = db.get(Cliente, pedido.cliente_id) if pedido.cliente_id else None
    pre_venda = criar_pre_venda(
        db,
        usuario,
        None,
        PreVendaCriar(
            itens=[ItemPreVendaCriar(produto_id=i.produto_id, quantidade=i.quantidade) for i in pedido.itens],
            cliente_cpf=cliente.cpf if cliente else None,
            loja_id=pedido.loja_id,
        ),
    )
    pedido.pre_venda_id = pre_venda.id
    db.commit()
    return saidas(db, [pedido])[0]


def pronto(db: Session, pedido_id: UUID) -> PedidoSaida:
    pedido = _mudar(db, pedido_id, ("separando",), "pronto")
    if pedido.entrega:
        raise ErroDeNegocio("Pedido para entrega: marque quando sair para entregar")
    db.commit()
    return saidas(db, [pedido])[0]


def saiu(db: Session, pedido_id: UUID) -> PedidoSaida:
    pedido = _mudar(db, pedido_id, ("separando", "pronto"), "saiu")
    if not pedido.entrega:
        raise ErroDeNegocio("Este pedido é para retirar na loja")
    db.commit()
    return saidas(db, [pedido])[0]


def entregue(db: Session, pedido_id: UUID) -> PedidoSaida:
    pedido = _mudar(db, pedido_id, ("separando", "pronto", "saiu"), "entregue")
    db.commit()
    return saidas(db, [pedido])[0]


def cancelar(db: Session, pedido_id: UUID, motivo: str) -> PedidoSaida:
    pedido = _mudar(db, pedido_id, EM_ANDAMENTO, "cancelado")
    pedido.motivo_cancelamento = motivo
    pre_venda = db.get(PreVenda, pedido.pre_venda_id) if pedido.pre_venda_id else None
    if pre_venda is not None and pre_venda.status == "recebida":
        raise ErroDeNegocio("O caixa já recebeu este pedido. Cancele a venda em Vendas")
    if pre_venda is not None and pre_venda.status == "aberta":
        cancelar_pre_venda(db, pre_venda.id)  # faz o commit do pedido junto
    else:
        db.commit()
    return saidas(db, [pedido])[0]

