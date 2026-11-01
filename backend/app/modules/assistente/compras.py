"""Pedido de compra pelo assistente: parte da sugestão de compras e separa por fornecedor.

O cartão mostra o texto pronto para copiar, mandar no WhatsApp ou por e-mail, e o botão "Salvar pedido"
grava cada fornecedor em Compras > Pedidos, para conferir quando a nota chegar.
"""

from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from app.modules.assistente.contexto import Contexto, ErroDaFerramenta
from app.modules.assistente.relatorios import reais
from app.modules.compras import service as compras
from app.modules.compras.pedidos import whatsapp
from app.modules.farmacias.models import Farmacia
from app.modules.fornecedores.models import Fornecedor
from app.modules.lojas.models import Loja
from app.modules.lojas.service import matriz
from app.modules.produtos.models import Produto
from app.shared.datas import hoje

SEM_PERMISSAO = "Só quem cuida do estoque (gerente, farmacêutico ou estoquista) monta pedido de compra."
MAX_ITENS = 60

FERRAMENTAS_COMPRAS: list[dict] = [
    {
        "name": "sugerir_compra",
        "description": (
            "O que comprar para a loja aguentar N dias no ritmo de venda recente, nunca abaixo do estoque mínimo, "
            "contando faltas anotadas e encomendas de clientes. Traz o último custo de cada fornecedor. Não mostra "
            "nada na tela: depois chame montar_pedido_compra com os itens."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "dias_cobertura": {"type": "integer", "description": "Comprar para quantos dias (padrão 15)"},
                "dias_historico": {"type": "integer", "description": "Olhar as vendas de quantos dias (padrão 30)"},
            },
            "required": ["dias_cobertura", "dias_historico"],
            "additionalProperties": False,
        },
    },
    {
        "name": "montar_pedido_compra",
        "description": (
            "Monta o pedido de compra separado por fornecedor e mostra na tela com os botões de copiar, WhatsApp "
            "e e-mail. Passe todos os itens do pedido (para mudar algo, chame de novo com a lista inteira). "
            "fornecedor_id null escolhe o fornecedor com o menor último custo."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "itens": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "produto_id": {"type": "string"},
                            "quantidade": {"type": "integer"},
                            "fornecedor_id": {"type": ["string", "null"]},
                        },
                        "required": ["produto_id", "quantidade", "fornecedor_id"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["itens"],
            "additionalProperties": False,
        },
    },
]


def _qtd(valor: Decimal) -> str:
    return f"{Decimal(valor).normalize():f}".replace(".", ",")


def _loja(ctx: Contexto) -> Loja | None:
    if ctx.terminal is not None:
        return ctx.db.get(Loja, ctx.terminal.loja_id)
    return matriz(ctx.db)


def _uuid(valor: str | None, o_que: str) -> UUID | None:
    if valor is None:
        return None
    try:
        return UUID(valor)
    except ValueError:
        raise ErroDaFerramenta(f"{o_que} inválido: {valor}. Use os ids que vieram das ferramentas.")


def sugerir_compra(ctx: Contexto, dias_cobertura: int, dias_historico: int) -> dict:
    if not ctx.compra:
        raise ErroDaFerramenta(SEM_PERMISSAO)
    loja = _loja(ctx)
    cobertura = max(1, min(dias_cobertura or 15, 180))
    historico = max(7, min(dias_historico or 30, 365))
    sug = compras.sugestao(ctx.db, loja.id if loja else None, historico, cobertura)
    return {
        "loja": loja.nome if loja else None,
        "dias_cobertura": cobertura,
        "dias_historico": historico,
        "total_estimado": reais(sug.total_estimado),
        "itens": [
            {
                "produto_id": str(i.produto_id),
                "nome": f"{i.nome} {i.apresentacao}" if i.apresentacao else i.nome,
                "tem": _qtd(i.saldo),
                "minimo": _qtd(i.estoque_minimo),
                "vendido_no_periodo": _qtd(i.vendido_no_periodo),
                "encomendas": _qtd(i.encomendas_abertas),
                "dias_de_estoque": None if i.dias_de_estoque is None else _qtd(i.dias_de_estoque),
                "sugerido": int(i.sugerido),
                "fornecedores": [
                    {"fornecedor_id": str(f.fornecedor_id), "nome": f.fornecedor_nome,
                     "custo": reais(f.custo_unitario)}
                    for f in i.fornecedores[:3]
                ],
            }
            for i in sug.itens[:MAX_ITENS]
        ],
        "aviso": "Agora chame montar_pedido_compra com estes itens e quantidades (fornecedor_id null).",
    }


def _texto_do_pedido(farmacia: str, loja: str | None, grupo: dict) -> str:
    linhas = [
        f"Olá{', ' + grupo['contato'] if grupo.get('contato') else ''}! Pedido de compra da {farmacia}"
        + (f" ({loja})" if loja else "") + f", {hoje():%d/%m/%Y}:",
        "",
    ]
    for item in grupo["itens"]:
        ean = f" (EAN {item['ean']})" if item["ean"] else ""
        linhas.append(f"- {item['quantidade']} x {item['nome']}{ean}")
    linhas += ["", "Por favor, confirme preço e prazo de entrega. Obrigado!"]
    return "\n".join(linhas)


