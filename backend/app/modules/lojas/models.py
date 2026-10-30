import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base, TabelaDaFarmacia

MODOS_CAIXA = ("mono", "multi")


class Loja(TabelaDaFarmacia, Base):
    """Unidade da farmácia: a matriz e as filiais, cada uma com o seu CNPJ."""

    __tablename__ = "lojas"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "id"),
        UniqueConstraint("farmacia_id", "cnpj"),
        ForeignKeyConstraint(
            ["farmacia_id", "terminal_central_id"],
            ["terminais.farmacia_id", "terminais.id"],
            name="fk_lojas_terminal_central",
            use_alter=True,
        ),
    )

    nome: Mapped[str] = mapped_column(String(60))
    matriz: Mapped[bool] = mapped_column(Boolean, default=False)
    razao_social: Mapped[str] = mapped_column(String(200))
    nome_fantasia: Mapped[str] = mapped_column(String(200))
    cnpj: Mapped[str] = mapped_column(String(14))
    inscricao_estadual: Mapped[str | None] = mapped_column(String(20))
    telefone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(254))
    cep: Mapped[str | None] = mapped_column(String(8))
    endereco: Mapped[str | None] = mapped_column(String(200))
    bairro: Mapped[str | None] = mapped_column(String(100))
    cidade: Mapped[str | None] = mapped_column(String(100))
    uf: Mapped[str] = mapped_column(String(2))
    responsavel_tecnico: Mapped[str | None] = mapped_column(String(120))
    crf: Mapped[str | None] = mapped_column(String(20))
    # mono: um PDV central recebe tudo; multi: cada PDV ativo abre o próprio caixa.
    modo_caixa: Mapped[str] = mapped_column(String(10), default="mono")
    terminal_central_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Terminal(TabelaDaFarmacia, Base):
    """Computador registrado como PDV (frente de caixa).

    O computador é reconhecido por uma chave secreta guardada no navegador dele,
    e não pelo IP: o servidor está na nuvem e veria o mesmo IP do roteador para
    todos os computadores da loja, e o IP muda quando a internet reconecta.
    """

    __tablename__ = "terminais"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "id"),
        UniqueConstraint("farmacia_id", "loja_id", "nome"),
        ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
    )

    loja_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    nome: Mapped[str] = mapped_column(String(40))
    chave_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    vinculado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_uso_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
