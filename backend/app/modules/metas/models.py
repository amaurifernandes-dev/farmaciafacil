import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, ForeignKeyConstraint, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base, TabelaDaFarmacia


class Meta(TabelaDaFarmacia, Base):
    """Quanto uma loja ou um vendedor deve vender no mês."""

    __tablename__ = "metas"
    __table_args__ = (ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),)

    mes: Mapped[date] = mapped_column(Date)
    loja_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))
