import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base, TabelaDaFarmacia


class Inventario(TabelaDaFarmacia, Base):
    """Uma contagem do estoque de uma loja. Ao finalizar, o saldo vira o que foi contado."""

    __tablename__ = "inventarios"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "id"),
        ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
    )

    loja_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    descricao: Mapped[str] = mapped_column(String(80))
    escopo: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(12), default="aberto")
    aberto_por: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    finalizado_por: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    finalizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    produtos_ajustados: Mapped[int | None] = mapped_column(Integer)
    valor_sobra: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    valor_falta: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))


class ItemInventario(TabelaDaFarmacia, Base):
    __tablename__ = "inventario_itens"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "inventario_id", "produto_id", name="uq_inventario_itens_produto"),
        ForeignKeyConstraint(["farmacia_id", "inventario_id"], ["inventarios.farmacia_id", "inventarios.id"]),
        ForeignKeyConstraint(["farmacia_id", "produto_id"], ["produtos.farmacia_id", "produtos.id"]),
    )

    inventario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    produto_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    quantidade: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    saldo_sistema: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    custo_unitario: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    contado: Mapped[bool] = mapped_column(Boolean, default=True)
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
