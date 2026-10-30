"""Regras de estoque. Toda mudança de saldo passa por `_movimentar`."""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy import true as sa_true
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.estoque.models import LOTE_PADRAO, Lote, MovimentoEstoque
from app.modules.estoque.schemas import (
    AjusteCriar,
    Alertas,
    EntradaCriar,
    LoteComProduto,
    PerdaCriar,
    ProdutoAbaixoMinimo,
    SaldoProduto,
    TransferenciaCriar,
)
from app.modules.lojas.models import Loja
from app.modules.lojas.service import matriz, obter_loja
from app.modules.produtos.models import Produto
from app.modules.produtos.service import listar as listar_produtos
from app.modules.produtos.service import obter as obter_produto
from app.shared.datas import hoje
from app.shared.erros import ErroDeNegocio, NaoEncontrado
from app.shared.models import uuid7


class EstoqueInsuficiente(ErroDeNegocio):
    status_code = 409


@dataclass
class Referencia:
    """De onde veio o movimento (ex.: tipo "venda_item" e o id do item)."""

    tipo: str
    id: UUID | None = None


def _movimentar(
    db: Session,
    lote: Lote,
    quantidade: Decimal,
    tipo: str,
    usuario_id: UUID,
    *,
    custo_unitario: Decimal | None = None,
    referencia: Referencia | None = None,
    motivo: str | None = None,
) -> MovimentoEstoque:
    """Altera o saldo do lote e grava o movimento. O lote deve estar travado (FOR UPDATE)."""
    novo_saldo = lote.quantidade + quantidade
    if novo_saldo < 0:
        raise EstoqueInsuficiente(f"Saldo insuficiente no lote {lote.numero_lote}")
    lote.quantidade = novo_saldo
    movimento = MovimentoEstoque(
        loja_id=lote.loja_id,
        produto_id=lote.produto_id,
        lote_id=lote.id,
        tipo=tipo,
        quantidade=quantidade,
        custo_unitario=custo_unitario,
        referencia_tipo=referencia.tipo if referencia else None,
        referencia_id=referencia.id if referencia else None,
        usuario_id=usuario_id,
        motivo=motivo,
    )
    db.add(movimento)
    return movimento


def _lote_travado(db: Session, lote_id: UUID) -> Lote:
    lote = db.scalar(select(Lote).where(Lote.id == lote_id).with_for_update(of=Lote))
    if lote is None:
        raise NaoEncontrado("Lote não encontrado")
    return lote


def loja_ou_matriz(db: Session, loja_id: UUID | None) -> Loja:
    """A loja informada, ou a matriz quando nenhuma foi escolhida."""
    loja = obter_loja(db, loja_id) if loja_id is not None else matriz(db)
    if not loja.ativo:
        raise ErroDeNegocio(f"A loja {loja.nome} está desativada")
    return loja


def _obter_ou_criar_lote(db: Session, loja_id: UUID, produto: Produto, numero_lote: str, validade) -> Lote:
    """Cria o lote na loja se ainda não existe (seguro com dois usuários ao mesmo tempo) e o trava."""
    db.execute(
        insert(Lote)
        .values(loja_id=loja_id, produto_id=produto.id, numero_lote=numero_lote, validade=validade, quantidade=0)
        .on_conflict_do_nothing(index_elements=["farmacia_id", "loja_id", "produto_id", "numero_lote"])
    )
    lote = db.scalar(
        select(Lote)
        .where(Lote.loja_id == loja_id, Lote.produto_id == produto.id, Lote.numero_lote == numero_lote)
        .with_for_update(of=Lote)
    )
    if validade is not None and lote.validade != validade:
        raise ErroDeNegocio(
            f"O lote {numero_lote} já existe com validade {lote.validade:%d/%m/%Y}. Confira a nota."
        )
    return lote