def montar_pedido_compra(ctx: Contexto, itens: list[dict]) -> dict:
    if not ctx.compra:
        raise ErroDaFerramenta(SEM_PERMISSAO)
    pedidos = [(_uuid(i["produto_id"], "produto_id"), int(i["quantidade"]), _uuid(i.get("fornecedor_id"), "fornecedor_id"))
               for i in itens[:MAX_ITENS] if int(i["quantidade"]) > 0]
    if not pedidos:
        raise ErroDaFerramenta("O pedido ficou sem itens. Diga o que comprar.")
    produtos = {p.id: p for p in ctx.db.scalars(select(Produto).where(Produto.id.in_([p for p, _, _ in pedidos])))}
    faltando = [str(p) for p, _, _ in pedidos if p not in produtos]
    if faltando:
        raise ErroDaFerramenta(f"Produto não encontrado: {', '.join(faltando)}. Procure com buscar_produtos.")
    precos = compras.precos_por_fornecedor(ctx.db, list(produtos))
    escolhidos = {f for _, _, f in pedidos if f}
    fornecedores = {f.id: f for f in ctx.db.scalars(select(Fornecedor).where(Fornecedor.id.in_(
        escolhidos | {p.fornecedor_id for lista in precos.values() for p in lista}
    )))}
    if escolhidos - set(fornecedores):
        raise ErroDaFerramenta("Fornecedor não encontrado. Use os fornecedor_id que vieram de sugerir_compra.")

    grupos: dict[UUID | None, list[dict]] = defaultdict(list)
    for produto_id, quantidade, fornecedor_id in pedidos:
        produto = produtos[produto_id]
        opcoes = precos.get(produto_id, [])
        if fornecedor_id is None and opcoes:
            fornecedor_id = opcoes[0].fornecedor_id
        custo = next((p.custo_unitario for p in opcoes if p.fornecedor_id == fornecedor_id), produto.preco_custo)
        grupos[fornecedor_id].append({
            "produto_id": str(produto_id),
            "nome": f"{produto.nome} {produto.apresentacao}" if produto.apresentacao else produto.nome,
            "ean": produto.ean,
            "quantidade": quantidade,
            "custo": reais(custo) if custo is not None else "-",
            "custo_unitario": str(custo) if custo is not None else None,
            "total": reais(custo * quantidade) if custo is not None else "-",
            "_total": (custo or Decimal(0)) * quantidade,
            "_sem_custo": custo is None,
        })

    loja = _loja(ctx)
    farmacia = ctx.db.get(Farmacia, ctx.usuario.farmacia_id)
    nome_farmacia = (farmacia.nome_fantasia or farmacia.razao_social) if farmacia else "farmácia"
    saida, total_geral = [], Decimal(0)
    # Fornecedores com nome em ordem alfabética; "sem fornecedor" por último.
    ordem = sorted(grupos, key=lambda f: (f is None, _nome_fornecedor(fornecedores.get(f)) if f else ""))
    for fornecedor_id in ordem:
        linhas = grupos[fornecedor_id]
        fornecedor = fornecedores.get(fornecedor_id) if fornecedor_id else None
        total = sum((linha["_total"] for linha in linhas), Decimal(0))
        total_geral += total
        grupo = {
            "fornecedor_id": str(fornecedor_id) if fornecedor_id else None,
            "fornecedor": _nome_fornecedor(fornecedor) if fornecedor else "Sem fornecedor definido",
            "contato": fornecedor.contato if fornecedor else None,
            "telefone": fornecedor.telefone if fornecedor else None,
            "whatsapp": whatsapp(fornecedor.telefone) if fornecedor else None,
            "email": fornecedor.email if fornecedor else None,
            "itens": [{k: v for k, v in linha.items() if not k.startswith("_")} for linha in linhas],
            "total": reais(total),
            "sem_custo": sum(1 for linha in linhas if linha["_sem_custo"]),
        }
        grupo["texto"] = _texto_do_pedido(nome_farmacia, loja.nome if loja else None, grupo)
        saida.append(grupo)

    ctx.cartoes.append({
        "tipo": "pedido_compra",
        "loja": loja.nome if loja else None,
        "loja_id": str(loja.id) if loja else None,
        "data": f"{hoje():%d/%m/%Y}",
        "grupos": saida,
        "total": reais(total_geral),
        "itens": len(pedidos),
    })
    return {
        "fornecedores": [
            {"fornecedor": g["fornecedor"], "itens": len(g["itens"]), "total": g["total"],
             "tem_whatsapp": bool(g["whatsapp"]), "tem_email": bool(g["email"])}
            for g in saida
        ],
        "total_estimado": reais(total_geral),
        "aviso": (
            "A tela já mostra o pedido com os botões de copiar, WhatsApp, e-mail e salvar. O pedido não é enviado "
            "sozinho: resuma em uma frase e diga que dá para ajustar falando (tirar, pôr ou trocar itens) e que o "
            "botão Salvar pedido guarda em Compras > Pedidos para conferir quando a nota chegar."
        ),
    }


def _nome_fornecedor(fornecedor: Fornecedor | None) -> str:
    if fornecedor is None:
        return ""
    return fornecedor.nome_fantasia or fornecedor.razao_social


EXECUTORES_COMPRAS = {
    "sugerir_compra": sugerir_compra,
    "montar_pedido_compra": montar_pedido_compra,
}
