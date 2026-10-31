import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKeyConstraint,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modules.produtos.models import Produto
from app.shared.models import FARMACIA_DA_SESSAO, Base, TabelaDaFarmacia, uuid7

# Produtos que não controlam lote (perfumaria, por exemplo) usam um lote único com este número.
LOTE_PADRAO = "SEM-LOTE"

TIPOS_MOVIMENTO = ("entrada", "venda", "ajuste", "perda", "devolucao", "transferencia")


class Lote(TabelaDaFarmacia, Base):
    """Lote de um produto guardado numa loja. O mesmo lote em duas lojas são duas linhas."""

    __tablename__ = "lotes"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "loja_id", "produto_id", "numero_lote", name="uq_lotes_loja_produto_numero"),
        UniqueConstraint("farmacia_id", "id"),
        ForeignKeyConstraint(["farmacia_id", "produto_id"], ["produtos.farmacia_id", "produtos.id"]),
        ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
    )

    loja_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    produto_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    numero_lote: Mapped[str] = mapped_column(String(40))
    validade: Mapped[date | None] = mapped_column(Date)
    # Saldo atual. Só muda pelo serviço de estoque, junto com um movimento.
    quantidade: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0)

    produto: Mapped[Produto] = relationship(lazy="joined")


class MovimentoEstoque(Base):
    """Histórico imutável: toda mudança de saldo gera uma linha aqui."""

    __tablename__ = "movimentos_estoque"
    __table_args__ = (
        ForeignKeyConstraint(["farmacia_id", "produto_id"], ["produtos.farmacia_id", "produtos.id"]),
        ForeignKeyConstraint(["farmacia_id", "lote_id"], ["lotes.farmacia_id", "lotes.id"]),
        ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    farmacia_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, server_default=FARMACIA_DA_SESSAO
    )
    loja_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    produto_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    lote_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    tipo: Mapped[str] = mapped_column(String(20))
    quantidade: Mapped[Decimal] = mapped_column(Numeric(12, 3))  # positiva entra, negativa sai
    custo_unitario: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    referencia_tipo: Mapped[str | None] = mapped_column(String(30))
    referencia_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    motivo: Mapped[str | None] = mapped_column(String(200))
    motivo_sngpc: Mapped[int | None] = mapped_column(SmallInteger)  # perda de controlado: código da Anvisa
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lote: Mapped[Lote] = relationship(lazy="joined")
