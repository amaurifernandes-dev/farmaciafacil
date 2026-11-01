"""Ferramentas do assistente: cada uma usa os serviços do sistema com o login de quem pergunta."""

import json
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import and_, func, or_, select

from app.modules.assistente.contexto import Contexto, ErroDaFerramenta
from app.modules.assistente.guias import POR_ID, lista_para_ferramenta
from app.modules.assistente.relatorios import (
    EXECUTORES_RELATORIOS,
    FERRAMENTAS_ESTOQUE,
    FERRAMENTAS_GERENCIA,
)
from app.modules.clientes import service as clientes
from app.modules.clientes.models import Cliente
from app.modules.clientes.schemas import ClienteCriar
from app.modules.estoque.service import _lotes_vendaveis
from app.modules.lojas.service import matriz
from app.modules.produtos.models import Produto
from app.modules.promocoes.service import melhor, resumo, vigentes_por_produto
from app.modules.vendas import service as vendas
from app.modules.vendas.schemas import PreVendaCriar
from app.shared.erros import ErroDeNegocio

ATENDIMENTO = ("admin", "gerente", "farmaceutico", "caixa", "atendente")
ACENTOS, SEM_ACENTOS = "áàãâäéèêëíìîïóòõôöúùûüç", "aaaaaeeeeiiiiooooouuuuc"


def _texto_ou_nulo(descricao: str) -> dict:
    return {"type": ["string", "null"], "description": descricao}


FERRAMENTAS: list[dict] = [
    {
        "name": "buscar_produtos",
        "description": (
            "Procura produtos no cadastro pelo nome, apresentação ou fabricante, com o preço, a promoção de hoje "
            "e o estoque desta loja. Passe vários termos para achar variações (ex.: para protetor solar: "
            "[\"protetor solar\", \"fps\", \"bloqueador\"]). Volta ordenado do menor preço final para o maior."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "termos": {"type": "array", "items": {"type": "string"}, "description": "Palavras para procurar"},
                "so_promocao": {"type": "boolean", "description": "Só produtos em promoção hoje"},
                "incluir_sem_estoque": {"type": "boolean", "description": "Mostrar também os sem estoque"},
            },
            "required": ["termos", "so_promocao", "incluir_sem_estoque"],
            "additionalProperties": False,
        },
    },
    {
        "name": "criar_pre_venda",
        "description": (
            "Abre uma pré-venda (pedido do balcão que o cliente paga no caixa). Use os produto_id que vieram de "
            "buscar_produtos. Antes, confirme com o usuário os produtos e as quantidades."
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
                            "quantidade": {"type": "number"},
                        },
                        "required": ["produto_id", "quantidade"],
                        "additionalProperties": False,
                    },
                },
                "cliente_cpf": _texto_ou_nulo("CPF do cliente, se ele quiser na nota"),
            },
            "required": ["itens", "cliente_cpf"],
            "additionalProperties": False,
        },
    },
    {
        "name": "buscar_cliente",
        "description": "Procura clientes já cadastrados pelo nome, CPF ou telefone (use antes de cadastrar um novo).",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"busca": {"type": "string"}},
            "required": ["busca"],
            "additionalProperties": False,
        },
    },
    {
        "name": "cadastrar_cliente",
        "description": (
            "Cadastra um cliente novo. Só chame depois de repetir todos os dados para o usuário e ele confirmar. "
            "Campos que o cliente não informou vão como null. Datas no formato AAAA-MM-DD; CPF, telefone e CEP "
            "só com números."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string", "description": "Nome completo"},
                "cpf": _texto_ou_nulo("CPF, só números"),
                "telefone": _texto_ou_nulo("Telefone com DDD, só números"),
                "email": _texto_ou_nulo("E-mail"),
                "data_nascimento": _texto_ou_nulo("AAAA-MM-DD"),
                "cep": _texto_ou_nulo("CEP, só números"),
                "endereco": _texto_ou_nulo("Rua e número"),
                "bairro": _texto_ou_nulo("Bairro"),
                "cidade": _texto_ou_nulo("Cidade"),
                "uf": _texto_ou_nulo("Sigla do estado"),
                "aceita_ofertas": {"type": "boolean", "description": "Só true se o cliente aceitou receber ofertas"},
            },
            "required": [
                "nome", "cpf", "telefone", "email", "data_nascimento", "cep", "endereco", "bairro", "cidade",
                "uf", "aceita_ofertas",
            ],
            "additionalProperties": False,
        },
    },
    {
        "name": "mostrar_guia",
        "description": (
            "Mostra o passo a passo de uma tarefa do sistema, com o botão \"Começar\" que abre a tela certa. "
            "Use quando perguntarem como fazer algo. Guias disponíveis:\n" + lista_para_ferramenta()
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"guia_id": {"type": "string", "enum": sorted(POR_ID)}},
            "required": ["guia_id"],
            "additionalProperties": False,
        },
    },
]


