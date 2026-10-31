import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKeyConstraint,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base, TabelaDaFarmacia


class Convenio(TabelaDaFarmacia, Base):
    """Empresa conveniada: os funcionários compram e ela paga uma fatura por mês."""

    __tablename__ = "convenios"
    __table_args__ = (UniqueConstraint("farmacia_id", "id"),)

    nome: Mapped[str] = mapped_column(String(120))
    cnpj: Mapped[str | None] = mapped_column(String(14))
    contato: Mapped[str | None] = mapped_column(String(120))
    telefone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(254))
    desconto: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)  # % para os funcionários
    limite_padrao: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)  # por funcionário, até fechar
    dia_fechamento: Mapped[int] = mapped_column(SmallInteger, default=25)
    dias_para_pagar: Mapped[int] = mapped_column(SmallInteger, default=10)
    observacao: Mapped[str | None] = mapped_column(String(300))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class CompraConvenio(TabelaDaFarmacia, Base):
    """A parte de uma venda paga pelo convênio. Ao fechar o mês, entra na fatura (uma conta a receber)."""

    __tablename__ = "convenio_compras"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "id"),
        UniqueConstraint("farmacia_id", "venda_id", name="uq_convenio_compras_venda"),
        ForeignKeyConstraint(["farmacia_id", "convenio_id"], ["convenios.farmacia_id", "convenios.id"]),
        ForeignKeyConstraint(["farmacia_id", "cliente_id"], ["clientes.farmacia_id", "clientes.id"]),
        ForeignKeyConstraint(["farmacia_id", "venda_id"], ["vendas.farmacia_id", "vendas.id"]),
        ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
        ForeignKeyConstraint(["farmacia_id", "conta_id"], ["contas.farmacia_id", "contas.id"]),
    )

    convenio_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    cliente_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    venda_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    loja_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    data: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default="aberta")  # aberta, faturada, cancelada
    conta_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # a fatura em que entrou
