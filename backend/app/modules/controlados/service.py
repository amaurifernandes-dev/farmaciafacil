"""Livro de controlados e arquivos do SNGPC (movimentação e inventário) para a Anvisa."""

import re
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID
from xml.sax.saxutils import escape

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.compras.models import NotaEntrada, NotaEntradaItem
from app.modules.controlados.models import Receita
from app.modules.controlados.regras import NOME_RECEITUARIO
from app.modules.controlados.schemas import (
    LinhaLivro,
    Pendencia,
    ResumoControlados,
    SaldoControlado,
    Totais,
)
from app.modules.estoque.models import Lote, MovimentoEstoque
from app.modules.estoque.service import loja_ou_matriz
from app.modules.lojas.models import Loja
from app.modules.produtos.models import Produto
from app.modules.vendas.models import Venda, VendaItem
from app.shared.datas import FUSO, hoje
from app.shared.erros import ErroDeNegocio

MOTIVOS_PERDA = {
    1: "Furto ou roubo",
    2: "Avaria",
    3: "Vencimento",
    4: "Apreensão pela Vigilância Sanitária",
    5: "Perda no processo",
    6: "Controle de qualidade",
    7: "Saiu da Portaria 344",
    8: "Desvio de qualidade",
    9: "Recolhimento do fabricante",
    10: "Devolução ao fornecedor",
}
NOME_DOCUMENTO = {1: "Registro profissional", 2: "RG"}


def periodo_padrao() -> tuple[date, date]:
    """Do dia 1 do mês até hoje."""
    fim = hoje()
    return fim.replace(day=1), fim


def _limites(inicio: date, fim: date) -> tuple[datetime, datetime]:
    if fim < inicio:
        raise ErroDeNegocio("A data final é antes da inicial")
    return datetime.combine(inicio, time.min, FUSO), datetime.combine(fim + timedelta(days=1), time.min, FUSO)


def _registro_ok(produto: Produto) -> bool:
    return bool(produto.registro_ms and re.fullmatch(r"\d{13}", produto.registro_ms))


def _movimentos(db: Session, loja_id: UUID, ate: datetime, desde: datetime | None = None):
    filtro = (
        select(MovimentoEstoque, Produto)
        .join(Produto, Produto.id == MovimentoEstoque.produto_id)
        .where(MovimentoEstoque.loja_id == loja_id, Produto.controle.is_not(None), MovimentoEstoque.criado_em < ate)
    )
    if desde is not None:
        filtro = filtro.where(MovimentoEstoque.criado_em >= desde)
    return db.execute(filtro.order_by(MovimentoEstoque.criado_em, MovimentoEstoque.id)).all()


def _saldos_iniciais(db: Session, loja_id: UUID, antes: datetime) -> dict[UUID, Decimal]:
    saldos: dict[UUID, Decimal] = defaultdict(Decimal)
    for movimento, produto in _movimentos(db, loja_id, antes):
        saldos[produto.id] += movimento.quantidade
    return saldos


class _Documentos:
    """Busca de uma vez as notas, vendas e receitas citadas pelos movimentos."""

    def __init__(self, db: Session, movimentos: list[MovimentoEstoque]):
        ids_nota = [m.referencia_id for m in movimentos if m.referencia_tipo == "nota_entrada_item"]
        ids_venda = [m.referencia_id for m in movimentos if m.referencia_tipo == "venda_item"]
        self.notas: dict[UUID, NotaEntrada] = {}
        if ids_nota:
            for item_id, nota in db.execute(
                select(NotaEntradaItem.id, NotaEntrada)
                .join(NotaEntrada, NotaEntrada.id == NotaEntradaItem.nota_id)
                .where(NotaEntradaItem.id.in_(ids_nota))
            ):
                self.notas[item_id] = nota
        self.vendas: dict[UUID, Venda] = {}
        if ids_venda:
            for item_id, venda in db.execute(
                select(VendaItem.id, Venda).join(Venda, Venda.id == VendaItem.venda_id).where(VendaItem.id.in_(ids_venda))
            ):
                self.vendas[item_id] = venda
        vendas = {v.id for v in self.vendas.values()}
        self.receitas: dict[UUID, Receita] = {}
        if vendas:
            self.receitas = {r.venda_id: r for r in db.scalars(select(Receita).where(Receita.venda_id.in_(vendas)))}

    def nota(self, movimento: MovimentoEstoque) -> NotaEntrada | None:
        return self.notas.get(movimento.referencia_id) if movimento.referencia_tipo == "nota_entrada_item" else None

    def venda(self, movimento: MovimentoEstoque) -> Venda | None:
        return self.vendas.get(movimento.referencia_id) if movimento.referencia_tipo == "venda_item" else None

    def receita(self, movimento: MovimentoEstoque) -> Receita | None:
        venda = self.venda(movimento)
        return self.receitas.get(venda.id) if venda else None


