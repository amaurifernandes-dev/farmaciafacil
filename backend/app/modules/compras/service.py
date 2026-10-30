"""Compras: notas de entrada pelo XML e sugestão do que comprar."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import ROUND_CEILING, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import TokenDados
from app.modules.compras.models import NotaEntrada, NotaEntradaItem, ProdutoFornecedor
from app.modules.compras.nfe_xml import ItemNota, NotaLida, ler_nfe
from app.modules.compras.schemas import (
    ItemAtualizar,
    ItemNotaSaida,
    ItemSugestao,
    NotaImportar,
    NotaResumo,
    NotaSaida,
    PrecoFornecedor,
    SugestaoCompras,
)
from app.modules.estoque.models import MovimentoEstoque
from app.modules.estoque.service import Referencia, _lotes_vendaveis, entrar, loja_ou_matriz
from app.modules.financeiro.service import contas_da_nota
from app.modules.fornecedores.models import Fornecedor
from app.modules.lojas.models import Loja
from app.modules.produtos.models import Produto, ProdutoCodigo
from app.modules.produtos.service import obter as obter_produto
from app.shared.erros import Conflito, ErroDeNegocio, NaoEncontrado

CENTAVO = Decimal("0.01")


def _agora() -> datetime:
    return datetime.now(timezone.utc)


# --- Importação do XML ---

def _fornecedor(db: Session, nota: NotaLida) -> Fornecedor:
    """O fornecedor pelo CNPJ. Se é a primeira compra dele, já fica cadastrado com os dados da nota."""
    emitente = nota.emitente
    fornecedor = db.scalar(select(Fornecedor).where(Fornecedor.cnpj == emitente.cnpj))
    if fornecedor is None:
        fornecedor = Fornecedor(
            cnpj=emitente.cnpj,
            razao_social=emitente.razao_social,
            nome_fantasia=emitente.nome_fantasia,
            inscricao_estadual=emitente.inscricao_estadual,
            telefone=emitente.telefone,
            cep=emitente.cep,
            endereco=emitente.endereco,
            bairro=emitente.bairro,
            cidade=emitente.cidade,
            uf=emitente.uf,
        )
        db.add(fornecedor)
        db.flush()
    return fornecedor


def _loja_da_nota(db: Session, nota: NotaLida, loja_id: UUID | None) -> Loja:
    if loja_id is not None:
        return loja_ou_matriz(db, loja_id)
    loja = db.scalar(select(Loja).where(Loja.cnpj == nota.cnpj_destinatario)) if nota.cnpj_destinatario else None
    if loja is None:
        raise ErroDeNegocio(
            "O CNPJ de destino desta nota não é de nenhuma das suas lojas. Escolha a loja que recebeu a mercadoria."
        )
    return loja_ou_matriz(db, loja.id)


def _produto_pelo_ean(db: Session, ean: str | None) -> Produto | None:
    if not ean:
        return None
    extra = select(ProdutoCodigo.produto_id).where(ProdutoCodigo.ean == ean)
    return db.scalar(
        select(Produto).where(Produto.ativo.is_(True), (Produto.ean == ean) | Produto.id.in_(extra))
    )


def _reconhecer(db: Session, fornecedor: Fornecedor, item: ItemNota) -> tuple[Produto | None, int]:
    """Acha o produto do item: primeiro pelo código já usado com este fornecedor, depois pelo código de barras."""
    vinculo = db.scalar(
        select(ProdutoFornecedor).where(
            ProdutoFornecedor.fornecedor_id == fornecedor.id, ProdutoFornecedor.codigo == item.codigo
        )
    )
    if vinculo is not None:
        produto = db.get(Produto, vinculo.produto_id)
        if produto is not None and produto.ativo:
            return produto, vinculo.fator
    produto = _produto_pelo_ean(db, item.ean)
    if produto is not None:
        return produto, 1
    # O código tributável costuma ser o da unidade (a caixa fechada tem outro).
    produto = _produto_pelo_ean(db, item.ean_tributavel)
    if produto is not None:
        return produto, item.fator_sugerido
    return None, item.fator_sugerido


def importar(db: Session, usuario: TokenDados, dados: NotaImportar) -> NotaEntrada:
    lida = ler_nfe(dados.xml)
    existente = db.scalar(
        select(NotaEntrada).where(NotaEntrada.chave == lida.chave, NotaEntrada.status != "cancelada")
    )
    if existente is not None:
        raise Conflito(f"A nota {existente.numero} deste fornecedor já foi importada")

    loja = _loja_da_nota(db, lida, dados.loja_id)
    fornecedor = _fornecedor(db, lida)
    nota = NotaEntrada(
        loja_id=loja.id,
        fornecedor_id=fornecedor.id,
        chave=lida.chave,
        numero=lida.numero,
        serie=lida.serie,
        emitida_em=lida.emitida_em,
        valor_produtos=lida.valor_produtos,
        valor_total=lida.valor_total,
        usuario_id=usuario.usuario_id,
        xml=dados.xml,
    )

    ordem = 0
    for item in lida.itens:
        produto, fator = _reconhecer(db, fornecedor, item)
        # Um item com dois lotes vira duas linhas, uma por lote.
        lotes = item.lotes or [None]
        for lote in lotes:
            ordem += 1
            quantidade = lote.quantidade if lote else item.quantidade
            nota.itens.append(
                NotaEntradaItem(
                    ordem=ordem,
                    codigo_fornecedor=item.codigo,
                    ean=item.ean or item.ean_tributavel,
                    descricao=item.descricao,
                    ncm=item.ncm,
                    cest=item.cest,
                    registro_ms=item.registro_ms,
                    unidade=item.unidade,
                    quantidade=quantidade,
                    valor_unitario=item.valor_unitario,
                    valor_total=(item.valor_unitario * quantidade).quantize(CENTAVO),
                    numero_lote=lote.numero.strip().upper() if lote else None,
                    validade=lote.validade if lote else None,
                    produto_id=produto.id if produto else None,
                    fator=fator,
                )
            )
    db.add(nota)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflito("Esta nota já foi importada")
    return nota


# --- Conferência e confirmação ---

def obter(db: Session, nota_id: UUID, travar: bool = False) -> NotaEntrada:
    filtro = select(NotaEntrada).where(NotaEntrada.id == nota_id)
    if travar:
        filtro = filtro.with_for_update(of=NotaEntrada)
    nota = db.scalar(filtro)
    if nota is None:
        raise NaoEncontrado("Nota não encontrada")
    return nota


def _resumo(nota: NotaEntrada) -> dict:
    return {
        "id": nota.id,
        "loja_id": nota.loja_id,
        "fornecedor_id": nota.fornecedor_id,
        "fornecedor_nome": nota.fornecedor.nome_fantasia or nota.fornecedor.razao_social,
        "chave": nota.chave,
        "numero": nota.numero,
        "serie": nota.serie,
        "emitida_em": nota.emitida_em,
        "valor_produtos": nota.valor_produtos,
        "valor_total": nota.valor_total,
        "status": nota.status,
        "criado_em": nota.criado_em,
        "confirmada_em": nota.confirmada_em,
        "quantidade_itens": len(nota.itens),
        "itens_sem_produto": sum(1 for i in nota.itens if i.produto_id is None),
    }


def saida(db: Session, nota: NotaEntrada) -> NotaSaida:
    ids = {i.produto_id for i in nota.itens if i.produto_id}
    produtos = {p.id: p for p in db.scalars(select(Produto).where(Produto.id.in_(ids)))} if ids else {}
    itens = []
    for item in nota.itens:
        produto = produtos.get(item.produto_id)
        itens.append(
            ItemNotaSaida.model_validate(item).model_copy(
                update={
                    "produto_nome": produto.nome if produto else None,
                    "produto_controla_lote": produto.controla_lote if produto else None,
                }
            )
        )
    return NotaSaida(**_resumo(nota), itens=itens)


def listar(db: Session, status: str | None, pagina: int, por_pagina: int) -> list[NotaResumo]:
    filtro = select(NotaEntrada)
    if status:
        filtro = filtro.where(NotaEntrada.status == status)
    notas = db.scalars(
        filtro.order_by(NotaEntrada.criado_em.desc()).offset((pagina - 1) * por_pagina).limit(por_pagina)
    ).all()
    return [NotaResumo(**_resumo(n)) for n in notas]


def _pendente(db: Session, nota_id: UUID) -> NotaEntrada:
    nota = obter(db, nota_id, travar=True)
    if nota.status != "pendente":
        raise Conflito(f"Esta nota já está {nota.status}")
    return nota


def atualizar_item(db: Session, nota_id: UUID, item_id: UUID, dados: ItemAtualizar) -> NotaEntrada:
    nota = _pendente(db, nota_id)
    item = next((i for i in nota.itens if i.id == item_id), None)
    if item is None:
        raise NaoEncontrado("Item não encontrado nesta nota")
    alteracoes = dados.model_dump(exclude_unset=True)
    if alteracoes.get("produto_id") is not None:
        obter_produto(db, alteracoes["produto_id"])
    if "fator" in alteracoes and alteracoes["fator"] is None:
        raise ErroDeNegocio("Informe quantas unidades vêm em cada embalagem")
    if alteracoes.get("numero_lote"):
        alteracoes["numero_lote"] = alteracoes["numero_lote"].strip().upper()
    for campo, valor in alteracoes.items():
        setattr(item, campo, valor)
    db.commit()
    return nota


def confirmar(db: Session, usuario: TokenDados, nota_id: UUID) -> NotaEntrada:
    """Dá entrada de todos os itens no estoque da loja da nota e lembra os códigos do fornecedor."""
    nota = _pendente(db, nota_id)
    sem_produto = [i.descricao for i in nota.itens if i.produto_id is None]
    if sem_produto:
        raise ErroDeNegocio(f"Escolha o produto do sistema para: {', '.join(sem_produto[:3])}")

    motivo = f"NF {nota.numero} - {nota.fornecedor.nome_fantasia or nota.fornecedor.razao_social}"[:200]
    vinculos: dict[str, tuple[UUID, int]] = {}
    for item in nota.itens:
        produto = obter_produto(db, item.produto_id)
        entrar(
            db,
            nota.loja_id,
            produto,
            item.numero_lote,
            item.validade,
            item.quantidade * item.fator,
            usuario.usuario_id,
            custo_unitario=(item.valor_unitario / item.fator).quantize(Decimal("0.0001")),
            referencia=Referencia("nota_entrada_item", item.id),
            motivo=motivo,
        )
        vinculos[item.codigo_fornecedor] = (item.produto_id, item.fator)

    for codigo, (produto_id, fator) in vinculos.items():
        if not codigo:
            continue
        db.execute(
            insert(ProdutoFornecedor)
            .values(fornecedor_id=nota.fornecedor_id, codigo=codigo, produto_id=produto_id, fator=fator)
            .on_conflict_do_update(
                index_elements=["farmacia_id", "fornecedor_id", "codigo"],
                set_={"produto_id": produto_id, "fator": fator, "atualizado_em": func.now()},
            )
        )

    contas_da_nota(db, usuario.usuario_id, nota)
    nota.status = "confirmada"
    nota.confirmada_em = _agora()
    db.commit()
    return nota


def cancelar(db: Session, nota_id: UUID) -> NotaEntrada:
    nota = _pendente(db, nota_id)
    nota.status = "cancelada"
    db.commit()
    return nota


# --- Sugestão de compras ---

def precos_por_fornecedor(db: Session, produto_ids: list[UUID]) -> dict[UUID, list[PrecoFornecedor]]:
    """Último custo de cada produto em cada fornecedor, pelas notas confirmadas. Mais barato primeiro."""
    if not produto_ids:
        return {}
    linhas = db.execute(
        select(
            NotaEntradaItem.produto_id,
            NotaEntrada.fornecedor_id,
            func.coalesce(Fornecedor.nome_fantasia, Fornecedor.razao_social).label("nome"),
            (NotaEntradaItem.valor_unitario / NotaEntradaItem.fator).label("custo"),
            NotaEntrada.confirmada_em,
        )
        .join(NotaEntrada, NotaEntrada.id == NotaEntradaItem.nota_id)
        .join(Fornecedor, Fornecedor.id == NotaEntrada.fornecedor_id)
        .where(NotaEntrada.status == "confirmada", NotaEntradaItem.produto_id.in_(produto_ids))
        .order_by(NotaEntradaItem.produto_id, NotaEntrada.fornecedor_id, NotaEntrada.confirmada_em.desc())
        .ext(distinct_on(NotaEntradaItem.produto_id, NotaEntrada.fornecedor_id))
    ).all()
    precos: dict[UUID, list[PrecoFornecedor]] = defaultdict(list)
    for linha in linhas:
        precos[linha.produto_id].append(
            PrecoFornecedor(
                fornecedor_id=linha.fornecedor_id,
                fornecedor_nome=linha.nome,
                custo_unitario=Decimal(linha.custo).quantize(CENTAVO),
                comprado_em=linha.confirmada_em,
            )
        )
    for lista in precos.values():
        lista.sort(key=lambda p: (p.custo_unitario, -p.comprado_em.timestamp()))
    return precos


def sugestao(db: Session, loja_id: UUID | None, dias_historico: int, dias_cobertura: int) -> SugestaoCompras:
    """Quanto comprar para a loja aguentar `dias_cobertura` dias no ritmo de venda recente.

    Nunca sugere menos que o estoque mínimo do produto.
    """
    loja = loja_ou_matriz(db, loja_id)
    desde = _agora() - timedelta(days=dias_historico)

    # Venda menos o que voltou por cancelamento.
    vendido = dict(
        db.execute(
            select(MovimentoEstoque.produto_id, -func.sum(MovimentoEstoque.quantidade))
            .where(
                MovimentoEstoque.loja_id == loja.id,
                MovimentoEstoque.tipo.in_(("venda", "devolucao")),
                MovimentoEstoque.criado_em >= desde,
            )
            .group_by(MovimentoEstoque.produto_id)
        ).all()
    )
    vendaveis = _lotes_vendaveis(loja.id).subquery()
    saldos = dict(
        db.execute(
            select(vendaveis.c.produto_id, func.sum(vendaveis.c.quantidade)).group_by(vendaveis.c.produto_id)
        ).all()
    )

    produtos = db.scalars(
        select(Produto)
        .where(Produto.ativo.is_(True))
        .where(Produto.id.in_(list(vendido)) | (Produto.estoque_minimo > 0))
    ).all()

    candidatos = []
    for produto in produtos:
        saida = max(Decimal(vendido.get(produto.id, 0)), Decimal(0))
        saldo = Decimal(saldos.get(produto.id, 0))
        media = saida / dias_historico
        alvo = max(produto.estoque_minimo, media * dias_cobertura)
        falta = (alvo - saldo).to_integral_value(rounding=ROUND_CEILING)
        if falta <= 0:
            continue
        candidatos.append((produto, saldo, saida, media, falta))

    precos = precos_por_fornecedor(db, [c[0].id for c in candidatos])
    itens = []
    total = Decimal(0)
    for produto, saldo, saida, media, falta in candidatos:
        fornecedores = precos.get(produto.id, [])
        custo = fornecedores[0].custo_unitario if fornecedores else produto.preco_custo
        if custo is not None:
            total += custo * falta
        itens.append(
            ItemSugestao(
                produto_id=produto.id,
                nome=produto.nome,
                apresentacao=produto.apresentacao,
                ean=produto.ean,
                saldo=saldo,
                estoque_minimo=produto.estoque_minimo,
                vendido_no_periodo=saida,
                media_diaria=media.quantize(Decimal("0.001")),
                dias_de_estoque=(saldo / media).quantize(Decimal("0.1")) if media > 0 else None,
                sugerido=falta,
                ultimo_custo=produto.preco_custo,
                fornecedores=fornecedores,
            )
        )
    # Primeiro o que acaba antes.
    itens.sort(key=lambda i: (i.dias_de_estoque is None, i.dias_de_estoque or 0, i.nome))
    return SugestaoCompras(
        loja_id=loja.id,
        dias_historico=dias_historico,
        dias_cobertura=dias_cobertura,
        itens=itens,
        total_estimado=total.quantize(CENTAVO),
    )
