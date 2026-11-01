import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class LicencaInstalada(Base):
    """O código de licença que veio da central, por CNPJ. Sem RLS: é lido antes do login (tela da licença)."""

    __tablename__ = "licencas_instaladas"

    cnpj: Mapped[str] = mapped_column(String(14), primary_key=True)
    codigo: Mapped[str] = mapped_column(Text)
    # Para renovar sozinho pela internet. Vazio: só renova colando um código novo.
    chave_ativacao: Mapped[str | None] = mapped_column(String(29))
    emitida_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    instalada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ultima_tentativa_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_erro: Mapped[str | None] = mapped_column(String(300))


class ServidorLocal(Base):
    """Uma linha só: a identidade deste servidor e a maior data já vista (para notar relógio voltado)."""

    __tablename__ = "servidor_local"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    maquina_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4)
    maior_data: Mapped[date | None] = mapped_column(Date)
