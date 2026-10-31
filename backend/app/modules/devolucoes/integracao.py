"""O que as vendas e o caixa precisam saber das devoluções e dos vales-troca.

Fica separado do service para o módulo de vendas poder usar sem importar o de devoluções.
"""

import re
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.devolucoes.models import Devolucao, ValeTroca
from app.shared.datas import hoje
from app.shared.erros import ErroDeNegocio, NaoEncontrado


def normalizar_codigo(codigo: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (codigo or "").upper())


def vale_pelo_codigo(db: Session, codigo: str | None, travar: bool = False) -> ValeTroca:
    consulta = select(ValeTroca).where(ValeTroca.codigo == normalizar_codigo(codigo))
    vale = db.scalar(consulta.with_for_update() if travar else consulta)
    if vale is None:
        raise NaoEncontrado("Vale-troca não encontrado. Confira o código.")
    return vale


def usar_vales(db: Session, pagamentos) -> dict[str, UUID]:
    """Desconta do saldo dos vales usados como pagamento. Devolve {código: id do vale}."""
    por_codigo: dict[str, Decimal] = {}
    for pagamento in pagamentos:
        if pagamento.forma != "vale":
            continue
        codigo = normalizar_codigo(pagamento.vale_codigo)
        if not codigo:
            raise ErroDeNegocio("Digite o código do vale-troca")
        por_codigo[codigo] = por_codigo.get(codigo, Decimal(0)) + pagamento.valor
    ids = {}
    for codigo, valor in por_codigo.items():
        vale = vale_pelo_codigo(db, codigo, travar=True)
        if vale.status == "cancelado":
            raise ErroDeNegocio(f"O vale {codigo} foi cancelado")
        if vale.status == "usado" or vale.saldo <= 0:
            raise ErroDeNegocio(f"O vale {codigo} já foi usado")
        if vale.validade < hoje():
            raise ErroDeNegocio(f"O vale {codigo} venceu em {vale.validade:%d/%m/%Y}")
        if valor > vale.saldo:
            raise ErroDeNegocio(f"O vale {codigo} só tem R$ {vale.saldo:.2f} de saldo")
        vale.saldo -= valor
        if vale.saldo == 0:
            vale.status = "usado"
        ids[codigo] = vale.id
    return ids


def estornar_vales(db: Session, venda) -> None:
    """Venda cancelada: o valor pago com vale volta para o saldo do vale."""
    for pagamento in venda.pagamentos:
        if pagamento.forma != "vale" or pagamento.vale_id is None:
            continue
        vale = db.scalar(select(ValeTroca).where(ValeTroca.id == pagamento.vale_id).with_for_update())
        vale.saldo += pagamento.valor
        if vale.status == "usado":
            vale.status = "ativo"


def devolvido_no_caixa(db: Session, caixa_id: UUID) -> Decimal:
    """Dinheiro que saiu da gaveta deste caixa para clientes que devolveram itens."""
    return db.scalar(
        select(func.coalesce(func.sum(Devolucao.valor_total), 0))
        .where(Devolucao.caixa_id == caixa_id, Devolucao.destino == "dinheiro")
    )


def tem_devolucao(db: Session, venda_id: UUID) -> bool:
    return db.scalar(select(func.count()).where(Devolucao.venda_id == venda_id)) > 0
