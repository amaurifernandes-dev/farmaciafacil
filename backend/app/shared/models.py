import secrets
import time
import uuid
from datetime import datetime

from sqlalchemy import DateTime, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Usado como valor padrão de farmacia_id: o banco preenche com a farmácia da transação.
FARMACIA_DA_SESSAO = text("NULLIF(current_setting('app.farmacia_id', true), '')::uuid")


def uuid7() -> uuid.UUID:
    """UUID versão 7: começa pelo horário, então fica ordenado por criação."""
    ms = time.time_ns() // 1_000_000
    aleatorio = secrets.randbits(74)
    valor = (
        (ms << 80)
        | (0x7 << 76)
        | ((aleatorio >> 62) << 64)
        | (0b10 << 62)
        | (aleatorio & ((1 << 62) - 1))
    )
    return uuid.UUID(int=valor)


class Base(DeclarativeBase):
    pass


class ComDatas:
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TabelaDaFarmacia(ComDatas):
    """Campos comuns a toda tabela de negócio (multi-tenant)."""

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    farmacia_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, server_default=FARMACIA_DA_SESSAO
    )