def _maiuscula(texto: str) -> str:
    return texto[:1].upper() + texto[1:]


def _linha(movimento: MovimentoEstoque, produto: Produto, saldo: Decimal, docs: _Documentos) -> LinhaLivro:
    documento = movimento.motivo
    receita_texto = pessoa = None
    if (nota := docs.nota(movimento)) is not None:
        documento = f"NF {nota.numero} de {nota.fornecedor.nome_fantasia or nota.fornecedor.razao_social}"
    elif movimento.tipo == "entrada":
        documento = f"Entrada sem nota{f': {movimento.motivo}' if movimento.motivo else ''}"
    if (venda := docs.venda(movimento)) is not None and movimento.tipo == "venda":
        documento = f"Venda {venda.numero}" + (" (cancelada)" if venda.status == "cancelada" else "")
        if (receita := docs.receita(movimento)) is not None:
            numero = f" nº {receita.numero_notificacao}" if receita.numero_notificacao else ""
            receita_texto = (
                f"{_maiuscula(NOME_RECEITUARIO[receita.tipo_receituario])}{numero} de "
                f"{receita.data_prescricao:%d/%m/%Y} · {receita.prescritor_nome} "
                f"{receita.prescritor_conselho} {receita.prescritor_numero}/{receita.prescritor_uf}"
            )
            pessoa = receita.comprador_nome or receita.paciente_nome
        else:
            receita_texto = "Sem receita registrada"
    if movimento.tipo == "perda" and movimento.motivo_sngpc:
        documento = f"{MOTIVOS_PERDA[movimento.motivo_sngpc]}: {movimento.motivo}"
    return LinhaLivro(
        data=movimento.criado_em,
        produto_id=produto.id,
        produto=produto.nome if not produto.apresentacao else f"{produto.nome} {produto.apresentacao}",
        lista=produto.controle,
        lote=movimento.lote.numero_lote,
        tipo=movimento.tipo,
        entrada=max(movimento.quantidade, Decimal(0)),
        saida=max(-movimento.quantidade, Decimal(0)),
        saldo=saldo,
        documento=documento,
        receita=receita_texto,
        pessoa=pessoa,
    )


def _saldos_atuais(db: Session, loja_id: UUID) -> list[SaldoControlado]:
    lotes = db.scalars(
        select(Lote)
        .join(Produto, Produto.id == Lote.produto_id)
        .where(Lote.loja_id == loja_id, Lote.quantidade > 0, Produto.controle.is_not(None))
        .order_by(Produto.nome, Lote.validade.asc().nulls_last())
    ).all()
    return [
        SaldoControlado(
            lote_id=lote.id,
            produto_id=lote.produto_id,
            produto=lote.produto.nome,
            lista=lote.produto.controle,
            registro_ms=lote.produto.registro_ms,
            lote=lote.numero_lote,
            validade=lote.validade,
            quantidade=lote.quantidade,
        )
        for lote in lotes
    ]


