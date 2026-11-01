import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import Base, TabelaDaFarmacia

FORMAS_PAGAMENTO = ("dinheiro", "debito", "credito", "pix", "prazo", "convenio", "popular", "vale")


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
        ForeignKeyConstraint(["farmacia_id", "cliente_id"], ["clientes.farmacia_id", "clientes.id"]),
    )

    caixa_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))  # quem passou no caixa
    # Quem vendeu (comissão): o balconista da pré-venda, ou o próprio caixa.
    vendedor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    numero: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12), default="finalizada")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    desconto: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    troco: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    # Pedido entregue em casa: a taxa entra no total (e na NFC-e como outras despesas).
    entrega: Mapped[bool] = mapped_column(Boolean, default=False)
    taxa_entrega: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    # Só preenchido se o cliente pedir CPF na nota (LGPD: não coletar sem motivo).
    cliente_cpf: Mapped[str | None] = mapped_column(String(11))
    # Obrigatório na venda a prazo: é quem fica devendo.
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    # Fidelidade: o desconto_pontos já está dentro de desconto.
    pontos_ganhos: Mapped[int] = mapped_column(Integer, default=0)
    pontos_resgatados: Mapped[int] = mapped_column(Integer, default=0)
    desconto_pontos: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    # Desconto da empresa conveniada do cliente (também já dentro de desconto).
    desconto_convenio: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    chave_idempotencia: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    # Feita no caixa sem internet e enviada depois (finalizada_em é a hora no caixa).
    offline: Mapped[bool] = mapped_column(Boolean, default=False)
    finalizada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cancelada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(200))

    itens: Mapped[list["VendaItem"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="VendaItem.ordem"
    )
    pagamentos: Mapped[list["VendaPagamento"]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    # Escrita só pelo módulo fiscal.
    nota: Mapped["NotaFiscal | None"] = relationship(lazy="selectin", viewonly=True)  # noqa: F821


class VendaItem(TabelaDaFarmacia, Base):
    __tablename__ = "venda_itens"
    __table_args__ = (
        ForeignKeyConstraint(["farmacia_id", "venda_id"], ["vendas.farmacia_id", "vendas.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["farmacia_id", "produto_id"], ["produtos.farmacia_id", "produtos.id"]),
        ForeignKeyConstraint(["farmacia_id", "promocao_id"], ["promocoes.farmacia_id", "promocoes.id"]),
    )

    venda_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    ordem: Mapped[int] = mapped_column(Integer)
    produto_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    # Descrição e preço são copiados do produto no momento da venda.
    descricao: Mapped[str] = mapped_column(String(200))
    quantidade: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    preco_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    desconto: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)  # inclui o da promoção
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    # Copiados na hora da venda, para os relatórios de lucro e de promoções.
    custo_unitario: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    promocao_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    desconto_promocao: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    # % de comissão no dia da venda. Vazio nas vendas antigas: vale a regra de hoje.
    comissao: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    # Vendido sem saldo no sistema (venda offline): o estoque do sistema estava abaixo do real.
    sem_estoque: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0)


class VendaPagamento(TabelaDaFarmacia, Base):
    __tablename__ = "venda_pagamentos"
    __table_args__ = (
        ForeignKeyConstraint(["farmacia_id", "venda_id"], ["vendas.farmacia_id", "vendas.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["farmacia_id", "vale_id"], ["vales_troca.farmacia_id", "vales_troca.id"]),
    )

    venda_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    forma: Mapped[str] = mapped_column(String(10))
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    vale_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # só na forma "vale"


class PreVenda(TabelaDaFarmacia, Base):
    """Pedido montado no balcão e recebido no caixa (usado no monocaixa).

    Os itens guardam descrição e preço só para exibir. Ao receber, o PDV
    carrega os itens no carrinho e a venda usa sempre o preço do cadastro.
    """

    __tablename__ = "pre_vendas"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "numero"),
        UniqueConstraint("farmacia_id", "id"),
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
    # Vindo de um pedido para entrega: a taxa é cobrada no caixa junto com os itens.
    entrega: Mapped[bool] = mapped_column(Boolean, default=False)
    taxa_entrega: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    # Já pago pelo cliente antes (Pix do site confirmado): o caixa recebe como Pix.
    pago_antecipado: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    venda_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    finalizada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
