import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    ForeignKeyConstraint,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import Base, TabelaDaFarmacia

TIPOS_PRODUTO = ("medicamento", "perfumaria", "outros")


class Produto(TabelaDaFarmacia, Base):
    __tablename__ = "produtos"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "ean"),
        UniqueConstraint("farmacia_id", "id"),  # alvo das FKs compostas
    )

    ean: Mapped[str | None] = mapped_column(String(14))
    nome: Mapped[str] = mapped_column(String(200))
    apresentacao: Mapped[str | None] = mapped_column(String(200))
    fabricante: Mapped[str | None] = mapped_column(String(120))
    ncm: Mapped[str | None] = mapped_column(String(8))
    cest: Mapped[str | None] = mapped_column(String(7))
    unidade: Mapped[str] = mapped_column(String(6), default="UN")
    preco_venda: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    preco_custo: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    estoque_minimo: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0)
    controla_lote: Mapped[bool] = mapped_column(Boolean, default=True)
    tipo: Mapped[str] = mapped_column(String(20), default="outros")
    registro_ms: Mapped[str | None] = mapped_column(String(20))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    codigos: Mapped[list["ProdutoCodigo"]] = relationship(
        back_populates="produto", cascade="all, delete-orphan", lazy="selectin"
    )


class ProdutoCodigo(TabelaDaFarmacia, Base):
    """Códigos de barras extras de um produto (embalagens diferentes, códigos antigos)."""

    __tablename__ = "produto_codigos"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "ean"),
        ForeignKeyConstraint(
            ["farmacia_id", "produto_id"],
            ["produtos.farmacia_id", "produtos.id"],
            ondelete="CASCADE",
        ),
    )

    produto_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    ean: Mapped[str] = mapped_column(String(14))

    produto: Mapped[Produto] = relationship(back_populates="codigos")