def _pendencias(loja: Loja, linhas: list[tuple[MovimentoEstoque, Produto]], docs: _Documentos,
                produtos_com_saldo: list[Produto]) -> list[Pendencia]:
    pendencias = []
    if not loja.responsavel_cpf:
        pendencias.append(Pendencia(
            codigo="sem_cpf",
            texto=f"Falta o CPF do farmacêutico responsável da loja {loja.nome} (vai no arquivo como quem transmite).",
            bloqueia=True,
        ))
    sem_registro = sorted({p.nome for _, p in linhas if not _registro_ok(p)} |
                          {p.nome for p in produtos_com_saldo if not _registro_ok(p)})
    if sem_registro:
        pendencias.append(Pendencia(
            codigo="sem_registro_ms",
            texto=f"Sem registro MS de 13 dígitos no cadastro: {', '.join(sem_registro)}.",
            bloqueia=True,
        ))
    sem_nota = sum(1 for m, _ in linhas if m.tipo == "entrada" and m.referencia_tipo != "nota_entrada_item")
    if sem_nota:
        pendencias.append(Pendencia(
            codigo="entrada_sem_nota",
            texto=f"{sem_nota} entrada(s) sem nota fiscal não vão no arquivo. Dê entrada pela nota de compra.",
            bloqueia=False,
        ))
    transferencias = sum(1 for m, _ in linhas if m.tipo == "transferencia")
    if transferencias:
        pendencias.append(Pendencia(
            codigo="transferencia",
            texto=f"{transferencias} movimento(s) de transferência entre lojas não vão no arquivo, porque precisam "
            "da nota fiscal de transferência. Lance direto no site do SNGPC.",
            bloqueia=False,
        ))
    sem_receita = sum(1 for m, _ in linhas if m.tipo == "venda" and docs.receita(m) is None)
    if sem_receita:
        pendencias.append(Pendencia(
            codigo="venda_sem_receita",
            texto=f"{sem_receita} venda(s) de controlado sem receita registrada (de antes desta função). "
            "Não vão no arquivo.",
            bloqueia=False,
        ))
    sem_motivo = sum(1 for m, _ in linhas if m.tipo == "perda" and not m.motivo_sngpc)
    if sem_motivo:
        pendencias.append(Pendencia(
            codigo="perda_sem_motivo",
            texto=f"{sem_motivo} perda(s) sem o motivo da Anvisa. Não vão no arquivo.",
            bloqueia=False,
        ))
    ajustes = sum(1 for m, _ in linhas if m.tipo == "ajuste")
    if ajustes:
        pendencias.append(Pendencia(
            codigo="ajuste",
            texto=f"{ajustes} ajuste(s) de inventário em controlados. A Anvisa não aceita ajuste: confira e, "
            "se preciso, mande um novo inventário.",
            bloqueia=False,
        ))
    return pendencias


def resumo(db: Session, loja_id: UUID | None, inicio: date | None, fim: date | None) -> ResumoControlados:
    loja = loja_ou_matriz(db, loja_id)
    padrao_inicio, padrao_fim = periodo_padrao()
    inicio, fim = inicio or padrao_inicio, fim or padrao_fim
    desde, ate = _limites(inicio, fim)

    saldo = _saldos_iniciais(db, loja.id, desde)
    linhas = _movimentos(db, loja.id, ate, desde)
    docs = _Documentos(db, [m for m, _ in linhas])
    livro = []
    totais = defaultdict(Decimal)
    for movimento, produto in linhas:
        saldo[produto.id] += movimento.quantidade
        livro.append(_linha(movimento, produto, saldo[produto.id], docs))
        if movimento.tipo == "entrada":
            totais["entradas"] += movimento.quantidade
        elif movimento.tipo == "venda":
            totais["vendas"] -= movimento.quantidade
        elif movimento.tipo == "devolucao" and movimento.referencia_tipo == "venda_item":
            totais["vendas"] -= movimento.quantidade  # cancelamento devolve a venda
        elif movimento.tipo == "perda":
            totais["perdas"] -= movimento.quantidade
        elif movimento.tipo == "transferencia" and movimento.quantidade < 0:
            totais["transferencias"] -= movimento.quantidade

    saldos = _saldos_atuais(db, loja.id)
    com_saldo = list({s.produto_id: db.get(Produto, s.produto_id) for s in saldos}.values())
    return ResumoControlados(
        loja_id=loja.id,
        inicio=inicio,
        fim=fim,
        totais=Totais(**{k: totais[k] for k in ("entradas", "vendas", "perdas", "transferencias")}),
        pendencias=_pendencias(loja, linhas, docs, com_saldo),
        saldos=saldos,
        livro=livro,
    )


# --- Arquivos XML do SNGPC ---

def _tag(nome: str, valor) -> str:
    return f"<{nome}>{escape(str(valor))}</{nome}>"


def _qtd(valor: Decimal) -> str:
    return str(int(abs(valor)))


def _unidade(produto: Produto) -> str:
    return "2" if produto.embalagem_sngpc == "frasco" else "1"


def _classe(produto: Produto) -> str:
    return "1" if produto.controle == "ATB" else "2"  # 1 antimicrobiano, 2 sujeito a controle especial


