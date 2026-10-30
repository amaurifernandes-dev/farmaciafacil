import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Integer, Numeric, String
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

    # Configurações gerais
    # Desconto máximo que um operador de caixa pode dar sozinho, em % do subtotal.
    desconto_maximo_caixa: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal(10))
    dias_alerta_vencimento: Mapped[int] = mapped_column(Integer, default=30)
    # Vencimento padrão da venda a prazo (fiado), em dias.
    dias_prazo_padrao: Mapped[int] = mapped_column(Integer, default=30)

    # Fidelidade: o cliente identificado ganha pontos por real gasto e troca por desconto.
    fidelidade_ativa: Mapped[bool] = mapped_column(Boolean, default=False)
    pontos_por_real: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal(1))
    valor_ponto: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.05"))
    pontos_minimo_resgate: Mapped[int] = mapped_column(Integer, default=100)
    # Vazio: não expiram. Senão, expiram se o cliente ficar esse tempo sem comprar.
    pontos_validade_meses: Mapped[int | None] = mapped_column(Integer, default=12)

    # Loja online: página pública da farmácia em /loja/<endereco>.
    loja_online_ativa: Mapped[bool] = mapped_column(Boolean, default=False)
    loja_online_endereco: Mapped[str | None] = mapped_column(String(40), unique=True)
    loja_online_loja_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # vazio: a matriz
    loja_online_mensagem: Mapped[str | None] = mapped_column(String(300))
    whatsapp: Mapped[str | None] = mapped_column(String(20))
    entrega_ativa: Mapped[bool] = mapped_column(Boolean, default=False)
    entrega_minimo: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal(0))
    entrega_area: Mapped[str | None] = mapped_column(String(200))
