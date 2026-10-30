from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base, TabelaDaFarmacia

PAPEIS = ("admin", "gerente", "farmaceutico", "caixa", "atendente", "estoque")


class Usuario(TabelaDaFarmacia, Base):
    __tablename__ = "usuarios"

    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    senha_hash: Mapped[str] = mapped_column(String(100))
    papel: Mapped[str] = mapped_column(String(20))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
