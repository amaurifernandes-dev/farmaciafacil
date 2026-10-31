"""Fechamento fiscal do mês: o que foi vendido e comprado, o que falta acertar e o pacote para o contador."""

import csv
import io
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, undefer

from app.modules.compras.models import NotaEntrada
from app.modules.fiscal.models import ConfiguracaoFiscal, NotaFiscal
from app.modules.fiscal.nfe_impostos import CSOSN_PARA_CST, ImpostosNota, ler_impostos
from app.modules.fiscal.schemas import (
    Fechamento,
    LinhaCfop,
    Pendencia,
    ReceitaPgdas,
    ResumoEntradas,
    ResumoSaidas,
)
from app.modules.fiscal.service import _ratear
from app.modules.lojas.models import Loja
from app.modules.lojas.service import matriz, obter_loja
from app.modules.produtos.models import Produto
from app.modules.vendas.models import Caixa, Venda
from app.shared.datas import FUSO
from app.shared.erros import ErroDeNegocio

ZERO = Decimal(0)
# PIS/COFINS monofásico: o fabricante já pagou (CST 04, comum em remédio). Não paga de novo no Simples.
PIS_COFINS_MONOFASICO = {"04"}
# ICMS já pago antes por substituição tributária: CSOSN 500 no Simples, CST 60 no regime normal.
ICMS_ST = {"500", "60", "10", "30", "70", "201", "202", "203"}


@dataclass
class ItemVendido:
    produto: Produto
    cfop: str
    cst_icms: str  # origem + CST (ou CSOSN, no Simples)
    cst_pis_cofins: str
    valor: Decimal  # já com o desconto da venda rateado


@dataclass
class VendaDoMes:
    venda: Venda
    nota: NotaFiscal | None
    itens: list[ItemVendido]


@dataclass
class EntradaDoMes:
    nota: NotaEntrada
    impostos: ImpostosNota


