"""Ferramentas de relatório do assistente: usam os mesmos cálculos das telas de Relatórios e Estoque."""

from datetime import date, timedelta
from decimal import Decimal

from app.modules.assistente.contexto import Contexto, ErroDaFerramenta
from app.modules.estoque import service as estoque
from app.modules.relatorios import service as relatorios
from app.shared.datas import hoje

PERIODOS = (
    "hoje", "ontem", "esta_semana", "semana_passada", "este_mes", "mes_passado",
    "ultimos_7_dias", "ultimos_30_dias", "este_ano", "personalizado",
)
NOMES_PERIODOS = {
    "hoje": "hoje", "ontem": "ontem", "esta_semana": "esta semana", "semana_passada": "semana passada",
    "este_mes": "este mês", "mes_passado": "mês passado", "ultimos_7_dias": "últimos 7 dias",
    "ultimos_30_dias": "últimos 30 dias", "este_ano": "este ano",
}
FORMAS = {
    "dinheiro": "Dinheiro", "debito": "Débito", "credito": "Crédito", "pix": "Pix", "prazo": "Fiado / a prazo",
    "convenio": "Convênio", "popular": "Farmácia Popular", "vale": "Vale-troca",
}
SEM_PERMISSAO = "Só gerente e administrador veem os números de vendas. Peça ao gerente."


def _periodo_schema() -> dict:
    return {
        "periodo": {
            "type": "string",
            "enum": list(PERIODOS),
            "description": "Período. Semana começa na segunda. Use personalizado com inicio e fim para datas exatas.",
        },
        "inicio": {"type": ["string", "null"], "description": "AAAA-MM-DD, só com periodo personalizado"},
        "fim": {"type": ["string", "null"], "description": "AAAA-MM-DD, só com periodo personalizado"},
    }


FERRAMENTAS_GERENCIA: list[dict] = [
    {
        "name": "relatorio_vendas",
        "description": (
            "Quanto a farmácia vendeu num período (todas as lojas): faturamento já sem devoluções, número de "
            "vendas, ticket médio, lucro bruto e margem, comparação com o período anterior de mesmo tamanho, "
            "vendas por forma de pagamento e por vendedor. Use para \"quanto vendi hoje\", \"como foi o mês\", "
            "\"quem vendeu mais\"."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": _periodo_schema(),
            "required": ["periodo", "inicio", "fim"],
            "additionalProperties": False,
        },
    },
    {
        "name": "mais_vendidos",
        "description": (
            "Os produtos que mais venderam num período, por faturamento, quantidade ou lucro, com a curva ABC. "
            "Use também para \"o que dá mais lucro\"."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                **_periodo_schema(),
                "ordenar_por": {"type": "string", "enum": ["faturamento", "quantidade", "lucro"]},
                "limite": {"type": "integer", "description": "Quantos produtos mostrar (até 20)"},
            },
            "required": ["periodo", "inicio", "fim", "ordenar_por", "limite"],
            "additionalProperties": False,
        },
    },
    {
        "name": "produtos_parados",
        "description": "Produtos com estoque que não vendem há N dias (ou nunca venderam), com o dinheiro parado.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"dias": {"type": "integer", "description": "Sem venda há quantos dias (padrão 60)"}},
            "required": ["dias"],
            "additionalProperties": False,
        },
    },
]

FERRAMENTAS_ESTOQUE: list[dict] = [
    {
        "name": "alertas_estoque",
        "description": (
            "Produtos acabando (abaixo do estoque mínimo, por loja), lotes vencendo nos próximos N dias e lotes "
            "já vencidos com saldo. Use para \"o que está acabando\", \"o que preciso comprar\", \"o que vence\"."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo": {"type": "string", "enum": ["acabando", "vencendo", "vencidos", "todos"]},
                "dias": {"type": "integer", "description": "Para vencendo: vence em até quantos dias (padrão 60)"},
            },
            "required": ["tipo", "dias"],
            "additionalProperties": False,
        },
    },
]


def reais(valor: Decimal | int | None) -> str:
    if valor is None:
        return "-"
    texto = f"{Decimal(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def _qtd(valor: Decimal) -> str:
    return f"{Decimal(valor).normalize():f}".replace(".", ",")


