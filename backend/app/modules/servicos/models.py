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
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base, TabelaDaFarmacia

TIPOS_SERVICO = ("pressao", "glicemia", "temperatura", "injetavel", "outro")


class Servico(TabelaDaFarmacia, Base):
    """Serviço que a farmácia oferece (aferição de pressão, glicemia, aplicação de injetável...)."""

    __tablename__ = "servicos"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "id"),
        UniqueConstraint("farmacia_id", "nome", name="uq_servicos_nome"),
    )

    nome: Mapped[str] = mapped_column(String(80))
    tipo: Mapped[str] = mapped_column(String(12))
    preco: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class AtendimentoServico(TabelaDaFarmacia, Base):
    """Um serviço feito para um paciente, com o resultado e a orientação do farmacêutico."""

    __tablename__ = "atendimentos_servico"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "numero", name="uq_atendimentos_servico_numero"),
        ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
        ForeignKeyConstraint(["farmacia_id", "servico_id"], ["servicos.farmacia_id", "servicos.id"]),
        ForeignKeyConstraint(["farmacia_id", "cliente_id"], ["clientes.farmacia_id", "clientes.id"]),
        ForeignKeyConstraint(["farmacia_id", "caixa_id"], ["caixas.farmacia_id", "caixas.id"]),
    )

    numero: Mapped[int] = mapped_column(Integer)
    loja_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    servico_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    servico_nome: Mapped[str] = mapped_column(String(80))
    tipo: Mapped[str] = mapped_column(String(12))
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    paciente_nome: Mapped[str] = mapped_column(String(120))
    paciente_cpf: Mapped[str | None] = mapped_column(String(11))
    paciente_nascimento: Mapped[date | None] = mapped_column(Date)
    farmaceutico_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    resultados: Mapped[dict] = mapped_column(JSONB, default=dict)
    orientacao: Mapped[str | None] = mapped_column(Text)
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    forma_pagamento: Mapped[str] = mapped_column(String(10))
    caixa_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(12), default="registrado")
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(200))
