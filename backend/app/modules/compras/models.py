import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKeyConstraint, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, deferred, mapped_column, relationship

from app.modules.fornecedores.models import Fornecedor
from app.shared.models import Base, TabelaDaFarmacia


class NotaEntrada(TabelaDaFarmacia, Base):
    """Nota de compra importada pelo XML. Só mexe no estoque quando é confirmada."""

    __tablename__ = "notas_entrada"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "id"),
        ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
        ForeignKeyConstraint(["farmacia_id", "fornecedor_id"], ["fornecedores.farmacia_id", "fornecedores.id"]),
    )

    loja_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    fornecedor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    chave: Mapped[str] = mapped_column(String(44))
    numero: Mapped[int] = mapped_column(Integer)
    serie: Mapped[int] = mapped_column(Integer)
    emitida_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valor_produtos: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    valor_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(10), default="pendente")
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    confirmada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # O XML original fica guardado (a farmácia precisa mantê-lo por 5 anos).
    xml: Mapped[str] = deferred(mapped_column(Text))

    fornecedor: Mapped[Fornecedor] = relationship(lazy="joined")
    itens: Mapped[list["NotaEntradaItem"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="NotaEntradaItem.ordem"
    )


class NotaEntradaItem(TabelaDaFarmacia, Base):
    """Item da nota. Um produto com dois lotes na nota vira dois itens."""

    __tablename__ = "notas_entrada_itens"
    __table_args__ = (
        ForeignKeyConstraint(
            ["farmacia_id", "nota_id"], ["notas_entrada.farmacia_id", "notas_entrada.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(["farmacia_id", "produto_id"], ["produtos.farmacia_id", "produtos.id"]),
    )

    nota_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    ordem: Mapped[int] = mapped_column(Integer)
    codigo_fornecedor: Mapped[str] = mapped_column(String(60))
    ean: Mapped[str | None] = mapped_column(String(14))
    descricao: Mapped[str] = mapped_column(String(200))
    ncm: Mapped[str | None] = mapped_column(String(8))
    cest: Mapped[str | None] = mapped_column(String(7))
    registro_ms: Mapped[str | None] = mapped_column(String(20))
    unidade: Mapped[str] = mapped_column(String(6))
    quantidade: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    valor_unitario: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    valor_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    numero_lote: Mapped[str | None] = mapped_column(String(40))
    validade: Mapped[date | None] = mapped_column(Date)
    produto_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    # Quantas unidades de venda vêm em cada unidade da nota (ex.: caixa com 10).
    fator: Mapped[int] = mapped_column(Integer, default=1)


class ProdutoFornecedor(TabelaDaFarmacia, Base):
    """Código que o fornecedor usa para o produto. Aprendido ao confirmar uma nota."""

    __tablename__ = "produtos_fornecedor"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "fornecedor_id", "codigo"),
        ForeignKeyConstraint(["farmacia_id", "fornecedor_id"], ["fornecedores.farmacia_id", "fornecedores.id"]),
        ForeignKeyConstraint(["farmacia_id", "produto_id"], ["produtos.farmacia_id", "produtos.id"]),
    )

    fornecedor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    codigo: Mapped[str] = mapped_column(String(60))
    produto_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    fator: Mapped[int] = mapped_column(Integer, default=1)