def _pct(valor: Decimal | None) -> str:
    return "-" if valor is None else f"{Decimal(valor):.1f}%".replace(".", ",")


def _data(d: date) -> str:
    return f"{d:%d/%m/%Y}"


def _intervalo(ini: date, fi: date) -> str:
    return _data(ini) if ini == fi else f"{_data(ini)} a {_data(fi)}"


def resolver_periodo(periodo: str, inicio: str | None, fim: str | None, base: date | None = None) -> tuple[date, date, str]:
    """Transforma o período falado em datas. Devolve (início, fim, nome para mostrar)."""
    dia = base or hoje()
    segunda = dia - timedelta(days=dia.weekday())
    primeiro_do_mes = dia.replace(day=1)
    if periodo == "personalizado":
        try:
            ini, fi = date.fromisoformat(inicio or ""), date.fromisoformat(fim or inicio or "")
        except ValueError:
            raise ErroDaFerramenta("Para período personalizado, informe inicio e fim no formato AAAA-MM-DD.")
        if ini > fi:
            raise ErroDaFerramenta("O início do período não pode ser depois do fim.")
        if (fi - ini).days > 366:
            raise ErroDaFerramenta("Escolha um período de até um ano.")
        nome = _data(ini) if ini == fi else f"{_data(ini)} a {_data(fi)}"
        return ini, fi, nome
    intervalos = {
        "hoje": (dia, dia),
        "ontem": (dia - timedelta(days=1), dia - timedelta(days=1)),
        "esta_semana": (segunda, dia),
        "semana_passada": (segunda - timedelta(days=7), segunda - timedelta(days=1)),
        "este_mes": (primeiro_do_mes, dia),
        "mes_passado": ((primeiro_do_mes - timedelta(days=1)).replace(day=1), primeiro_do_mes - timedelta(days=1)),
        "ultimos_7_dias": (dia - timedelta(days=6), dia),
        "ultimos_30_dias": (dia - timedelta(days=29), dia),
        "este_ano": (dia.replace(month=1, day=1), dia),
    }
    if periodo not in intervalos:
        raise ErroDaFerramenta(f"Período desconhecido: {periodo}")
    ini, fi = intervalos[periodo]
    return ini, fi, NOMES_PERIODOS[periodo]


def _exigir_gerente(ctx: Contexto) -> None:
    if not ctx.gerente:
        raise ErroDaFerramenta(SEM_PERMISSAO)


def _variacao(atual: Decimal, anterior: Decimal) -> Decimal | None:
    if not anterior:
        return None
    return ((atual - anterior) / anterior * 100).quantize(Decimal("0.1"))


def relatorio_vendas(ctx: Contexto, periodo: str, inicio: str | None, fim: str | None) -> dict:
    _exigir_gerente(ctx)
    ini, fi, nome = resolver_periodo(periodo, inicio, fim)
    rel = relatorios.vendas(ctx.db, ini, fi, None)
    r, a = rel.resumo, rel.anterior
    variacao = _variacao(r.faturamento, a.faturamento)
    formas = [{"forma": FORMAS.get(f.forma, f.forma), "valor": reais(f.valor)} for f in rel.por_forma if f.valor]
    vendedores = [
        {"nome": o.nome, "vendas": o.quantidade, "total": reais(o.total)} for o in rel.por_operador[:5]
    ]
    ctx.cartoes.append({
        "tipo": "vendas",
        "titulo": f"Vendas de {nome}" if periodo in ("hoje", "ontem") else f"Vendas: {nome}",
        "periodo": _intervalo(ini, fi),
        "indicadores": [
            {"rotulo": "Faturamento", "valor": reais(r.faturamento)},
            {"rotulo": "Vendas", "valor": str(r.quantidade)},
            {"rotulo": "Ticket médio", "valor": reais(r.ticket_medio)},
            {"rotulo": "Lucro bruto", "valor": f"{reais(r.lucro_bruto)} ({_pct(r.margem)})"},
        ],
        "variacao": None if variacao is None else float(variacao),
        "anterior": reais(a.faturamento),
        "comparado_com": "ontem" if periodo == "hoje" else "o período anterior",
        "formas": formas,
        "vendedores": vendedores,
        "rota": "/relatorios",
    })
    return {
        "periodo": nome,
        "de": ini.isoformat(),
        "ate": fi.isoformat(),
        "faturamento": reais(r.faturamento),
        "vendas": r.quantidade,
        "ticket_medio": reais(r.ticket_medio),
        "lucro_bruto": reais(r.lucro_bruto),
        "margem": _pct(r.margem),
        "descontos": reais(r.descontos + r.descontos_promocao),
        "devolucoes": {"quantidade": r.devolucoes, "valor": reais(r.valor_devolvido)},
        "canceladas": {"quantidade": r.canceladas, "valor": reais(r.valor_cancelado)},
        "itens_sem_custo": r.itens_sem_custo,
        "periodo_anterior": {"faturamento": reais(a.faturamento), "vendas": a.quantidade},
        "variacao_faturamento": None if variacao is None else _pct(variacao),
        "por_forma": formas,
        "por_vendedor": vendedores,
        "aviso": "A tela já mostra um cartão com estes números: responda com um resumo de uma ou duas frases.",
    }