def _sem_acento(coluna):
    return func.translate(func.lower(coluna), ACENTOS, SEM_ACENTOS)


def _normalizar(texto: str) -> str:
    return texto.lower().translate(str.maketrans(ACENTOS, SEM_ACENTOS)).strip()


def _loja_id(ctx: Contexto) -> UUID | None:
    if ctx.terminal is not None:
        return ctx.terminal.loja_id
    loja = matriz(ctx.db)
    return loja.id if loja else None


def _dinheiro(valor: Decimal) -> str:
    return f"{valor:.2f}"


def buscar_produtos(ctx: Contexto, termos: list[str], so_promocao: bool, incluir_sem_estoque: bool) -> dict:
    condicoes = []
    for termo in termos[:6]:
        palavras = [p for p in _normalizar(termo).split() if p]
        if not palavras:
            continue
        # Todas as palavras do termo, em qualquer campo de texto do produto.
        texto = _sem_acento(
            func.concat_ws(" ", Produto.nome, Produto.apresentacao, Produto.fabricante)
        )
        condicoes.append(and_(*[texto.like(f"%{p}%") for p in palavras]))
    if not condicoes:
        raise ErroDaFerramenta("Diga o que procurar (nome do produto ou tipo de produto).")
    produtos = ctx.db.scalars(
        select(Produto).where(Produto.ativo.is_(True), or_(*condicoes)).order_by(Produto.nome).limit(60)
    ).all()
    loja_id = _loja_id(ctx)
    vendaveis = _lotes_vendaveis(loja_id).subquery()
    saldos = dict(ctx.db.execute(
        select(vendaveis.c.produto_id, func.sum(vendaveis.c.quantidade))
        .where(vendaveis.c.produto_id.in_([p.id for p in produtos]))
        .group_by(vendaveis.c.produto_id)
    ).all())
    promocoes = vigentes_por_produto(ctx.db, [p.id for p in produtos], loja_id)
    itens = []
    for p in produtos:
        saldo = saldos.get(p.id, Decimal(0))
        promocao, desconto = melhor(promocoes.get(p.id, []), p.preco_venda, Decimal(1), com_cliente=True)
        if so_promocao and promocao is None:
            continue
        if saldo <= 0 and not incluir_sem_estoque:
            continue
        itens.append({
            "produto_id": str(p.id),
            "nome": p.nome,
            "apresentacao": p.apresentacao,
            "fabricante": p.fabricante,
            "preco": _dinheiro(p.preco_venda),
            "preco_final": _dinheiro(p.preco_venda - desconto),
            "promocao": resumo(promocao) if promocao else None,
            "so_clientes": bool(promocao and promocao.so_clientes),
            "estoque": f"{saldo.normalize():f}",
        })
    itens.sort(key=lambda i: (Decimal(i["preco_final"]), i["nome"]))
    itens = itens[:15]
    ctx.cartoes.append({"tipo": "produtos", "termos": termos, "itens": itens})
    return {"quantidade": len(itens), "produtos": itens}


