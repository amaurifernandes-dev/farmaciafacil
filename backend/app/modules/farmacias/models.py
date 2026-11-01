import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
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
    # Farmácia Popular: validade da receita e dias até o paciente levar o mesmo remédio de novo (0: não confere).
    popular_validade_receita: Mapped[int] = mapped_column(Integer, default=180)
    popular_intervalo_dias: Mapped[int] = mapped_column(Integer, default=30)
    # Comissão dos vendedores, em % do que venderam (o produto pode ter outra).
    comissao_padrao: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal(0))

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
    # Taxa de entrega: a padrão, ou a do bairro quando há lista de bairros ([{"bairro": ..., "taxa": "5.00"}]).
    # Com a lista preenchida, o site só entrega nesses bairros.
    entrega_taxa: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal(0))
    entrega_gratis_acima: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    entrega_bairros: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    # Pix no site: QR Code com a chave da própria farmácia (sem banco intermediário); a equipe confirma o recebimento.
    pix_chave: Mapped[str | None] = mapped_column(String(77))
    pix_nome: Mapped[str | None] = mapped_column(String(25))
    pix_cidade: Mapped[str | None] = mapped_column(String(15))
    pix_no_site: Mapped[bool] = mapped_column(Boolean, default=False)
    # Perfis que podem usar o assistente de IA. Lista vazia: assistente desligado para todos.
    assistente_perfis: Mapped[list[str]] = mapped_column(
        JSONB, default=lambda: ["admin", "gerente", "farmaceutico", "caixa", "atendente", "estoque"]
    )
    # Funções desligadas no Gerenciamento de telas: somem para todos e as rotas respondem 403.
    modulos_desligados: Mapped[list[str]] = mapped_column(JSONB, default=list)