def entrar(
    db: Session,
    loja_id: UUID,
    produto: Produto,
    numero_lote: str | None,
    validade,
    quantidade: Decimal,
    usuario_id: UUID,
    *,
    custo_unitario: Decimal | None = None,
    referencia: Referencia | None = None,
    motivo: str | None = None,
) -> MovimentoEstoque:
    """Soma `quantidade` no lote da loja, criando o lote se preciso. Não faz commit."""
    if produto.controla_lote:
        if not numero_lote or validade is None:
            raise ErroDeNegocio(f"Informe lote e validade de {produto.nome}")
        if validade < hoje():
            raise ErroDeNegocio(f"O lote {numero_lote} de {produto.nome} já está vencido")
        lote = _obter_ou_criar_lote(db, loja_id, produto, numero_lote.strip().upper(), validade)
    else:
        lote = _obter_ou_criar_lote(db, loja_id, produto, LOTE_PADRAO, None)

    if custo_unitario is not None:
        produto.preco_custo = custo_unitario.quantize(Decimal("0.01"))
    return _movimentar(
        db,
        lote,
        quantidade,
        "entrada",
        usuario_id,
        custo_unitario=custo_unitario,
        referencia=referencia,
        motivo=motivo,
    )


def registrar_entrada(db: Session, usuario_id: UUID, entrada: EntradaCriar) -> list[MovimentoEstoque]:
    loja = loja_ou_matriz(db, entrada.loja_id)
    movimentos = [
        entrar(
            db,
            loja.id,
            obter_produto(db, item.produto_id),
            item.numero_lote,
            item.validade,
            item.quantidade,
            usuario_id,
            custo_unitario=item.custo_unitario,
            motivo=entrada.observacao,
        )
        for item in entrada.itens
    ]
    db.commit()
    return movimentos


def ajustar(db: Session, usuario_id: UUID, ajuste: AjusteCriar) -> MovimentoEstoque:
    lote = _lote_travado(db, ajuste.lote_id)
    diferenca = ajuste.nova_quantidade - lote.quantidade
    if diferenca == 0:
        raise ErroDeNegocio("A quantidade informada é igual ao saldo atual")
    movimento = _movimentar(db, lote, diferenca, "ajuste", usuario_id, motivo=ajuste.motivo)
    db.commit()
    return movimento


def registrar_perda(db: Session, usuario_id: UUID, perda: PerdaCriar) -> MovimentoEstoque:
    lote = _lote_travado(db, perda.lote_id)
    movimento = _movimentar(db, lote, -perda.quantidade, "perda", usuario_id, motivo=perda.motivo)
    db.commit()
    return movimento


def transferir(db: Session, usuario_id: UUID, dados: TransferenciaCriar) -> list[MovimentoEstoque]:
    """Leva lotes de uma loja para outra. Cada item gera uma saída e uma entrada com a mesma referência."""
    destino = loja_ou_matriz(db, dados.loja_destino_id)
    referencia = Referencia("transferencia", uuid7())
    movimentos = []
    for item in dados.itens:
        origem = _lote_travado(db, item.lote_id)
        if origem.loja_id == destino.id:
            raise ErroDeNegocio(f"O lote {origem.numero_lote} já está na loja {destino.nome}")
        if origem.validade is not None and origem.validade < hoje():
            raise ErroDeNegocio(f"O lote {origem.numero_lote} está vencido e não pode ser transferido")
        motivo = dados.observacao or f"Transferência para {destino.nome}"
        movimentos.append(
            _movimentar(db, origem, -item.quantidade, "transferencia", usuario_id, referencia=referencia, motivo=motivo)
        )
        chegada = _obter_ou_criar_lote(db, destino.id, origem.produto, origem.numero_lote, origem.validade)
        movimentos.append(
            _movimentar(db, chegada, item.quantidade, "transferencia", usuario_id, referencia=referencia, motivo=motivo)
        )
    db.commit()
    return movimentos


def _lotes_vendaveis(loja_id: UUID | None = None):
    """Lotes com saldo e não vencidos, na ordem FEFO (vence primeiro, sai primeiro)."""
    filtro = select(Lote).where(Lote.quantidade > 0, or_(Lote.validade.is_(None), Lote.validade >= hoje()))
    if loja_id is not None:
        filtro = filtro.where(Lote.loja_id == loja_id)
    return filtro.order_by(Lote.validade.asc().nulls_last(), Lote.criado_em)


