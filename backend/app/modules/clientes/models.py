from datetime import date, datetime

from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base, TabelaDaFarmacia


class Cliente(TabelaDaFarmacia, Base):
    """Cadastro opcional. Ofertas só com consentimento registrado (LGPD)."""

    __tablename__ = "clientes"
    __table_args__ = (UniqueConstraint("farmacia_id", "cpf"), UniqueConstraint("farmacia_id", "id"))

    nome: Mapped[str] = mapped_column(String(120))
    cpf: Mapped[str | None] = mapped_column(String(11))
    data_nascimento: Mapped[date | None] = mapped_column(Date)
    telefone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(254))
    cep: Mapped[str | None] = mapped_column(String(8))
    endereco: Mapped[str | None] = mapped_column(String(200))
    bairro: Mapped[str | None] = mapped_column(String(100))
    cidade: Mapped[str | None] = mapped_column(String(100))
    uf: Mapped[str | None] = mapped_column(String(2))
    aceita_ofertas: Mapped[bool] = mapped_column(Boolean, default=False)
    consentimento_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observacoes: Mapped[str | None] = mapped_column(String(500))
    # Quanto o cliente pode dever na venda a prazo. Vazio ou zero: não compra a prazo.
    limite_credito: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
