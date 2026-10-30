import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKeyConstraint, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base, TabelaDaFarmacia

# registrada: só anotou que faltou (conta na sugestão de compras).
# aberta: encomenda, o cliente quer ser avisado quando chegar.
STATUS = ("registrada", "aberta", "avisado", "entregue", "cancelada")
PENDENTES = ("aberta", "avisado")


class Falta(TabelaDaFarmacia, Base):
    """O que o cliente pediu e a loja não tinha. Com contato, vira encomenda."""

    __tablename__ = "faltas"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "id"),
        ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
        ForeignKeyConstraint(["farmacia_id", "produto_id"], ["produtos.farmacia_id", "produtos.id"]),
        ForeignKeyConstraint(["farmacia_id", "cliente_id"], ["clientes.farmacia_id", "clientes.id"]),
        ForeignKeyConstraint(["farmacia_id", "venda_id"], ["vendas.farmacia_id", "vendas.id"]),
    )

    loja_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    produto_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # vazio: produto que não temos cadastrado
    descricao: Mapped[str] = mapped_column(String(200))
    quantidade: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal(1))
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    contato_nome: Mapped[str | None] = mapped_column(String(120))
    contato_telefone: Mapped[str | None] = mapped_column(String(20))
    observacao: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(12))
    origem: Mapped[str] = mapped_column(String(8), default="balcao")
    avisado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalizada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    venda_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # a venda que entregou a encomenda
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
