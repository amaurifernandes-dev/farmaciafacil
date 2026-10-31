import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKeyConstraint, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base, TabelaDaFarmacia


class Etiqueta(TabelaDaFarmacia, Base):
    """A etiqueta que está na gôndola de uma loja: o preço e a promoção impressos da última vez."""

    __tablename__ = "etiquetas"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "loja_id", "produto_id", name="uq_etiquetas_loja_produto"),
        ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
        ForeignKeyConstraint(["farmacia_id", "produto_id"], ["produtos.farmacia_id", "produtos.id"]),
    )

    loja_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    produto_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    preco: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    preco_promocional: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    promocao: Mapped[str | None] = mapped_column(String(120))
    impressa_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
