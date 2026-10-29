import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base, ComDatas, uuid7


class Farmacia(ComDatas, Base):
    __tablename__ = "farmacias"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    razao_social: Mapped[str] = mapped_column(String(200))
    nome_fantasia: Mapped[str] = mapped_column(String(200))
    cnpj: Mapped[str] = mapped_column(String(14), unique=True)
    uf: Mapped[str] = mapped_column(String(2))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
