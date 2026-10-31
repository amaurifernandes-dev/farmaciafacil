"""Inventário: a equipe conta o estoque da loja (bipando com o celular) e, no fim, o saldo vira o contado."""

import csv
import io
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import TokenDados
from app.modules.auth.models import Usuario
from app.modules.estoque.models import LOTE_PADRAO, Lote
from app.modules.estoque.service import (
    Referencia,
    _movimentar,
    _obter_ou_criar_lote,
    loja_ou_matriz,
)
from app.modules.inventario.models import Inventario, ItemInventario
from app.modules.inventario.schemas import (
    Contar,
    InventarioCriar,
    InventarioDetalhe,
    InventarioSaida,
    ItemSaida,
    Resumo,
)
from app.modules.lojas.models import Loja
from app.modules.produtos.models import Produto
from app.modules.produtos.service import obter as obter_produto
from app.modules.produtos.service import obter_por_ean
from app.shared.datas import hoje
from app.shared.erros import Conflito, ErroDeNegocio, NaoEncontrado

ZERO = Decimal(0)
CENTAVO = Decimal("0.01")
CUIDAM_DO_ESTOQUE = ("admin", "gerente", "farmaceutico", "estoque")


def ve_saldo(usuario: TokenDados) -> bool:
    return usuario.papel in CUIDAM_DO_ESTOQUE


def _saldos(db: Session, loja_id: UUID, produto_ids: list[UUID] | None = None) -> dict[UUID, Decimal]:
    """Saldo de cada produto na loja, somando todos os lotes (os vencidos também estão na prateleira)."""
    consulta = select(Lote.produto_id, func.sum(Lote.quantidade)).where(Lote.loja_id == loja_id)
    if produto_ids is not None:
        consulta = consulta.where(Lote.produto_id.in_(produto_ids))
    return dict(db.execute(consulta.group_by(Lote.produto_id)).all())


def _obter(db: Session, inventario_id: UUID, travar: bool = False) -> Inventario:
    consulta = select(Inventario).where(Inventario.id == inventario_id)
    if travar:
        consulta = consulta.with_for_update()
    inventario = db.scalar(consulta)
    if inventario is None:
        raise NaoEncontrado("Inventário não encontrado")
    return inventario


def _aberto(db: Session, inventario_id: UUID) -> Inventario:
    inventario = _obter(db, inventario_id)
    if inventario.status != "aberto":
        raise ErroDeNegocio("Este inventário já foi encerrado")
    return inventario


def _saida(db: Session, inventario: Inventario, nomes: dict | None = None) -> InventarioSaida:
    nomes = nomes if nomes is not None else dict(db.execute(select(Usuario.id, Usuario.nome)).all())
    loja = db.get(Loja, inventario.loja_id)
    return InventarioSaida(
        id=inventario.id,
        loja_id=inventario.loja_id,
        loja_nome=loja.nome,
        descricao=inventario.descricao,
        escopo=inventario.escopo,
        status=inventario.status,
        aberto_por=nomes.get(inventario.aberto_por, ""),
        criado_em=inventario.criado_em,
        finalizado_por=nomes.get(inventario.finalizado_por) if inventario.finalizado_por else None,
        finalizado_em=inventario.finalizado_em,
        produtos_ajustados=inventario.produtos_ajustados,
        valor_sobra=inventario.valor_sobra,
        valor_falta=inventario.valor_falta,
    )


def listar(db: Session) -> list[InventarioSaida]:
    nomes = dict(db.execute(select(Usuario.id, Usuario.nome)).all())
    inventarios = db.scalars(select(Inventario).order_by(Inventario.criado_em.desc()).limit(100)).all()
    return [_saida(db, i, nomes) for i in inventarios]


def abrir(db: Session, usuario: TokenDados, dados: InventarioCriar) -> InventarioSaida:
    loja = loja_ou_matriz(db, dados.loja_id)
    if db.scalar(select(Inventario.id).where(Inventario.loja_id == loja.id, Inventario.status == "aberto")):
        raise Conflito(f"Já tem uma contagem aberta na loja {loja.nome}. Termine ou cancele antes de abrir outra.")
    inventario = Inventario(loja_id=loja.id, descricao=dados.descricao.strip(), escopo=dados.escopo,
                            status="aberto", aberto_por=usuario.usuario_id)
    db.add(inventario)
    db.commit()
    return _saida(db, inventario)


def _item(produto: Produto, item: ItemInventario, mostra_saldo: bool) -> ItemSaida:
    diferenca = item.quantidade - item.saldo_sistema
    valor = (diferenca * item.custo_unitario).quantize(CENTAVO, ROUND_HALF_UP) if item.custo_unitario is not None else None
    return ItemSaida(
        produto_id=produto.id,
        nome=produto.nome,
        apresentacao=produto.apresentacao,
        ean=produto.ean,
        quantidade=item.quantidade,
        contado=item.contado,
        saldo_sistema=item.saldo_sistema if mostra_saldo else None,
        diferenca=diferenca if mostra_saldo else None,
        custo_unitario=item.custo_unitario if mostra_saldo else None,
        valor_diferenca=valor if mostra_saldo else None,
        atualizado_em=item.atualizado_em or datetime.now(UTC),
    )


