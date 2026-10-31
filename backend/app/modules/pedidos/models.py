import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import Base, TabelaDaFarmacia

CANAIS = ("site", "whatsapp", "telefone")
# novo → separando (virou pré-venda) → pronto (retirada) ou saiu (entrega) → entregue
STATUS = ("novo", "separando", "pronto", "saiu", "entregue", "cancelado")
EM_ANDAMENTO = ("novo", "separando", "pronto", "saiu")
FORMAS = ("dinheiro", "cartao", "pix")


class Pedido(TabelaDaFarmacia, Base):
    """Pedido que chega de fora do balcão. A farmácia confirma e ele vira pré-venda para o caixa receber."""

    __tablename__ = "pedidos"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "id"),
        UniqueConstraint("farmacia_id", "numero"),
        ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
        ForeignKeyConstraint(["farmacia_id", "cliente_id"], ["clientes.farmacia_id", "clientes.id"]),
        ForeignKeyConstraint(["farmacia_id", "pre_venda_id"], ["pre_vendas.farmacia_id", "pre_vendas.id"]),
    )

    numero: Mapped[int] = mapped_column(Integer)
    codigo: Mapped[str] = mapped_column(String(16), unique=True)  # para o cliente acompanhar sem login
    canal: Mapped[str] = mapped_column(String(10))
    loja_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    nome: Mapped[str] = mapped_column(String(120))
    telefone: Mapped[str] = mapped_column(String(20))
    entrega: Mapped[bool] = mapped_column(Boolean)
    endereco: Mapped[str | None] = mapped_column(String(300))
    forma_pagamento: Mapped[str] = mapped_column(String(10))
    troco_para: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    observacao: Mapped[str | None] = mapped_column(String(300))
    bairro: Mapped[str | None] = mapped_column(String(60))
    taxa_entrega: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal(0))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # itens + taxa de entrega
    status: Mapped[str] = mapped_column(String(10), default="novo")
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(200))
    pre_venda_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # quem anotou (WhatsApp, telefone)
    # Pix pelo site: o identificador vai no QR Code; quem confere o extrato marca como recebido.
    pix_txid: Mapped[str | None] = mapped_column(String(25))
    pix_pago_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pix_confirmado_por: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    itens: Mapped[list["PedidoItem"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class PedidoItem(TabelaDaFarmacia, Base):
    __tablename__ = "pedido_itens"
    __table_args__ = (
        ForeignKeyConstraint(["farmacia_id", "pedido_id"], ["pedidos.farmacia_id", "pedidos.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["farmacia_id", "produto_id"], ["produtos.farmacia_id", "produtos.id"]),
    )

    pedido_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    produto_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    descricao: Mapped[str] = mapped_column(String(400))
    quantidade: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    preco_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    desconto: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal(0))  # da promoção
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