def mais_vendidos(
    ctx: Contexto, periodo: str, inicio: str | None, fim: str | None, ordenar_por: str, limite: int
) -> dict:
    _exigir_gerente(ctx)
    ini, fi, nome = resolver_periodo(periodo, inicio, fim)
    rel = relatorios.produtos(ctx.db, ini, fi, None)
    chave = {
        "faturamento": lambda p: p.faturamento,
        "quantidade": lambda p: p.quantidade,
        "lucro": lambda p: p.lucro if p.lucro is not None else Decimal("-1e18"),
    }[ordenar_por]
    produtos = sorted(rel.produtos, key=chave, reverse=True)[: max(1, min(limite, 20))]
    linhas = [
        [p.nome, _qtd(p.quantidade), reais(p.faturamento), reais(p.lucro), p.curva] for p in produtos
    ]
    ctx.cartoes.append({
        "tipo": "tabela",
        "titulo": f"Mais vendidos por {ordenar_por}: {nome}",
        "subtitulo": f"{_intervalo(ini, fi)} · faturamento total {reais(rel.faturamento)}",
        "colunas": [
            {"rotulo": "Produto", "num": False}, {"rotulo": "Qtd.", "num": True},
            {"rotulo": "Vendido", "num": True}, {"rotulo": "Lucro", "num": True}, {"rotulo": "Curva", "num": False},
        ],
        "linhas": linhas,
        "vazio": "Nenhuma venda no período.",
        "rota": "/relatorios",
    })
    return {
        "periodo": nome,
        "faturamento_total": reais(rel.faturamento),
        "produtos": [
            {"nome": p.nome, "quantidade": _qtd(p.quantidade), "vendido": reais(p.faturamento),
             "lucro": reais(p.lucro), "margem": _pct(p.margem), "participacao": _pct(p.participacao),
             "curva": p.curva}
            for p in produtos
        ],
        "aviso": "A tela já mostra a tabela: destaque só os primeiros e algo que chame atenção.",
    }


def produtos_parados(ctx: Contexto, dias: int) -> dict:
    _exigir_gerente(ctx)
    dias = max(7, min(dias or 60, 730))
    rel = relatorios.parados(ctx.db, dias, None)
    produtos = rel.produtos[:20]
    ctx.cartoes.append({
        "tipo": "tabela",
        "titulo": f"Sem venda há {dias} dias ou mais",
        "subtitulo": f"{len(rel.produtos)} produtos · {reais(rel.valor_total)} parados no estoque (pelo custo)",
        "colunas": [
            {"rotulo": "Produto", "num": False}, {"rotulo": "Estoque", "num": True},
            {"rotulo": "Parado", "num": True}, {"rotulo": "Última venda", "num": False},
        ],
        "linhas": [
            [p.nome, _qtd(p.saldo), reais(p.valor_parado),
             f"há {p.dias_parado} dias" if p.dias_parado is not None else "nunca vendeu"]
            for p in produtos
        ],
        "vazio": "Nenhum produto parado.",
        "rota": "/relatorios",
    })
    return {
        "dias": dias,
        "quantidade": len(rel.produtos),
        "valor_parado": reais(rel.valor_total),
        "produtos": [
            {"nome": p.nome, "estoque": _qtd(p.saldo), "valor_parado": reais(p.valor_parado),
             "dias_sem_venda": p.dias_parado,
             "validade_mais_proxima": p.validade_mais_proxima.isoformat() if p.validade_mais_proxima else None}
            for p in produtos
        ],
        "aviso": "A tela já mostra a tabela. Sugira promoção ou devolução ao fornecedor só se fizer sentido.",
    }