def saldo_vendavel(db: Session, produto_id: UUID, loja_id: UUID | None = None) -> Decimal:
    """Saldo que pode ser vendido. Sem loja, soma todas as lojas."""
    vendaveis = _lotes_vendaveis(loja_id).where(Lote.produto_id == produto_id).subquery()
    return db.scalar(select(func.coalesce(func.sum(vendaveis.c.quantidade), 0)))


def baixar_fefo(
    db: Session,
    loja_id: UUID,
    produto: Produto,
    quantidade: Decimal,
    usuario_id: UUID,
    referencia: Referencia,
    tipo: str = "venda",
) -> list[MovimentoEstoque]:
    """Tira `quantidade` do estoque da loja, começando pelo lote que vence antes.

    Não faz commit: quem chama (a venda) decide, para tudo entrar numa transação só.
    """
    lotes = db.scalars(
        _lotes_vendaveis(loja_id).where(Lote.produto_id == produto.id).with_for_update(of=Lote)
    ).all()
    disponivel = sum((lote.quantidade for lote in lotes), Decimal(0))
    if disponivel < quantidade:
        raise EstoqueInsuficiente(
            f"Estoque insuficiente de {produto.nome}: disponível {disponivel.normalize()}"
        )

    movimentos = []
    restante = quantidade
    for lote in lotes:
        if restante == 0:
            break
        tirar = min(lote.quantidade, restante)
        movimentos.append(_movimentar(db, lote, -tirar, tipo, usuario_id, referencia=referencia))
        restante -= tirar
    return movimentos


def listar_lotes(
    db: Session, produto_id: UUID | None, incluir_zerados: bool, loja_id: UUID | None = None
) -> list[Lote]:
    filtro = select(Lote)
    if produto_id is not None:
        filtro = filtro.where(Lote.produto_id == produto_id)
    if loja_id is not None:
        filtro = filtro.where(Lote.loja_id == loja_id)
    if not incluir_zerados:
        filtro = filtro.where(Lote.quantidade > 0)
    return db.scalars(filtro.order_by(Lote.validade.asc().nulls_last())).all()


def listar_movimentos(
    db: Session, produto_id: UUID | None, pagina: int, por_pagina: int, loja_id: UUID | None = None
):
    filtro = select(MovimentoEstoque)
    if produto_id is not None:
        filtro = filtro.where(MovimentoEstoque.produto_id == produto_id)
    if loja_id is not None:
        filtro = filtro.where(MovimentoEstoque.loja_id == loja_id)
    return db.scalars(
        filtro.order_by(MovimentoEstoque.criado_em.desc(), MovimentoEstoque.id.desc())
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    ).all()


def _com_produto(lote: Lote, lojas: dict[UUID, str]) -> LoteComProduto:
    dias = (lote.validade - hoje()).days if lote.validade else None
    return LoteComProduto(
        id=lote.id,
        loja_id=lote.loja_id,
        produto_id=lote.produto_id,
        numero_lote=lote.numero_lote,
        validade=lote.validade,
        quantidade=lote.quantidade,
        produto_nome=lote.produto.nome,
        loja_nome=lojas.get(lote.loja_id, ""),
        dias_para_vencer=dias,
    )


def _nomes_das_lojas(db: Session) -> dict[UUID, str]:
    return dict(db.execute(select(Loja.id, Loja.nome)).all())


