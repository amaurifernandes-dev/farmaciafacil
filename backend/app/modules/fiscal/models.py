import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base, TabelaDaFarmacia

AMBIENTES = ("homologacao", "producao")
REGIMES = ("simples", "presumido", "real")
# processando: enviada sem resposta definitiva (ex.: timeout), precisa ser consultada de novo.
# erro: não chegou à SEFAZ (dados faltando, provedor fora do ar); pode ser reenviada.
STATUS_NOTA = ("processando", "autorizada", "rejeitada", "cancelada", "erro")


class ConfiguracaoFiscal(TabelaDaFarmacia, Base):
    """Uma por farmácia. Certificado A1, CSC, IE e endereço ficam cadastrados no provedor."""

    __tablename__ = "configuracoes_fiscais"
    __table_args__ = (UniqueConstraint("farmacia_id"),)

    ambiente: Mapped[str] = mapped_column(String(11), default="homologacao")
    emitir_automaticamente: Mapped[bool] = mapped_column(Boolean, default=True)
    # Padrões usados quando o produto não tem a própria tributação.
    cfop_padrao: Mapped[str] = mapped_column(String(4), default="5102")
    icms_situacao_tributaria_padrao: Mapped[str] = mapped_column(String(3), default="102")
    pis_cofins_situacao_tributaria_padrao: Mapped[str] = mapped_column(String(2), default="49")
    # simples: Simples Nacional (não entrega SPED Fiscal); presumido e real: regime normal.
    regime: Mapped[str] = mapped_column(String(10), default="simples")
    perfil_efd: Mapped[str] = mapped_column(String(1), default="A")
    # O contador vai no registro 0100 do SPED.
    contador_nome: Mapped[str | None] = mapped_column(String(120))
    contador_cpf: Mapped[str | None] = mapped_column(String(11))
    contador_crc: Mapped[str | None] = mapped_column(String(15))
    contador_email: Mapped[str | None] = mapped_column(String(254))


class NotaFiscal(TabelaDaFarmacia, Base):
    """NFC-e de uma venda. A referência enviada ao provedor é o id da venda, então reenviar não duplica."""

    __tablename__ = "notas_fiscais"
    __table_args__ = (
        UniqueConstraint("farmacia_id", "venda_id"),
        ForeignKeyConstraint(["farmacia_id", "venda_id"], ["vendas.farmacia_id", "vendas.id"]),
    )

    venda_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    ambiente: Mapped[str] = mapped_column(String(11))
    status: Mapped[str] = mapped_column(String(12))
    tentativas: Mapped[int] = mapped_column(Integer, default=0)
    numero: Mapped[str | None] = mapped_column(String(9))
    serie: Mapped[str | None] = mapped_column(String(3))
    chave: Mapped[str | None] = mapped_column(String(44))
    status_sefaz: Mapped[str | None] = mapped_column(String(4))
    mensagem: Mapped[str | None] = mapped_column(String(500))
    url_xml: Mapped[str | None] = mapped_column(String(500))
    url_danfe: Mapped[str | None] = mapped_column(String(500))
    url_qrcode: Mapped[str | None] = mapped_column(String(1000))
    url_consulta: Mapped[str | None] = mapped_column(String(500))
    url_xml_cancelamento: Mapped[str | None] = mapped_column(String(500))
    autorizada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
