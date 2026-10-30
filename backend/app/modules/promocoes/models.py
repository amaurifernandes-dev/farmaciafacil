import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKeyConstraint, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import Base, TabelaDaFarmacia

TIPOS = ("percentual", "preco_fixo", "leve_pague")


class Promocao(TabelaDaFarmacia, Base):
    """Desconto automático em produtos durante um período. O PDV aplica sozinho; o melhor para o cliente vale."""

    __tablename__ = "promocoes"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "id"),
        ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
    )

    nome: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(String(12))
    percentual: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))  # percentual: % de desconto
    preco: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))  # preco_fixo: preço da unidade na promoção
    leve: Mapped[int | None] = mapped_column(Integer)  # leve_pague: leve 3, pague 2
    pague: Mapped[int | None] = mapped_column(Integer)
    inicio: Mapped[date] = mapped_column(Date)
    fim: Mapped[date | None] = mapped_column(Date)  # vazio: sem data para acabar
    # Só para clientes identificados no caixa (ajuda a fazer o cadastro).
    so_clientes: Mapped[bool] = mapped_column(Boolean, default=False)
    loja_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # vazio: todas as lojas
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))

    produtos: Mapped[list["PromocaoProduto"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class PromocaoProduto(TabelaDaFarmacia, Base):
    __tablename__ = "promocao_produtos"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "promocao_id", "produto_id"),
        ForeignKeyConstraint(["farmacia_id", "promocao_id"], ["promocoes.farmacia_id", "promocoes.id"],
                             ondelete="CASCADE"),
        ForeignKeyConstraint(["farmacia_id", "produto_id"], ["produtos.farmacia_id", "produtos.id"]),
    )

    promocao_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    produto_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