def _medicamento(produto: Produto, lote: str, quantidade: Decimal, *, com_classe: bool = False,
                 uso_prolongado: str | None = None) -> str:
    partes = []
    if uso_prolongado is not None:
        partes.append(_tag("usoProlongado", uso_prolongado))
    if com_classe:
        partes.append(_tag("classeTerapeutica", _classe(produto)))
    partes += [
        _tag("registroMSMedicamento", produto.registro_ms),
        _tag("numeroLoteMedicamento", lote),
        _tag("quantidadeMedicamento", _qtd(quantidade)),
        _tag("unidadeMedidaMedicamento", _unidade(produto)),
    ]
    return "".join(partes)


def _exigir_sem_bloqueio(pendencias: list[Pendencia]) -> None:
    bloqueios = [p.texto for p in pendencias if p.bloqueia]
    if bloqueios:
        raise ErroDeNegocio("Antes de gerar o arquivo: " + " ".join(bloqueios))


def _cabecalho_xml(raiz: str) -> str:
    return f'<?xml version="1.0" encoding="ISO-8859-1"?>\n<{raiz} xmlns="urn:sngpc-schema">'


def _receita_xml(receita: Receita) -> str:
    partes = [
        _tag("tipoReceituarioMedicamento", receita.tipo_receituario),
        _tag("numeroNotificacaoMedicamento", receita.numero_notificacao or "0"),
        _tag("dataPrescricaoMedicamento", receita.data_prescricao.isoformat()),
        "<prescritorMedicamento>"
        + _tag("nomePrescritor", receita.prescritor_nome)
        + _tag("numeroRegistroProfissional", receita.prescritor_numero)
        + _tag("conselhoProfissional", receita.prescritor_conselho)
        + _tag("UFConselho", receita.prescritor_uf)
        + "</prescritorMedicamento>",
        _tag("usoMedicamento", receita.uso),
    ]
    if receita.comprador_nome:
        partes.append(
            "<compradorMedicamento>"
            + _tag("nomeComprador", receita.comprador_nome)
            + _tag("tipoDocumento", receita.comprador_tipo_documento or 2)
            + _tag("numeroDocumento", receita.comprador_documento or "")
            + _tag("orgaoExpedidor", receita.comprador_orgao or "")
            + _tag("UFEmissaoDocumento", receita.comprador_uf or "")
            + "</compradorMedicamento>"
        )
    if receita.paciente_idade is not None or receita.paciente_nome:
        paciente = "<pacienteMedicamento>"
        if receita.paciente_nome:
            paciente += _tag("nome", receita.paciente_nome)
        if receita.paciente_idade is not None:
            paciente += _tag("idade", receita.paciente_idade) + _tag("unidadeIdade", receita.paciente_unidade_idade or 1)
        if receita.paciente_sexo:
            paciente += _tag("sexo", receita.paciente_sexo)
        if receita.cid:
            paciente += _tag("cid", receita.cid)
        partes.append(paciente + "</pacienteMedicamento>")
    return "".join(partes)