def contar(db: Session, usuario: TokenDados, inventario_id: UUID, dados: Contar) -> ItemSaida:
    inventario = _aberto(db, inventario_id)
    if dados.codigo is not None:
        try:
            produto = obter_por_ean(db, dados.codigo.strip())
        except NaoEncontrado:
            raise NaoEncontrado(f"Nenhum produto com o código {dados.codigo}. Confira ou busque pelo nome.") from None
    else:
        produto = obter_produto(db, dados.produto_id)
    if produto.controle:
        raise ErroDeNegocio(
            f"{produto.nome} é controlado e não entra no inventário: a diferença de controlado é lançada como "
            "perda com o motivo da Anvisa, em Estoque."
        )
    item = db.scalar(
        select(ItemInventario)
        .where(ItemInventario.inventario_id == inventario.id, ItemInventario.produto_id == produto.id)
        .with_for_update()
    )
    saldo_agora = _saldos(db, inventario.loja_id, [produto.id]).get(produto.id, ZERO)
    if item is None:
        if dados.quantidade < 0:
            raise ErroDeNegocio(f"{produto.nome} ainda não foi contado")
        item = ItemInventario(inventario_id=inventario.id, produto_id=produto.id, quantidade=dados.quantidade,
                              saldo_sistema=saldo_agora, custo_unitario=produto.preco_custo, contado=True,
                              usuario_id=usuario.usuario_id)
        db.add(item)
    else:
        nova = item.quantidade + dados.quantidade if dados.modo == "somar" else dados.quantidade
        if nova < 0:
            raise ErroDeNegocio(f"A contagem de {produto.nome} ficaria negativa")
        item.quantidade = nova
        item.usuario_id = usuario.usuario_id
        if dados.modo == "definir":
            # Contou tudo de novo: compara com o saldo de agora.
            item.saldo_sistema = saldo_agora
    db.commit()
    db.refresh(item)
    return _item(produto, item, ve_saldo(usuario))


def remover_item(db: Session, inventario_id: UUID, produto_id: UUID) -> None:
    inventario = _aberto(db, inventario_id)
    item = db.scalar(select(ItemInventario).where(
        ItemInventario.inventario_id == inventario.id, ItemInventario.produto_id == produto_id))
    if item is None:
        raise NaoEncontrado("Este produto não foi contado")
    db.delete(item)
    db.commit()


def _nao_contados(db: Session, inventario: Inventario, contados: set[UUID]) -> list[tuple[Produto, Decimal]]:
    """No inventário geral, o que tem saldo na loja e ninguém contou (não inclui controlados)."""
    saldos = {p: s for p, s in _saldos(db, inventario.loja_id).items() if s > 0 and p not in contados}
    if not saldos:
        return []
    produtos = db.scalars(select(Produto).where(Produto.id.in_(saldos), Produto.controle.is_(None))
                          .order_by(Produto.nome)).all()
    return [(p, saldos[p.id]) for p in produtos]


def _resumo(itens: list[ItemSaida], nao_contados: list[ItemSaida] | None, mostra_saldo: bool) -> Resumo:
    contados = [i for i in itens if i.contado]
    todos = itens + (nao_contados or [])
    com_diferenca = [i for i in todos if i.diferenca]
    return Resumo(
        produtos_contados=len(contados),
        unidades_contadas=sum((i.quantidade for i in contados), ZERO),
        com_diferenca=len(com_diferenca) if mostra_saldo else None,
        valor_sobra=sum((i.valor_diferenca for i in com_diferenca if i.valor_diferenca and i.valor_diferenca > 0),
                        ZERO) if mostra_saldo else None,
        valor_falta=-sum((i.valor_diferenca for i in com_diferenca if i.valor_diferenca and i.valor_diferenca < 0),
                         ZERO) if mostra_saldo else None,
        sem_custo=sum(1 for i in com_diferenca if i.custo_unitario is None) if mostra_saldo else None,
        nao_contados=len(nao_contados) if nao_contados is not None else None,
    )


def detalhe(db: Session, usuario: TokenDados, inventario_id: UUID) -> InventarioDetalhe:
    inventario = _obter(db, inventario_id)
    mostra = ve_saldo(usuario)
    linhas = db.execute(
        select(ItemInventario, Produto).join(Produto, Produto.id == ItemInventario.produto_id)
        .where(ItemInventario.inventario_id == inventario.id)
        .order_by(ItemInventario.atualizado_em.desc())
    ).all()
    itens = [_item(p, i, mostra) for i, p in linhas]
    nao_contados = None
    if inventario.escopo == "geral" and inventario.status == "aberto":
        agora = datetime.now(UTC)
        nao_contados = [
            _item(p, ItemInventario(quantidade=ZERO, saldo_sistema=saldo, custo_unitario=p.preco_custo,
                                    contado=False, atualizado_em=agora), mostra)
            for p, saldo in _nao_contados(db, inventario, {i.produto_id for i in itens})
        ]
    return InventarioDetalhe(
        **_saida(db, inventario).model_dump(),
        resumo=_resumo(itens, nao_contados, mostra),
        itens=itens,
        nao_contados=nao_contados if mostra else None,
        ve_saldo=mostra,
    )


