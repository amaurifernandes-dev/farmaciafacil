from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.modules.farmacias.schemas import TaxaBairro

Canal = Literal["site", "whatsapp", "telefone"]
Forma = Literal["dinheiro", "cartao", "pix"]
Situacao = Literal["abertos", "novo", "separando", "pronto", "saiu", "entregue", "cancelado", "todos"]


class ItemPedidoCriar(BaseModel):
    produto_id: UUID
    quantidade: Annotated[Decimal, Field(gt=0, le=50, max_digits=12, decimal_places=3)]


class PedidoCriar(BaseModel):
    itens: Annotated[list[ItemPedidoCriar], Field(min_length=1, max_length=30)]
    nome: Annotated[str, Field(min_length=2, max_length=120)]
    telefone: Annotated[str, Field(min_length=8, max_length=20, pattern=r"^[\d\s()+-]+$")]
    entrega: bool = False
    endereco: Annotated[str, Field(max_length=300)] | None = None
    bairro: Annotated[str, Field(max_length=60)] | None = Field(
        default=None, description="Obrigatório na entrega quando a farmácia cobra por bairro"
    )
    forma_pagamento: Forma = "pix"
    troco_para: Annotated[Decimal, Field(gt=0, le=100_000, max_digits=12, decimal_places=2)] | None = None
    observacao: Annotated[str, Field(max_length=300)] | None = None

    @model_validator(mode="after")
    def _endereco_na_entrega(self):
        if self.entrega and not (self.endereco or "").strip():
            raise ValueError("Informe o endereço para a entrega")
        return self


class PedidoBalcaoCriar(PedidoCriar):
    """Pedido anotado pela farmácia (chegou pelo WhatsApp ou telefone)."""

    canal: Literal["whatsapp", "telefone"] = "whatsapp"
    loja_id: UUID | None = None


class PedidoCancelar(BaseModel):
    motivo: Annotated[str, Field(min_length=3, max_length=200)]


class ItemPedidoSaida(BaseModel):
    produto_id: UUID
    descricao: str
    quantidade: Decimal
    preco_unitario: Decimal
    desconto: Decimal
    total: Decimal


class PedidoSaida(BaseModel):
    id: UUID
    numero: int
    codigo: str
    canal: str
    loja_id: UUID
    loja_nome: str
    cliente_id: UUID | None
    nome: str
    telefone: str
    entrega: bool
    endereco: str | None
    forma_pagamento: str
    troco_para: Decimal | None
    observacao: str | None
    bairro: str | None
    taxa_entrega: Decimal
    total: Decimal
    status: str
    motivo_cancelamento: str | None
    pix_copia_e_cola: str | None = Field(description="Pix com o valor do pedido, para mandar ao cliente")
    pix_pago_em: datetime | None
    pre_venda_numero: int | None
    pago: bool = Field(description="O caixa já recebeu a pré-venda do pedido")
    itens: list[ItemPedidoSaida]
    criado_em: datetime
    atualizado_em: datetime


class ResumoPedidos(BaseModel):
    novo: int
    separando: int
    pronto: int
    saiu: int
    entregues_hoje: int
    total_hoje: Decimal


class ListaPedidos(BaseModel):
    resumo: ResumoPedidos
    pedidos: list[PedidoSaida]


# --- Loja online (público) ---

class LojaPublica(BaseModel):
    nome: str
    mensagem: str | None
    whatsapp: str | None
    telefone: str | None
    endereco: str | None
    cidade: str | None
    uf: str
    entrega: bool
    entrega_minimo: Decimal
    entrega_area: str | None
    entrega_taxa: Decimal
    entrega_gratis_acima: Decimal | None
    bairros: list[TaxaBairro] = Field(description="Vazio: entrega em qualquer bairro, com a taxa padrão")
    pix: bool = Field(description="Aceita Pix pelo site, com QR Code na hora")


class ProdutoPublico(BaseModel):
    id: UUID
    nome: str
    apresentacao: str | None
    fabricante: str | None
    preco: Decimal
    preco_promocional: Decimal | None = Field(description="Preço da unidade com a promoção")
    promocao: str | None = Field(description="Ex.: Leve 3, pague 2")
    maximo: int = Field(description="Quanto dá para pedir de uma vez (sem mostrar o estoque)")


class Catalogo(BaseModel):
    produtos: list[ProdutoPublico]
    total: int


class PedidoPublico(BaseModel):
    numero: int
    codigo: str
    status: str
    entrega: bool
    forma_pagamento: str
    troco_para: Decimal | None
    taxa_entrega: Decimal
    total: Decimal
    itens: list[ItemPedidoSaida]
    criado_em: datetime
    motivo_cancelamento: str | None
    pix_copia_e_cola: str | None = Field(description="Enquanto o Pix do site não foi confirmado pela farmácia")
    pix_pago: bool
