import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKeyConstraint, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import Base, TabelaDaFarmacia

FORMAS_PAGAMENTO = ("dinheiro", "debito", "credito", "pix")


class Caixa(TabelaDaFarmacia, Base):
    """Sessão de caixa de um operador num PDV: do valor de abertura até o fechamento."""

    __tablename__ = "caixas"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "id"),
        ForeignKeyConstraint(["farmacia_id", "terminal_id"], ["terminais.farmacia_id", "terminais.id"]),
        ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
    )

    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    # Nulos só em caixas abertos antes de existirem PDVs registrados.
    terminal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    loja_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(10), default="aberto")
    valor_abertura: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    aberto_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fechado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valor_fechamento_informado: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))


class Venda(TabelaDaFarmacia, Base):
    __tablename__ = "vendas"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "id"),
        UniqueConstraint("farmacia_id", "numero"),
        UniqueConstraint("farmacia_id", "chave_idempotencia"),
        ForeignKeyConstraint(["farmacia_id", "caixa_id"], ["caixas.farmacia_id", "caixas.id"]),
    )

    caixa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    numero: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12), default="finalizada")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    desconto: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    troco: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    # Só preenchido se o cliente pedir CPF na nota (LGPD: não coletar sem motivo).
    cliente_cpf: Mapped[str | None] = mapped_column(String(11))
    chave_idempotencia: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    finalizada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cancelada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(200))

    itens: Mapped[list["VendaItem"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="VendaItem.ordem"
    )
    pagamentos: Mapped[list["VendaPagamento"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class VendaItem(TabelaDaFarmacia, Base):
    __tablename__ = "venda_itens"
    __table_args__ = (
        ForeignKeyConstraint(["farmacia_id", "venda_id"], ["vendas.farmacia_id", "vendas.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["farmacia_id", "produto_id"], ["produtos.farmacia_id", "produtos.id"]),
    )

    venda_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    ordem: Mapped[int] = mapped_column(Integer)
    produto_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    # Descrição e preço são copiados do produto no momento da venda.
    descricao: Mapped[str] = mapped_column(String(200))
    quantidade: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    preco_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    desconto: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))


class VendaPagamento(TabelaDaFarmacia, Base):
    __tablename__ = "venda_pagamentos"
    __table_args__ = (
        ForeignKeyConstraint(["farmacia_id", "venda_id"], ["vendas.farmacia_id", "vendas.id"], ondelete="CASCADE"),
    )

    venda_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    forma: Mapped[str] = mapped_column(String(10))
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))


class PreVenda(TabelaDaFarmacia, Base):
    """Pedido montado no balcão e recebido no caixa (usado no monocaixa).

    Os itens guardam descrição e preço só para exibir. Ao receber, o PDV
    carrega os itens no carrinho e a venda usa sempre o preço do cadastro.
    """

    __tablename__ = "pre_vendas"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "numero"),
        ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
        ForeignKeyConstraint(["farmacia_id", "venda_id"], ["vendas.farmacia_id", "vendas.id"]),
    )

    loja_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    numero: Mapped[int] = mapped_column(Integer)
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(10), default="aberta")
    itens: Mapped[list[dict]] = mapped_column(JSONB)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    cliente_cpf: Mapped[str | None] = mapped_column(String(11))
    venda_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    finalizada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
