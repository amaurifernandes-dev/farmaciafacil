"""Funções que o administrador pode desligar no Gerenciamento de telas.

Desligada, a função some das telas de todo mundo (inclusive do administrador) e as rotas dela respondem 403.
O básico (vendas, caixa, produtos, estoque, compras, clientes, financeiro, configurações) não desliga.
"""

from typing import Literal

Modulo = Literal[
    "devolucoes",
    "faltas",
    "pedidos",
    "loja_online",
    "convenios",
    "popular",
    "controlados",
    "servicos",
    "comissoes",
    "metas",
    "promocoes",
    "etiquetas",
]

MODULOS: tuple[str, ...] = Modulo.__args__

NOMES: dict[str, str] = {
    "devolucoes": "Trocas e devoluções",
    "faltas": "Faltas e encomendas",
    "pedidos": "Pedidos e entregas",
    "loja_online": "Loja online",
    "convenios": "Convênios",
    "popular": "Farmácia Popular",
    "controlados": "Controlados (SNGPC)",
    "servicos": "Serviços farmacêuticos",
    "comissoes": "Comissões",
    "metas": "Metas",
    "promocoes": "Promoções",
    "etiquetas": "Etiquetas de gôndola",
}

# Ligar a primeira exige a segunda: a loja online gera pedidos.
DEPENDE_DE: dict[str, str] = {"loja_online": "pedidos"}


def desligado(desligados: list[str] | None, modulo: str) -> bool:
    desligados = desligados or []
    return modulo in desligados or (modulo in DEPENDE_DE and DEPENDE_DE[modulo] in desligados)
