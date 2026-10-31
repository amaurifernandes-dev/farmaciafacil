import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKeyConstraint,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base, TabelaDaFarmacia


class Receita(TabelaDaFarmacia, Base):
    """Dados da receita guardados na venda de remédio controlado (vão para o SNGPC).

    Os códigos seguem o layout do SNGPC da Anvisa (tipo de receituário, documento, sexo...).
    """

    __tablename__ = "receitas"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "id"),
        UniqueConstraint("farmacia_id", "venda_id", name="uq_receitas_venda"),
        ForeignKeyConstraint(["farmacia_id", "venda_id"], ["vendas.farmacia_id", "vendas.id"]),
    )

    venda_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    # 1 controle especial, 2 notificação B, 3 notificação especial, 4 notificação A, 5 antimicrobiano
    tipo_receituario: Mapped[int] = mapped_column(SmallInteger)
    numero_notificacao: Mapped[str | None] = mapped_column(String(20))
    data_prescricao: Mapped[date] = mapped_column(Date)
    prescritor_nome: Mapped[str] = mapped_column(String(120))
    prescritor_conselho: Mapped[str] = mapped_column(String(4))
    prescritor_numero: Mapped[str] = mapped_column(String(20))
    prescritor_uf: Mapped[str] = mapped_column(String(2))
    uso: Mapped[int] = mapped_column(SmallInteger, default=1)  # 1 humano, 2 veterinário
    uso_prolongado: Mapped[bool] = mapped_column(Boolean, default=False)
    comprador_nome: Mapped[str | None] = mapped_column(String(120))
    comprador_tipo_documento: Mapped[int | None] = mapped_column(SmallInteger)
    comprador_documento: Mapped[str | None] = mapped_column(String(30))
    comprador_orgao: Mapped[str | None] = mapped_column(String(10))
    comprador_uf: Mapped[str | None] = mapped_column(String(2))
    paciente_nome: Mapped[str | None] = mapped_column(String(120))
    paciente_idade: Mapped[int | None] = mapped_column(SmallInteger)
    paciente_unidade_idade: Mapped[int | None] = mapped_column(SmallInteger)  # 1 anos, 2 meses
    paciente_sexo: Mapped[int | None] = mapped_column(SmallInteger)  # 1 masculino, 2 feminino
    cid: Mapped[str | None] = mapped_column(String(8))