def arquivo_movimentacao(db: Session, loja_id: UUID | None, inicio: date | None, fim: date | None) -> tuple[str, bytes]:
    """Arquivo de movimentação do período: entradas por nota, vendas com receita e perdas."""
    dados = resumo(db, loja_id, inicio, fim)
    _exigir_sem_bloqueio(dados.pendencias)
    loja = db.get(Loja, dados.loja_id)
    desde, ate = _limites(dados.inicio, dados.fim)
    linhas = _movimentos(db, loja.id, ate, desde)
    docs = _Documentos(db, [m for m, _ in linhas])

    entradas: dict[UUID, list] = defaultdict(list)
    vendas: dict[UUID, list] = defaultdict(list)
    perdas = []
    for movimento, produto in linhas:
        if movimento.tipo == "entrada" and (nota := docs.nota(movimento)) is not None:
            entradas[nota.id].append((movimento, produto, nota))
        elif movimento.tipo == "venda" and (venda := docs.venda(movimento)) is not None:
            if venda.status != "cancelada" and docs.receita(movimento) is not None:
                vendas[venda.id].append((movimento, produto, venda))
        elif movimento.tipo == "perda" and movimento.motivo_sngpc:
            perdas.append((movimento, produto))

    corpo = []
    for itens in entradas.values():
        nota = itens[0][2]
        corpo.append(
            "<entradaMedicamentos><notaFiscalEntradaMedicamento>"
            + _tag("numeroNotaFiscal", nota.numero)
            + _tag("tipoOperacaoNotaFiscal", 1)
            + _tag("dataNotaFiscal", nota.emitida_em.astimezone(FUSO).date().isoformat())
            + _tag("cnpjOrigem", nota.fornecedor.cnpj or "")
            + _tag("cnpjDestino", loja.cnpj)
            + "</notaFiscalEntradaMedicamento>"
            + "".join(
                f"<medicamentoEntrada>{_medicamento(p, m.lote.numero_lote, m.quantidade, com_classe=True)}</medicamentoEntrada>"
                for m, p, _ in itens
            )
            + _tag("dataRecebimentoMedicamento", itens[0][0].criado_em.astimezone(FUSO).date().isoformat())
            + "</entradaMedicamentos>"
        )
    for itens in vendas.values():
        movimento, _, venda = itens[0]
        receita = docs.receita(movimento)
        uso_prolongado = "S" if receita.uso_prolongado else "N"
        corpo.append(
            "<saidaMedicamentoVendaAoConsumidor>"
            + _receita_xml(receita)
            + "".join(
                f"<medicamentoVenda>{_medicamento(p, m.lote.numero_lote, m.quantidade, uso_prolongado=uso_prolongado)}"
                "</medicamentoVenda>"
                for m, p, _ in itens
            )
            + _tag("dataVendaMedicamento", venda.finalizada_em.astimezone(FUSO).date().isoformat())
            + "</saidaMedicamentoVendaAoConsumidor>"
        )
    for movimento, produto in perdas:
        corpo.append(
            "<saidaMedicamentoPerda>"
            + _tag("motivoPerdaMedicamento", movimento.motivo_sngpc)
            + f"<medicamentoPerda>{_medicamento(produto, movimento.lote.numero_lote, movimento.quantidade)}</medicamentoPerda>"
            + _tag("dataPerdaMedicamento", movimento.criado_em.astimezone(FUSO).date().isoformat())
            + "</saidaMedicamentoPerda>"
        )

    xml = (
        _cabecalho_xml("mensagemSNGPC")
        + "<cabecalho>"
        + _tag("cnpjEmissor", loja.cnpj)
        + _tag("cpfTransmissor", loja.responsavel_cpf)
        + _tag("dataInicio", dados.inicio.isoformat())
        + _tag("dataFim", dados.fim.isoformat())
        + "</cabecalho><corpo><medicamentos>"
        + "".join(corpo)
        + "</medicamentos><insumos></insumos></corpo></mensagemSNGPC>\n"
    )
    nome = f"sngpc-{loja.cnpj}-{dados.inicio:%Y%m%d}-{dados.fim:%Y%m%d}.xml"
    return nome, xml.encode("iso-8859-1", errors="replace")


def arquivo_inventario(db: Session, loja_id: UUID | None) -> tuple[str, bytes]:
    """Inventário de hoje: o saldo de cada lote de controlado na loja."""
    loja = loja_ou_matriz(db, loja_id)
    saldos = _saldos_atuais(db, loja.id)
    produtos = {s.produto_id: db.get(Produto, s.produto_id) for s in saldos}
    _exigir_sem_bloqueio(_pendencias(loja, [], _Documentos(db, []), list(produtos.values())))
    data = hoje()
    itens = "".join(
        f"<medicamentoEntrada>{_medicamento(produtos[s.produto_id], s.lote, s.quantidade, com_classe=True)}"
        "</medicamentoEntrada>"
        for s in saldos
    )
    xml = (
        _cabecalho_xml("mensagemSNGPCInventario")
        + "<cabecalho>"
        + _tag("cnpjEmissor", loja.cnpj)
        + _tag("cpfTransmissor", loja.responsavel_cpf)
        + _tag("data", data.isoformat())
        + "</cabecalho><corpo><medicamentos><entradaMedicamentos>"
        + itens
        + "</entradaMedicamentos></medicamentos><insumos></insumos></corpo></mensagemSNGPCInventario>\n"
    )
    return f"sngpc-inventario-{loja.cnpj}-{data:%Y%m%d}.xml", xml.encode("iso-8859-1", errors="replace")
