"""Tabelas do banco da central. Ficam num banco PostgreSQL só delas, separado do banco das farmácias."""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class BaseCentral(DeclarativeBase):
    pass


class UsuarioCentral(BaseCentral):
    __tablename__ = "usuarios_central"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    senha_hash: Mapped[str] = mapped_column(String(100))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class LicencaCentral(BaseCentral):
    """O cadastro do cliente e o contrato. A chave assinada é gerada a partir daqui a cada pedido."""

    __tablename__ = "licencas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cnpj: Mapped[str] = mapped_column(String(14), index=True)
    nome: Mapped[str] = mapped_column(String(200))
    contato: Mapped[str | None] = mapped_column(String(200))
    tipo: Mapped[str] = mapped_column(String(10))  # nuvem | farmacia
    plano: Mapped[str] = mapped_column(String(10))  # mensal | anual | vitalicio
    inicio: Mapped[date] = mapped_column(Date)
    vence: Mapped[date | None] = mapped_column(Date)
    tolerancia_dias: Mapped[int] = mapped_column(Integer, default=7)
    max_usuarios: Mapped[int | None] = mapped_column(Integer)
    max_caixas: Mapped[int | None] = mapped_column(Integer)
    modulos: Mapped[list[str] | None] = mapped_column(JSONB)
    # Chave de ativação, como a do Windows. O servidor da farmácia usa para buscar e renovar a licença.
    chave_ativacao: Mapped[str] = mapped_column(String(29), unique=True)
    # Código do servidor onde a licença foi ativada. Vazio: ainda não ativada (ou troca liberada).
    maquina: Mapped[str | None] = mapped_column(String(19))
    suspensa: Mapped[bool] = mapped_column(Boolean, default=False)
    observacao: Mapped[str | None] = mapped_column(Text)
    ultima_consulta_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class HistoricoLicenca(BaseCentral):
    __tablename__ = "historico_licencas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    licenca_id: Mapped[int] = mapped_column(ForeignKey("licencas.id", ondelete="CASCADE"), index=True)
    quando: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    quem: Mapped[str] = mapped_column(String(120))
    o_que: Mapped[str] = mapped_column(String(300))