def _reais(valor: Decimal) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def periodo(mes: str) -> tuple[date, date]:
    try:
        inicio = date.fromisoformat(f"{mes}-01")
    except ValueError:
        raise ErroDeNegocio("Mês inválido. Use o formato AAAA-MM")
    fim = (inicio.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    return inicio, fim


def _limites(inicio: date, fim: date) -> tuple[datetime, datetime]:
    return datetime.combine(inicio, time(), FUSO), datetime.combine(fim + timedelta(days=1), time(), FUSO)


def configuracao(db: Session) -> ConfiguracaoFiscal:
    """A configuração salva, ou a padrão (Simples Nacional) para quem ainda não configurou."""
    return db.scalar(select(ConfiguracaoFiscal)) or ConfiguracaoFiscal(
        regime="simples", perfil_efd="A", cfop_padrao="5102", icms_situacao_tributaria_padrao="102",
        pis_cofins_situacao_tributaria_padrao="49",
    )


def loja_do_fechamento(db: Session, loja_id: UUID | None) -> Loja:
    return obter_loja(db, loja_id) if loja_id is not None else matriz(db)


def _situacao_icms(produto: Produto, config: ConfiguracaoFiscal) -> str:
    """CSOSN no Simples; no regime normal, um CSOSN que sobrou do cadastro vira o CST equivalente."""
    codigo = produto.icms_situacao_tributaria or config.icms_situacao_tributaria_padrao
    if config.regime != "simples" and len(codigo) == 3:
        return CSOSN_PARA_CST.get(codigo, "90")
    return codigo


def vendas_do_mes(db: Session, loja: Loja, inicio: date, fim: date, config: ConfiguracaoFiscal) -> list[VendaDoMes]:
    de, ate = _limites(inicio, fim)
    # Caixa sem loja (antigo) é da matriz.
    da_loja = Caixa.loja_id == loja.id if not loja.matriz else (Caixa.loja_id == loja.id) | Caixa.loja_id.is_(None)
    vendas = db.scalars(
        select(Venda)
        .join(Caixa, Caixa.id == Venda.caixa_id)
        .where(da_loja, Venda.finalizada_em >= de, Venda.finalizada_em < ate,
               Venda.status.in_(("finalizada", "cancelada")))
        .order_by(Venda.numero)
    ).all()
    notas = {
        n.venda_id: n
        for n in db.scalars(select(NotaFiscal).where(NotaFiscal.venda_id.in_([v.id for v in vendas])))
    } if vendas else {}
    produtos = {
        p.id: p
        for p in db.scalars(select(Produto).where(Produto.id.in_({i.produto_id for v in vendas for i in v.itens})))
    } if vendas else {}

    resultado = []
    for venda in vendas:
        # O desconto dado no total da venda é dividido entre os itens, como na NFC-e.
        desconto_da_venda = venda.desconto - sum((i.desconto for i in venda.itens), ZERO)
        rateio = _ratear(desconto_da_venda, [i.total for i in venda.itens])
        taxas = _ratear(venda.taxa_entrega, [i.total for i in venda.itens])  # entrega: outras despesas
        itens = []
        for item, desconto, taxa in zip(venda.itens, rateio, taxas):
            produto = produtos[item.produto_id]
            itens.append(
                ItemVendido(
                    produto=produto,
                    cfop=produto.cfop or config.cfop_padrao,
                    cst_icms=produto.icms_origem + _situacao_icms(produto, config),
                    cst_pis_cofins=produto.pis_cofins_situacao_tributaria or config.pis_cofins_situacao_tributaria_padrao,
                    valor=item.total - desconto + taxa,
                )
            )
        resultado.append(VendaDoMes(venda=venda, nota=notas.get(venda.id), itens=itens))
    return resultado


def entradas_do_mes(db: Session, loja: Loja, inicio: date, fim: date) -> list[EntradaDoMes]:
    """Notas de compra que entraram no estoque no mês (a data de entrada é a da conferência)."""
    de, ate = _limites(inicio, fim)
    notas = db.scalars(
        select(NotaEntrada)
        .options(undefer(NotaEntrada.xml))
        .where(NotaEntrada.loja_id == loja.id, NotaEntrada.status == "confirmada",
               NotaEntrada.confirmada_em >= de, NotaEntrada.confirmada_em < ate)
        .order_by(NotaEntrada.confirmada_em)
    ).all()
    return [EntradaDoMes(nota=n, impostos=ler_impostos(n.xml)) for n in notas]


def _pendencias(db: Session, loja: Loja, inicio: date, fim: date, config: ConfiguracaoFiscal,
                vendas: list[VendaDoMes]) -> list[Pendencia]:
    pendencias = []
    finalizadas = [v for v in vendas if v.venda.status == "finalizada"]
    sem_nota = [v for v in finalizadas if v.nota is None or v.nota.status not in ("autorizada", "cancelada")]
    if sem_nota:
        valor = sum((v.venda.total for v in sem_nota), ZERO)
        pendencias.append(Pendencia(
            tipo="vendas_sem_nfce", quantidade=len(sem_nota),
            texto=f"{len(sem_nota)} venda(s) sem NFC-e autorizada, somando {_reais(valor)}. "
            "Reenvie em Vendas antes de fechar o mês.",
        ))
    sem_ncm = {i.produto.nome for v in finalizadas for i in v.itens if not i.produto.ncm}
    if sem_ncm:
        pendencias.append(Pendencia(
            tipo="produtos_sem_ncm", quantidade=len(sem_ncm),
            texto=f"{len(sem_ncm)} produto(s) vendido(s) sem NCM ({', '.join(sorted(sem_ncm)[:5])}"
            f"{' e outros' if len(sem_ncm) > 5 else ''}). Cadastre o NCM em Produtos.",
        ))
    de, ate = _limites(inicio, fim)
    pendentes = db.scalar(
        select(func.count()).select_from(NotaEntrada)
        .where(NotaEntrada.loja_id == loja.id, NotaEntrada.status == "pendente", NotaEntrada.emitida_em < ate)
    )
    if pendentes:
        pendencias.append(Pendencia(
            tipo="notas_entrada_pendentes", quantidade=pendentes,
            texto=f"{pendentes} nota(s) de compra importada(s) e ainda não conferida(s). Confira em Compras.",
        ))
    if config.regime != "simples":
        faltando = [nome for nome, valor in (("inscrição estadual", loja.inscricao_estadual),
                                             ("código do município (IBGE)", loja.codigo_municipio)) if not valor]
        if faltando:
            pendencias.append(Pendencia(
                tipo="loja_incompleta", quantidade=len(faltando),
                texto=f"Falta na loja {loja.nome}: {' e '.join(faltando)}. Complete em Minha farmácia.",
            ))
        if not (config.contador_nome and config.contador_cpf and config.contador_crc):
            pendencias.append(Pendencia(
                tipo="contador", quantidade=1,
                texto="Cadastre nome, CPF e CRC do contador nos dados fiscais (vão no SPED).",
            ))
        com_csosn = {i.produto.nome for v in finalizadas for i in v.itens
                     if len(i.produto.icms_situacao_tributaria or config.icms_situacao_tributaria_padrao) == 3}
        if com_csosn:
            pendencias.append(Pendencia(
                tipo="csosn_no_regime_normal", quantidade=len(com_csosn),
                texto=f"{len(com_csosn)} produto(s) vendido(s) ainda com CSOSN do Simples (ex.: 102, 500). O sistema usou "
                "o CST equivalente; confira com o contador e ajuste o padrão fiscal e os produtos.",
            ))
        cst_tributado = {i.produto.nome for v in finalizadas for i in v.itens if i.cst_icms[1:] in ("00", "20")}
        if cst_tributado:
            pendencias.append(Pendencia(
                tipo="icms_sem_aliquota", quantidade=len(cst_tributado),
                texto="Há vendas com CST 00/20, mas o sistema ainda não guarda a alíquota de ICMS do produto: "
                "o débito dessas vendas sai zerado no SPED e o contador precisa lançar.",
            ))
    return pendencias


def _por_cfop(linhas: list[tuple[str, str, Decimal, Decimal, Decimal]]) -> list[LinhaCfop]:
    soma: dict[tuple[str, str], list[Decimal]] = defaultdict(lambda: [ZERO, ZERO, ZERO])
    for cfop, cst, valor, icms, icms_st in linhas:
        soma[(cfop, cst)][0] += valor
        soma[(cfop, cst)][1] += icms
        soma[(cfop, cst)][2] += icms_st
    return [LinhaCfop(cfop=c, cst=s, valor=v[0], icms=v[1], icms_st=v[2]) for (c, s), v in sorted(soma.items())]


def pgdas(vendas: list[VendaDoMes]) -> ReceitaPgdas:
    """Receita do mês separada como o PGDAS-D pede: o que já teve ICMS-ST e PIS/COFINS monofásico paga menos."""
    partes = defaultdict(lambda: ZERO)
    for venda in vendas:
        if venda.venda.status != "finalizada":
            continue
        for item in venda.itens:
            st = item.cst_icms[1:] in ICMS_ST
            monofasico = item.cst_pis_cofins in PIS_COFINS_MONOFASICO
            chave = "st_e_monofasico" if st and monofasico else "icms_st" if st else "monofasico" if monofasico else "normal"
            partes[chave] += item.valor
    return ReceitaPgdas(
        normal=partes["normal"], icms_st=partes["icms_st"], monofasico=partes["monofasico"],
        st_e_monofasico=partes["st_e_monofasico"], total=sum(partes.values(), ZERO),
    )


def fechamento(db: Session, mes: str, loja_id: UUID | None) -> Fechamento:
    inicio, fim = periodo(mes)
    loja = loja_do_fechamento(db, loja_id)
    config = configuracao(db)
    vendas = vendas_do_mes(db, loja, inicio, fim, config)
    entradas = entradas_do_mes(db, loja, inicio, fim)

    finalizadas = [v for v in vendas if v.venda.status == "finalizada"]
    autorizadas = [v for v in vendas if v.nota is not None and v.nota.status == "autorizada"]
    saidas = _por_cfop([
        (i.cfop, i.cst_icms, i.valor, ZERO, ZERO) for v in autorizadas for i in v.itens
    ])
    linhas_entrada = [
        (item.cfop_entrada, item.cst_icms, item.valor_operacao, item.icms, item.icms_st)
        for e in entradas for item in e.impostos.itens.values()
    ]
    return Fechamento(
        mes=mes,
        inicio=inicio,
        fim=fim,
        loja_id=loja.id,
        loja_nome=loja.nome,
        cnpj=loja.cnpj,
        regime=config.regime,
        saidas=ResumoSaidas(
            vendas=len(finalizadas),
            total_vendido=sum((v.venda.total for v in finalizadas), ZERO),
            nfce_autorizadas=len(autorizadas),
            valor_nfce=sum((v.venda.total for v in autorizadas), ZERO),
            nfce_canceladas=sum(1 for v in vendas if v.nota is not None and v.nota.status == "cancelada"),
            por_cfop=saidas,
        ),
        entradas=ResumoEntradas(
            notas=len(entradas),
            valor_total=sum((e.impostos.total for e in entradas), ZERO),
            icms=sum((e.impostos.icms for e in entradas), ZERO),
            icms_st=sum((e.impostos.icms_st for e in entradas), ZERO),
            ipi=sum((e.impostos.ipi for e in entradas), ZERO),
            por_cfop=_por_cfop(linhas_entrada),
        ),
        pgdas=pgdas(vendas),
        pendencias=_pendencias(db, loja, inicio, fim, config, vendas),
        sped_disponivel=config.regime != "simples",
    )


# --- Pacote para o contador ---

def _csv(cabecalho: list[str], linhas: list[list]) -> str:
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";")
    escritor.writerow(cabecalho)
    for linha in linhas:
        escritor.writerow([f"{c:.2f}".replace(".", ",") if isinstance(c, Decimal) else c for c in linha])
    return "﻿" + saida.getvalue()  # BOM: o Excel abre com acento certo


