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
    # Entra no cálculo de comissão (o dono ou o gerente podem ficar de fora).
    recebe_comissao: Mapped[bool] = mapped_column(Boolean, default=True)
    crf: Mapped[str | None] = mapped_column(String(20))  # do farmacêutico, vai na declaração de serviço
