"""SPED Fiscal (EFD ICMS/IPI) do mês, para quem está no regime normal (lucro presumido ou real).

O arquivo sai pronto para o contador abrir no PVA da Receita, conferir e transmitir. Traz as compras
(C100/C170/C190, lidas dos XMLs guardados), as NFC-e do mês (C100/C190) e a apuração do ICMS (E110).
"""

from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.compras.models import NotaEntradaItem
from app.modules.fiscal.fechamento import (
    EntradaDoMes,
    VendaDoMes,
    configuracao,
    entradas_do_mes,
    loja_do_fechamento,
    periodo,
    vendas_do_mes,
)
from app.modules.fiscal.models import ConfiguracaoFiscal
from app.modules.fiscal.nfe_impostos import CSOSN_PARA_CST, ImpostoItem
from app.modules.lojas.models import Loja
from app.modules.produtos.models import Produto
from app.shared.datas import FUSO
from app.shared.erros import ErroDeNegocio

ZERO = Decimal(0)
CENTAVO = Decimal("0.01")
# Versão do leiaute pelo ano do período (Guia Prático da EFD ICMS/IPI).
VERSOES = {2024: "018", 2025: "019", 2026: "020"}


def _versao(ano: int) -> str:
    return VERSOES.get(ano, VERSOES[max(VERSOES)] if ano > max(VERSOES) else VERSOES[min(VERSOES)])


def _dia(valor: date | datetime | None) -> str:
    if valor is None:
        return ""
    if isinstance(valor, datetime):
        valor = valor.astimezone(FUSO).date()
    return valor.strftime("%d%m%Y")


def _num(valor: Decimal | None, casas: int = 2) -> str:
    if valor is None:
        return ""
    return str(valor.quantize(Decimal(1).scaleb(-casas), ROUND_HALF_UP)).replace(".", ",")


def _txt(valor: str | None, tamanho: int | None = None) -> str:
    texto = " ".join((valor or "").replace("|", " ").split())
    return texto[:tamanho] if tamanho else texto


def _cst(cst_icms: str) -> str:
    """Origem + CST com 3 dígitos. Se o produto ainda tem CSOSN (do Simples), usa o CST equivalente."""
    origem, codigo = cst_icms[:1], cst_icms[1:]
    if len(codigo) == 3:
        codigo = CSOSN_PARA_CST.get(codigo, "90")
    return origem + codigo


class Arquivo:
    def __init__(self) -> None:
        self.linhas: list[str] = []
        self.contagem: Counter[str] = Counter()

    def __call__(self, registro: str, *campos) -> None:
        self.linhas.append("|" + "|".join([registro, *("" if c is None else str(c) for c in campos)]) + "|")
        self.contagem[registro] += 1

    def bloco(self, letra: str) -> int:
        return sum(q for r, q in self.contagem.items() if r[0] == letra)


def _itens_da_entrada(entrada: EntradaDoMes) -> list[tuple[ImpostoItem, list[NotaEntradaItem]]]:
    """Junta cada item do XML com os itens guardados (um produto com dois lotes vira dois itens guardados)."""
    guardados: dict[str, list[NotaEntradaItem]] = defaultdict(list)
    for item in entrada.nota.itens:
        guardados[item.codigo_fornecedor].append(item)
    resultado = []
    for imposto in sorted(entrada.impostos.itens.values(), key=lambda i: i.numero):
        fila = guardados[imposto.codigo[:60]]
        usados: list[NotaEntradaItem] = []
        while fila and sum((u.quantidade for u in usados), ZERO) < imposto.quantidade:
            usados.append(fila.pop(0))
        resultado.append((imposto, usados))
    return resultado


def gerar_sped(db: Session, mes: str, loja_id: UUID | None) -> tuple[str, bytes]:
    config = configuracao(db)
    if config.regime == "simples":
        raise ErroDeNegocio(
            "Farmácia do Simples Nacional não entrega o SPED Fiscal. Use o pacote do mês para o contador."
        )
    inicio, fim = periodo(mes)
    loja = loja_do_fechamento(db, loja_id)
    vendas = vendas_do_mes(db, loja, inicio, fim, config)
    entradas = entradas_do_mes(db, loja, inicio, fim)
    conteudo = _montar(db, loja, config, inicio, fim, vendas, entradas)
    return f"SPED-EFD-{loja.cnpj}-{inicio:%Y%m}.txt", conteudo.encode("latin-1", errors="replace")