def pacote(db: Session, mes: str, loja_id: UUID | None) -> tuple[str, bytes]:
    """ZIP com o resumo, a lista das NFC-e, os XMLs das compras e o SPED (no regime normal)."""
    from app.modules.fiscal.sped import gerar_sped  # evita import circular

    resumo = fechamento(db, mes, loja_id)
    inicio, fim = periodo(mes)
    loja = loja_do_fechamento(db, loja_id)
    config = configuracao(db)
    vendas = vendas_do_mes(db, loja, inicio, fim, config)
    entradas = entradas_do_mes(db, loja, inicio, fim)

    arquivo = io.BytesIO()
    with zipfile.ZipFile(arquivo, "w", zipfile.ZIP_DEFLATED) as zip_:
        linhas = [["Saída", l.cfop, l.cst, l.valor, l.icms, l.icms_st] for l in resumo.saidas.por_cfop]
        linhas += [["Entrada", l.cfop, l.cst, l.valor, l.icms, l.icms_st] for l in resumo.entradas.por_cfop]
        zip_.writestr("resumo-por-cfop.csv", _csv(["Tipo", "CFOP", "CST", "Valor", "ICMS", "ICMS ST"], linhas))
        p = resumo.pgdas
        zip_.writestr("receita-pgdas.csv", _csv(
            ["Receita", "Valor"],
            [["Sem ST e sem monofásico", p.normal], ["Com ICMS-ST", p.icms_st],
             ["Com PIS/COFINS monofásico", p.monofasico], ["Com ICMS-ST e monofásico", p.st_e_monofasico],
             ["Total", p.total]],
        ))
        zip_.writestr("nfce-do-mes.csv", _csv(
            ["Venda", "Data", "Número", "Série", "Chave", "Situação", "Valor", "XML"],
            [[v.venda.numero, v.venda.finalizada_em.astimezone(FUSO).strftime("%d/%m/%Y %H:%M"),
              v.nota.numero if v.nota else "", v.nota.serie if v.nota else "", v.nota.chave if v.nota else "",
              v.nota.status if v.nota else "sem nota", v.venda.total, v.nota.url_xml if v.nota else ""]
             for v in vendas],
        ))
        for entrada in entradas:
            zip_.writestr(f"xml-compras/{entrada.nota.chave}.xml", entrada.nota.xml)
        if resumo.pendencias:
            zip_.writestr("pendencias.txt", "\n".join(f"- {p.texto}" for p in resumo.pendencias) + "\n")
        if config.regime != "simples":
            nome_sped, conteudo = gerar_sped(db, mes, loja_id)
            zip_.writestr(nome_sped, conteudo)
    return f"fechamento-{loja.cnpj}-{mes}.zip", arquivo.getvalue()

