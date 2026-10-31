import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKeyConstraint, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base, TabelaDaFarmacia

TIPOS = ("pagar", "receber")

# Plano de contas simples. A chave fica gravada; o nome é o que aparece na tela.
CATEGORIAS = {
    "pagar": {
        "fornecedores": "Fornecedores (mercadoria)",
        "aluguel": "Aluguel e condomínio",
        "salarios": "Salários e encargos",
        "impostos": "Impostos e taxas",
        "contas_consumo": "Água, luz, telefone e internet",
        "servicos": "Serviços (contador, sistema, manutenção)",
        "cartao": "Taxas de cartão e banco",
        "outras": "Outras despesas",
    },
    "receber": {
        "venda_prazo": "Venda a prazo (fiado)",
        "convenio": "Convênio de empresa",
        "outras": "Outras receitas",
    },
}

FORMAS_BAIXA = ("dinheiro", "pix", "boleto", "transferencia", "debito", "credito", "cheque")


class Conta(TabelaDaFarmacia, Base):
    """Uma parcela a pagar ou a receber. "Vencida" não é gravado: é aberta com vencimento antes de hoje."""

    __tablename__ = "contas"
    __table_args__ = (
        ForeignKeyConstraint(["farmacia_id", "loja_id"], ["lojas.farmacia_id", "lojas.id"]),
        ForeignKeyConstraint(["farmacia_id", "fornecedor_id"], ["fornecedores.farmacia_id", "fornecedores.id"]),
        ForeignKeyConstraint(["farmacia_id", "cliente_id"], ["clientes.farmacia_id", "clientes.id"]),
        ForeignKeyConstraint(["farmacia_id", "caixa_id"], ["caixas.farmacia_id", "caixas.id"]),
        ForeignKeyConstraint(["farmacia_id", "nota_entrada_id"], ["notas_entrada.farmacia_id", "notas_entrada.id"]),
        ForeignKeyConstraint(["farmacia_id", "venda_id"], ["vendas.farmacia_id", "vendas.id"]),
        ForeignKeyConstraint(["farmacia_id", "convenio_id"], ["convenios.farmacia_id", "convenios.id"]),
        UniqueConstraint("farmacia_id", "id"),
    )

    tipo: Mapped[str] = mapped_column(String(8))
    loja_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    descricao: Mapped[str] = mapped_column(String(200))
    categoria: Mapped[str] = mapped_column(String(30))
    fornecedor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    documento: Mapped[str | None] = mapped_column(String(60))
    parcela: Mapped[int] = mapped_column(Integer, default=1)
    parcelas: Mapped[int] = mapped_column(Integer, default=1)
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    vencimento: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default="aberta")
    pago_em: Mapped[date | None] = mapped_column(Date)
    valor_pago: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    forma_pagamento: Mapped[str | None] = mapped_column(String(20))
    caixa_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    nota_entrada_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    venda_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    convenio_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # fatura mensal de um convênio
    observacao: Mapped[str | None] = mapped_column(String(300))
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    baixada_por: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