def _montar(db: Session, loja: Loja, config: ConfiguracaoFiscal, inicio: date, fim: date,
            vendas: list[VendaDoMes], entradas: list[EntradaDoMes]) -> str:
    sped = Arquivo()
    itens_das_entradas = [(e, _itens_da_entrada(e)) for e in entradas]
    produto_ids = {u.produto_id for _, itens in itens_das_entradas for _, usados in itens for u in usados
                   if u.produto_id}
    produtos = {p.id: p for p in db.scalars(select(Produto).where(Produto.id.in_(produto_ids)))} if produto_ids else {}

    # --- Bloco 0: abertura e cadastros ---
    sped("0000", _versao(inicio.year), "0", _dia(inicio), _dia(fim), _txt(loja.razao_social, 100), loja.cnpj, "",
         loja.uf, _txt(loja.inscricao_estadual), loja.codigo_municipio or "", "", "", config.perfil_efd, "1")
    sped("0001", "0")
    sped("0005", _txt(loja.nome_fantasia, 60), loja.cep or "", _txt(loja.endereco, 60), "", "",
         _txt(loja.bairro, 60), _txt(loja.telefone, 11), "", _txt(loja.email))
    sped("0100", _txt(config.contador_nome, 100), config.contador_cpf or "", _txt(config.contador_crc), "", "", "",
         "", "", "", "", "", _txt(config.contador_email), "")

    participantes = {}
    for entrada, _ in itens_das_entradas:
        emitente = entrada.impostos.emitente
        participantes.setdefault(emitente.cnpj, emitente)
    for cnpj, p in sorted(participantes.items()):
        sped("0150", f"F{cnpj}", _txt(p.nome, 100), "01058", cnpj, "", _txt(p.inscricao_estadual),
             p.codigo_municipio or "", "", _txt(p.endereco, 60), _txt(p.numero, 10), "", _txt(p.bairro, 60))

    usados_por_produto = sorted(produtos.values(), key=lambda p: p.nome)
    for unidade in sorted({p.unidade for p in usados_por_produto}):
        sped("0190", unidade, unidade)
    for p in usados_por_produto:
        sped("0200", p.id.hex, _txt(p.nome, 200), p.ean or "", "", p.unidade, "00", p.ncm or "", "", "", "", "",
             p.cest or "")
    sped("0990", sped.bloco("0") + 1)

    # Bloco B (ISS do DF): sem dados.
    sped("B001", "1")
    sped("B990", 2)

    # --- Bloco C: notas de mercadoria ---
    tem_notas = bool(entradas) or any(v.nota and v.nota.chave for v in vendas)
    sped("C001", "0" if tem_notas else "1")
    creditos = ZERO
    for entrada, itens in itens_das_entradas:
        nota, imp = entrada.nota, entrada.impostos
        sped("C100", "0", "1", f"F{imp.emitente.cnpj}", "55", "00", str(nota.serie), nota.numero, nota.chave,
             _dia(nota.emitida_em), _dia(nota.confirmada_em), _num(imp.total), "0" if imp.a_vista else "1",
             _num(imp.desconto), _num(ZERO), _num(imp.valor_produtos), "0" if imp.frete else "9", _num(imp.frete),
             _num(imp.seguro), _num(imp.outras), _num(imp.base_icms), _num(imp.icms), _num(imp.base_icms_st),
             _num(imp.icms_st), _num(imp.ipi), _num(imp.pis), _num(imp.cofins), "", "")
        resumo: dict[tuple[str, str, Decimal], list[Decimal]] = defaultdict(lambda: [ZERO] * 6)
        for numero, (item, usados) in enumerate(itens, start=1):
            produto = produtos.get(usados[0].produto_id) if usados else None
            quantidade = sum((u.quantidade * u.fator for u in usados), ZERO) if usados else item.quantidade
            cst, cfop = _cst(item.cst_icms), item.cfop_entrada
            sped("C170", numero, produto.id.hex if produto else _txt(item.codigo, 60), "", _num(quantidade, 5),
                 produto.unidade if produto else "UN", _num(item.valor_produto), _num(item.desconto), "0", cst, cfop,
                 "", _num(item.base_icms), _num(item.aliquota_icms), _num(item.icms), _num(item.base_icms_st), "",
                 _num(item.icms_st), "", "", "", "", "", _num(item.ipi), "", "", "", "", "", "", "", "", "", "", "",
                 "", "", "")
            soma = resumo[(cst, cfop, item.aliquota_icms)]
            for i, valor in enumerate((item.valor_operacao, item.base_icms, item.icms, item.base_icms_st,
                                       item.icms_st, item.ipi)):
                soma[i] += valor
        for (cst, cfop, aliquota), s in sorted(resumo.items()):
            sped("C190", cst, cfop, _num(aliquota), _num(s[0]), _num(s[1]), _num(s[2]), _num(s[3]), _num(s[4]),
                 _num(ZERO), _num(s[5]), "")
            creditos += s[2]

    debitos = ZERO
    for venda in vendas:
        nota = venda.nota
        if nota is None or not nota.chave or nota.status not in ("autorizada", "cancelada"):
            continue
        if nota.status == "cancelada" or venda.venda.status == "cancelada":
            sped("C100", "1", "0", "", "65", "02", nota.serie or "", nota.numero or "", nota.chave,
                 *([""] * 20))
            continue
        v = venda.venda
        sped("C100", "1", "0", "", "65", "00", nota.serie or "", nota.numero or "", nota.chave,
             _dia(nota.autorizada_em or v.finalizada_em), _dia(v.finalizada_em), _num(v.total), "0",
             _num(v.desconto), _num(ZERO), _num(v.subtotal), "9", _num(ZERO), _num(ZERO),
             _num(v.taxa_entrega),
             _num(ZERO), _num(ZERO), "", "", "", "", "", "", "")
        resumo_saida: dict[tuple[str, str], Decimal] = defaultdict(lambda: ZERO)
        for item in venda.itens:
            resumo_saida[(_cst(item.cst_icms), item.cfop)] += item.valor
        for (cst, cfop), valor in sorted(resumo_saida.items()):
            # A alíquota do ICMS na saída ainda não é guardada: o débito vai zerado e o contador ajusta no PVA.
            sped("C190", cst, cfop, _num(ZERO), _num(valor), _num(ZERO), _num(ZERO), _num(ZERO), _num(ZERO),
                 _num(ZERO), _num(ZERO), "")
    sped("C990", sped.bloco("C") + 1)

    # Bloco D (transporte e comunicação): sem dados.
    sped("D001", "1")
    sped("D990", 2)

    # --- Bloco E: apuração do ICMS ---
    sped("E001", "0")
    sped("E100", _dia(inicio), _dia(fim))
    saldo = debitos - creditos
    recolher = max(saldo, ZERO)
    credor = max(-saldo, ZERO)
    sped("E110", _num(debitos), _num(ZERO), _num(ZERO), _num(ZERO), _num(creditos), _num(ZERO), _num(ZERO),
         _num(ZERO), _num(ZERO), _num(recolher), _num(ZERO), _num(recolher), _num(credor), _num(ZERO))
    sped("E990", sped.bloco("E") + 1)

    # Blocos G (CIAP), H (inventário, entregue em fevereiro) e K (produção): sem dados.
    for letra in "GHK":
        sped(f"{letra}001", "1")
        sped(f"{letra}990", 2)

    sped("1001", "0")
    sped("1010", *(["N"] * 13))
    sped("1990", sped.bloco("1") + 1)

    # --- Bloco 9: totais de linhas ---
    sped("9001", "0")
    registros = sorted(sped.contagem) + ["9900", "9990", "9999"]
    for registro in registros:
        # O próprio 9900 conta todas as linhas 9900, inclusive a dele.
        quantidade = len(registros) if registro == "9900" else sped.contagem[registro] or 1
        sped("9900", registro, quantidade)
    sped("9990", sped.bloco("9") + 2)
    sped("9999", len(sped.linhas) + 1)
    return "\r\n".join(sped.linhas) + "\r\n"
