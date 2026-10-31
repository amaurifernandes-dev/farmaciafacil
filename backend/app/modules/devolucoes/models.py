import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import Base, TabelaDaFarmacia

DESTINOS = ("dinheiro", "vale")


class ValeTroca(TabelaDaFarmacia, Base):
    """Crédito do cliente na loja, gerado numa devolução e usado como pagamento no PDV."""

    __tablename__ = "vales_troca"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "id"),
        UniqueConstraint("farmacia_id", "codigo", name="uq_vales_troca_codigo"),
        ForeignKeyConstraint(["farmacia_id", "cliente_id"], ["clientes.farmacia_id", "clientes.id"]),
    )

    codigo: Mapped[str] = mapped_column(String(10))
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    saldo: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    validade: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default="ativo")  # ativo, usado ou cancelado


class Devolucao(TabelaDaFarmacia, Base):
    """Itens de uma venda que o cliente trouxe de volta, e como recebeu o valor."""

    __tablename__ = "devolucoes"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "id"),
        UniqueConstraint("farmacia_id", "numero", name="uq_devolucoes_numero"),
        ForeignKeyConstraint(["farmacia_id", "venda_id"], ["vendas.farmacia_id", "vendas.id"]),
        ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
        ForeignKeyConstraint(["farmacia_id", "caixa_id"], ["caixas.farmacia_id", "caixas.id"]),
        ForeignKeyConstraint(["farmacia_id", "vale_id"], ["vales_troca.farmacia_id", "vales_troca.id"]),
    )

    numero: Mapped[int] = mapped_column(Integer)
    venda_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    loja_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    destino: Mapped[str] = mapped_column(String(10))
    caixa_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    vale_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    valor_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    motivo: Mapped[str] = mapped_column(String(200))

    itens: Mapped[list["ItemDevolucao"]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    vale: Mapped[ValeTroca | None] = relationship(lazy="joined")


class ItemDevolucao(TabelaDaFarmacia, Base):
    __tablename__ = "devolucao_itens"
    __table_args__ = (
        ForeignKeyConstraint(
            ["farmacia_id", "devolucao_id"], ["devolucoes.farmacia_id", "devolucoes.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(["farmacia_id", "produto_id"], ["produtos.farmacia_id", "produtos.id"]),
    )

    devolucao_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    venda_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("venda_itens.id"))
    produto_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    descricao: Mapped[str] = mapped_column(String(200))
    quantidade: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    # Falso quando o produto não pode voltar para a prateleira (ex.: remédio que saiu da loja).
    volta_estoque: Mapped[bool] = mapped_column(Boolean)