def _cartao_se(ctx: Contexto, tipo: str, itens: list, cartao: dict) -> None:
    """No pedido de "todos", o que está vazio não vira cartão (o modelo ainda recebe a lista vazia)."""
    if itens or tipo != "todos":
        ctx.cartoes.append(cartao)


def alertas_estoque(ctx: Contexto, tipo: str, dias: int) -> dict:
    dias = max(1, min(dias or 60, 365))
    loja_id = ctx.terminal.loja_id if ctx.terminal is not None else None
    al = estoque.alertas(ctx.db, dias, loja_id)
    resultado: dict = {}
    if tipo in ("acabando", "todos"):
        itens = al.abaixo_do_minimo[:30]
        _cartao_se(ctx, tipo, itens, {
            "tipo": "tabela",
            "titulo": "Acabando (abaixo do mínimo)",
            "subtitulo": f"{len(al.abaixo_do_minimo)} produtos",
            "colunas": [
                {"rotulo": "Produto", "num": False}, {"rotulo": "Loja", "num": False},
                {"rotulo": "Tem", "num": True}, {"rotulo": "Mínimo", "num": True},
            ],
            "linhas": [[p.nome, p.loja_nome, _qtd(p.saldo), _qtd(p.estoque_minimo)] for p in itens],
            "vazio": "Nada abaixo do mínimo.",
            "rota": "/compras/sugestao",
            "rotulo_rota": "Ver sugestão de compras",
        })
        resultado["acabando"] = [
            {"produto": p.nome, "loja": p.loja_nome, "saldo": _qtd(p.saldo), "minimo": _qtd(p.estoque_minimo)}
            for p in itens
        ]
    for nome, lotes, titulo in (
        ("vencendo", al.vencendo, f"Vencendo em até {dias} dias"),
        ("vencidos", al.vencidos, "Vencidos com saldo"),
    ):
        if tipo not in (nome, "todos"):
            continue
        itens = lotes[:30]
        _cartao_se(ctx, tipo, itens, {
            "tipo": "tabela",
            "titulo": titulo,
            "subtitulo": f"{len(lotes)} lotes",
            "colunas": [
                {"rotulo": "Produto", "num": False}, {"rotulo": "Lote", "num": False},
                {"rotulo": "Validade", "num": False}, {"rotulo": "Qtd.", "num": True},
            ],
            "linhas": [
                [lote.produto_nome, lote.numero_lote, _data(lote.validade) if lote.validade else "-",
                 _qtd(lote.quantidade)]
                for lote in itens
            ],
            "vazio": "Nenhum lote." if nome == "vencidos" else "Nada vencendo nesse prazo.",
            "rota": "/estoque",
            "rotulo_rota": "Ver alertas do estoque",
        })
        resultado[nome] = [
            {"produto": lote.produto_nome, "lote": lote.numero_lote,
             "validade": lote.validade.isoformat() if lote.validade else None,
             "dias_para_vencer": lote.dias_para_vencer, "quantidade": _qtd(lote.quantidade), "loja": lote.loja_nome}
            for lote in itens
        ]
    resultado["aviso"] = "A tela já mostra as tabelas: resuma em poucas frases o que pede atenção primeiro."
    return resultado


EXECUTORES_RELATORIOS = {
    "relatorio_vendas": relatorio_vendas,
    "mais_vendidos": mais_vendidos,
    "produtos_parados": produtos_parados,
    "alertas_estoque": alertas_estoque,
}
