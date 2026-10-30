from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base, TabelaDaFarmacia


class Fornecedor(TabelaDaFarmacia, Base):
    __tablename__ = "fornecedores"
    __table_args__ = (UniqueConstraint("farmacia_id", "cnpj"), UniqueConstraint("farmacia_id", "id"))

    razao_social: Mapped[str] = mapped_column(String(200))
    nome_fantasia: Mapped[str | None] = mapped_column(String(200))
    cnpj: Mapped[str | None] = mapped_column(String(14))
    inscricao_estadual: Mapped[str | None] = mapped_column(String(20))
    contato: Mapped[str | None] = mapped_column(String(120))
    telefone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(254))
    cep: Mapped[str | None] = mapped_column(String(8))
    endereco: Mapped[str | None] = mapped_column(String(200))
    bairro: Mapped[str | None] = mapped_column(String(100))
    cidade: Mapped[str | None] = mapped_column(String(100))
    uf: Mapped[str | None] = mapped_column(String(2))
    observacoes: Mapped[str | None] = mapped_column(String(500))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