def alertas(db: Session, dias: int, loja_id: UUID | None = None) -> Alertas:
    """Vencidos, vencendo e abaixo do mínimo. Sem loja, mostra cada loja ativa separada."""
    lojas = _nomes_das_lojas(db)
    com_saldo = select(Lote).where(Lote.quantidade > 0, Lote.validade.is_not(None))
    if loja_id is not None:
        com_saldo = com_saldo.where(Lote.loja_id == loja_id)
    vencidos = db.scalars(com_saldo.where(Lote.validade < hoje()).order_by(Lote.validade)).all()
    vencendo = db.scalars(
        com_saldo.where(Lote.validade >= hoje(), Lote.validade <= hoje() + timedelta(days=dias))
        .order_by(Lote.validade)
    ).all()

    # O mínimo vale para cada loja: cada prateleira precisa ter o seu.
    vendaveis = _lotes_vendaveis().subquery()
    saldo = func.coalesce(func.sum(vendaveis.c.quantidade), 0)
    lojas_ativas = select(Loja.id.label("loja_id"), Loja.nome.label("loja_nome")).where(Loja.ativo.is_(True))
    if loja_id is not None:
        lojas_ativas = lojas_ativas.where(Loja.id == loja_id)
    lojas_ativas = lojas_ativas.subquery()
    abaixo = db.execute(
        select(
            Produto.id, Produto.nome, lojas_ativas.c.loja_id, lojas_ativas.c.loja_nome,
            saldo.label("saldo"), Produto.estoque_minimo,
        )
        .select_from(Produto)
        .join(lojas_ativas, sa_true())
        .outerjoin(
            vendaveis, (vendaveis.c.produto_id == Produto.id) & (vendaveis.c.loja_id == lojas_ativas.c.loja_id)
        )
        .where(Produto.ativo.is_(True), Produto.estoque_minimo > 0)
        .group_by(Produto.id, lojas_ativas.c.loja_id, lojas_ativas.c.loja_nome)
        .having(saldo < Produto.estoque_minimo)
        .order_by(Produto.nome, lojas_ativas.c.loja_nome)
    ).all()

    return Alertas(
        vencidos=[_com_produto(lote, lojas) for lote in vencidos],
        vencendo=[_com_produto(lote, lojas) for lote in vencendo],
        abaixo_do_minimo=[
            ProdutoAbaixoMinimo(
                produto_id=l.id, nome=l.nome, loja_id=l.loja_id, loja_nome=l.loja_nome,
                saldo=l.saldo, estoque_minimo=l.estoque_minimo,
            )
            for l in abaixo
        ],
    )


def saldos(db: Session, busca: str | None, pagina: int, por_pagina: int) -> tuple[list[SaldoProduto], int]:
    """Saldo vendável de cada produto em cada loja, e quanto está vencido parado no estoque."""
    produtos, total = listar_produtos(db, busca, pagina, por_pagina, incluir_inativos=False)
    ids = [p.id for p in produtos]
    vendavel: dict[UUID, dict[str, Decimal]] = {i: {} for i in ids}
    vencido: dict[UUID, Decimal] = {i: Decimal(0) for i in ids}
    if ids:
        vendaveis = _lotes_vendaveis().where(Lote.produto_id.in_(ids)).subquery()
        for produto_id, loja, quantidade in db.execute(
            select(vendaveis.c.produto_id, vendaveis.c.loja_id, func.sum(vendaveis.c.quantidade))
            .group_by(vendaveis.c.produto_id, vendaveis.c.loja_id)
        ):
            vendavel[produto_id][str(loja)] = quantidade
        for produto_id, quantidade in db.execute(
            select(Lote.produto_id, func.sum(Lote.quantidade))
            .where(Lote.produto_id.in_(ids), Lote.quantidade > 0, Lote.validade < hoje())
            .group_by(Lote.produto_id)
        ):
            vencido[produto_id] = quantidade
    return [
        SaldoProduto(
            produto_id=p.id,
            nome=p.nome,
            apresentacao=p.apresentacao,
            ean=p.ean,
            estoque_minimo=p.estoque_minimo,
            total=sum(vendavel[p.id].values(), Decimal(0)),
            por_loja=vendavel[p.id],
            vencido=vencido[p.id],
        )
        for p in produtos
    ], total


def devolver_movimento(db: Session, movimento: MovimentoEstoque, usuario_id: UUID, motivo: str) -> MovimentoEstoque:
    """Desfaz uma saída, devolvendo a quantidade ao mesmo lote. Não faz commit."""
    lote = _lote_travado(db, movimento.lote_id)
    return _movimentar(
        db,
        lote,
        -movimento.quantidade,
        "devolucao",
        usuario_id,
        referencia=Referencia(movimento.referencia_tipo, movimento.referencia_id),
        motivo=motivo,
    )
