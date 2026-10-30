import uuid

from sqlalchemy import ForeignKeyConstraint, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base, TabelaDaFarmacia

TIPOS = ("ganho", "resgate", "estorno", "ajuste", "expirado")


class MovimentoPontos(TabelaDaFarmacia, Base):
    """Extrato de pontos do cliente. O saldo é a soma; nada é alterado depois de gravado."""

    __tablename__ = "movimentos_pontos"
    __table_args__ = (
        ForeignKeyConstraint(["farmacia_id", "cliente_id"], ["clientes.farmacia_id", "clientes.id"]),
        ForeignKeyConstraint(["farmacia_id", "venda_id"], ["vendas.farmacia_id", "vendas.id"]),
    )

    cliente_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    tipo: Mapped[str] = mapped_column(String(10))
    pontos: Mapped[int] = mapped_column(Integer)  # positivo entra, negativo sai
    venda_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    observacao: Mapped[str | None] = mapped_column(String(200))
