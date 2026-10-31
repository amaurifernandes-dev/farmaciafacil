import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKeyConstraint, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base, TabelaDaFarmacia


class VendaPopular(TabelaDaFarmacia, Base):
    """Uma venda pela Farmácia Popular: a parte que o governo paga, e os dados que a auditoria pede."""

    __tablename__ = "popular_vendas"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "id"),
        UniqueConstraint("farmacia_id", "venda_id", name="uq_popular_vendas_venda"),
        ForeignKeyConstraint(["farmacia_id", "venda_id"], ["vendas.farmacia_id", "vendas.id"]),
        ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
        ForeignKeyConstraint(["farmacia_id", "conta_id"], ["contas.farmacia_id", "contas.id"]),
    )

    venda_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    loja_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    data: Mapped[date] = mapped_column(Date)
    paciente_cpf: Mapped[str] = mapped_column(String(11))
    paciente_nome: Mapped[str] = mapped_column(String(120))
    prescritor_crm: Mapped[str] = mapped_column(String(20))
    prescritor_uf: Mapped[str] = mapped_column(String(2))
    receita_data: Mapped[date] = mapped_column(Date)
    autorizacao: Mapped[str] = mapped_column(String(40))
    valor_governo: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    valor_paciente: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    # [{"produto_id", "descricao", "quantidade", "total", "governo"}], só os remédios do programa.
    itens: Mapped[list[dict]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(10), default="aberta")  # aberta, lancada, cancelada
    conta_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # o lançamento do mês em que entrou