def criar_pre_venda(ctx: Contexto, itens: list[dict], cliente_cpf: str | None) -> dict:
    if ctx.usuario.papel not in ATENDIMENTO:
        raise ErroDaFerramenta("O perfil deste usuário não faz pré-vendas.")
    try:
        dados = PreVendaCriar(itens=itens, cliente_cpf=cliente_cpf)
    except ValidationError as erro:
        raise ErroDaFerramenta(f"Dados da pré-venda inválidos: {erro.errors()[0]['msg']}")
    pre_venda = vendas.criar_pre_venda(ctx.db, ctx.usuario, ctx.terminal, dados)
    saida = vendas.saida_pre_venda(ctx.db, pre_venda)
    # A pré-venda guarda o preço de tabela; o caixa aplica as promoções na hora de receber.
    promocoes = vigentes_por_produto(ctx.db, [i.produto_id for i in saida.itens], _loja_id(ctx))
    descontos = [
        melhor(promocoes.get(i.produto_id, []), i.preco_unitario, i.quantidade, com_cliente=False)[1]
        for i in saida.itens
    ]
    cartao = {
        "tipo": "pre_venda",
        "id": str(saida.id),
        "numero": saida.numero,
        "total": _dinheiro(saida.total),
        "total_com_promocoes": _dinheiro(saida.total - sum(descontos, Decimal(0))),
        "itens": [
            {"descricao": i.descricao, "quantidade": f"{i.quantidade.normalize():f}", "total": _dinheiro(i.total)}
            for i in saida.itens
        ],
    }
    ctx.cartoes.append(cartao)
    return {
        "pre_venda_numero": saida.numero,
        "total_tabela": cartao["total"],
        "total_com_promocoes_no_caixa": cartao["total_com_promocoes"],
        "itens": cartao["itens"],
    }


def buscar_cliente(ctx: Contexto, busca: str) -> dict:
    encontrados, total = clientes.listar(ctx.db, busca, 1, 5, False)
    return {
        "total": total,
        "clientes": [
            {"id": str(c.id), "nome": c.nome, "cpf": c.cpf, "telefone": c.telefone} for c in encontrados
        ],
    }


def cadastrar_cliente(ctx: Contexto, **dados: Any) -> dict:
    try:
        cliente = ClienteCriar(**dados)
    except ValidationError as erro:
        campo = ".".join(str(c) for c in erro.errors()[0]["loc"])
        raise ErroDaFerramenta(f"O campo {campo} está inválido: {erro.errors()[0]['msg']}. Peça para o cliente repetir.")
    criado: Cliente = clientes.criar(ctx.db, cliente)
    ctx.cartoes.append({"tipo": "cliente", "id": str(criado.id), "nome": criado.nome})
    return {"cliente_id": str(criado.id), "nome": criado.nome, "cadastrado": True}


def mostrar_guia(ctx: Contexto, guia_id: str) -> dict:
    guia = POR_ID.get(guia_id)
    if guia is None:
        raise ErroDaFerramenta("Guia não encontrado.")
    ctx.cartoes.append({"tipo": "guia", "id": guia.id, "titulo": guia.titulo, "rota": guia.rota,
                        "passos": list(guia.passos)})
    return {"titulo": guia.titulo, "passos": list(guia.passos), "tela": guia.rota,
            "aviso": "A tela já mostra os passos e o botão Começar: responda só com um resumo curto."}


EXECUTORES = {
    "buscar_produtos": buscar_produtos,
    "criar_pre_venda": criar_pre_venda,
    "buscar_cliente": buscar_cliente,
    "cadastrar_cliente": cadastrar_cliente,
    "mostrar_guia": mostrar_guia,
    **EXECUTORES_RELATORIOS,
}


def ferramentas_para(ctx: Contexto) -> list[dict]:
    """O modelo só conhece as ferramentas que o perfil pode usar (os números de vendas são da gerência)."""
    return [*FERRAMENTAS, *FERRAMENTAS_ESTOQUE, *(FERRAMENTAS_GERENCIA if ctx.gerente else [])]


def executar(ctx: Contexto, nome: str, entrada: dict) -> tuple[str, bool]:
    """Roda a ferramenta e devolve (conteúdo para o modelo, é_erro)."""
    executor = EXECUTORES.get(nome)
    if executor is None:
        return f"Ferramenta desconhecida: {nome}", True
    try:
        resultado = executor(ctx, **entrada)
    except (ErroDaFerramenta, ErroDeNegocio) as erro:
        ctx.db.rollback()
        return str(erro), True
    except TypeError as erro:
        ctx.db.rollback()
        return f"Parâmetros inválidos: {erro}", True
    return json.dumps(resultado, ensure_ascii=False), False
