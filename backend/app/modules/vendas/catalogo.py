"""Cópia do catálogo para o caixa vender quando a internet cair."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import DB, Operador
from app.modules.estoque.service import _lotes_vendaveis
from app.modules.farmacias.models import Farmacia
from app.modules.lojas.deps import TerminalAtual
from app.modules.produtos.models import Produto
from app.modules.produtos.schemas import ProdutoPDV
from app.modules.promocoes.service import para_pdv, vigentes_por_produto
from app.modules.vendas.service import _exigir_terminal


class CatalogoPDV(BaseModel):
    gerado_em: datetime
    loja_id: UUID
    desconto_maximo_caixa: Decimal
    produtos: list[ProdutoPDV]


def montar(db: Session, farmacia_id: UUID, loja_id: UUID) -> CatalogoPDV:
    """Produtos ativos com o preço, as promoções de hoje e o saldo vendável desta loja."""
    produtos = db.scalars(select(Produto).where(Produto.ativo.is_(True)).order_by(Produto.nome)).all()
    vendaveis = _lotes_vendaveis(loja_id).subquery()
    saldos = dict(db.execute(
        select(vendaveis.c.produto_id, func.sum(vendaveis.c.quantidade)).group_by(vendaveis.c.produto_id)
    ).all())
    promocoes = vigentes_por_produto(db, [p.id for p in produtos], loja_id)
    farmacia = db.get(Farmacia, farmacia_id)
    return CatalogoPDV(
        gerado_em=datetime.now(UTC),
        loja_id=loja_id,
        desconto_maximo_caixa=farmacia.desconto_maximo_caixa,
        produtos=[
            ProdutoPDV.model_validate(p).model_copy(
                update={"saldo": saldos.get(p.id, Decimal(0)), "promocoes": para_pdv(promocoes.get(p.id, []))}
            )
            for p in produtos
        ],
    )


router = APIRouter(prefix="/pdv", tags=["caixa"])


@router.get("/catalogo", summary="Cópia do catálogo para o caixa vender sem internet")
def catalogo(db: DB, usuario: Operador, terminal: TerminalAtual) -> CatalogoPDV:
    return montar(db, usuario.farmacia_id, _exigir_terminal(terminal).loja_id)