def _aplicar(db: Session, inventario: Inventario, produto: Produto, diferenca: Decimal, usuario_id: UUID) -> None:
    """Leva a diferença para os lotes da loja: a falta sai dos que vencem primeiro; a sobra entra no mais novo."""
    referencia = Referencia("inventario", inventario.id)
    motivo = f"Inventário: {inventario.descricao}"[:200]
    lotes = db.scalars(
        select(Lote).where(Lote.loja_id == inventario.loja_id, Lote.produto_id == produto.id)
        .order_by(Lote.validade.asc().nulls_last(), Lote.criado_em).with_for_update(of=Lote)
    ).all()
    if diferenca < 0:
        falta = -diferenca
        for lote in lotes:
            if falta <= 0:
                break
            tirar = min(falta, lote.quantidade)
            if tirar > 0:
                _movimentar(db, lote, -tirar, "ajuste", usuario_id, custo_unitario=produto.preco_custo,
                            referencia=referencia, motivo=motivo)
                falta -= tirar
        return
    validos = [lote for lote in lotes if lote.validade is None or lote.validade >= hoje()]
    destino = validos[-1] if validos else None
    if destino is None:
        destino = _obter_ou_criar_lote(db, inventario.loja_id, produto, LOTE_PADRAO, None)
    _movimentar(db, destino, diferenca, "ajuste", usuario_id, custo_unitario=produto.preco_custo,
                referencia=referencia, motivo=motivo)


def finalizar(db: Session, usuario: TokenDados, inventario_id: UUID) -> InventarioSaida:
    inventario = _obter(db, inventario_id, travar=True)
    if inventario.status != "aberto":
        raise ErroDeNegocio("Este inventário já foi encerrado")
    linhas = db.execute(
        select(ItemInventario, Produto).join(Produto, Produto.id == ItemInventario.produto_id)
        .where(ItemInventario.inventario_id == inventario.id)
    ).all()
    if not linhas:
        raise ErroDeNegocio("Nenhum produto foi contado. Conte ou cancele o inventário.")
    pares = [(item, produto) for item, produto in linhas]
    if inventario.escopo == "geral":
        for produto, saldo in _nao_contados(db, inventario, {i.produto_id for i, _ in pares}):
            item = ItemInventario(inventario_id=inventario.id, produto_id=produto.id, quantidade=ZERO,
                                  saldo_sistema=saldo, custo_unitario=produto.preco_custo, contado=False,
                                  usuario_id=usuario.usuario_id)
            db.add(item)
            pares.append((item, produto))

    ajustados, sobra, falta = 0, ZERO, ZERO
    for item, produto in pares:
        diferenca = item.quantidade - item.saldo_sistema
        if diferenca == 0:
            continue
        _aplicar(db, inventario, produto, diferenca, usuario.usuario_id)
        ajustados += 1
        if item.custo_unitario is not None:
            valor = (diferenca * item.custo_unitario).quantize(CENTAVO, ROUND_HALF_UP)
            if valor > 0:
                sobra += valor
            else:
                falta -= valor
    inventario.status = "finalizado"
    inventario.finalizado_por = usuario.usuario_id
    inventario.finalizado_em = datetime.now(UTC)
    inventario.produtos_ajustados = ajustados
    inventario.valor_sobra = sobra
    inventario.valor_falta = falta
    db.commit()
    return _saida(db, inventario)


def cancelar(db: Session, inventario_id: UUID) -> InventarioSaida:
    inventario = _obter(db, inventario_id, travar=True)
    if inventario.status != "aberto":
        raise ErroDeNegocio("Este inventário já foi encerrado")
    inventario.status = "cancelado"
    db.commit()
    return _saida(db, inventario)


def planilha_csv(db: Session, usuario: TokenDados, inventario_id: UUID) -> tuple[str, bytes]:
    dados = detalhe(db, usuario, inventario_id)
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";")
    escritor.writerow([f"{dados.descricao} - {dados.loja_nome} - {dados.criado_em:%d/%m/%Y}"])
    escritor.writerow(["Produto", "Código de barras", "Contado", "Sistema", "Diferença", "Custo", "Valor"])
    for i in dados.itens + (dados.nao_contados or []):
        escritor.writerow([
            f"{i.nome} {i.apresentacao or ''}".strip() + ("" if i.contado else " (não contado)"),
            i.ean or "", _br(i.quantidade, 3), _br(i.saldo_sistema, 3), _br(i.diferenca, 3),
            _br(i.custo_unitario), _br(i.valor_diferenca),
        ])
    return f"inventario-{dados.criado_em:%Y-%m-%d}.csv", saida.getvalue().encode("utf-8-sig")


def _br(valor: Decimal | None, casas: int = 2) -> str:
    if valor is None:
        return ""
    texto = f"{valor:.{casas}f}".replace(".", ",")
    return texto.rstrip("0").rstrip(",") if casas == 3 else texto
