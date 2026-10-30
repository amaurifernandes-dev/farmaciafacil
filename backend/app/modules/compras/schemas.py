from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NotaImportar(BaseModel):
    xml: Annotated[str, Field(min_length=50, max_length=5_000_000, description="Conteúdo do arquivo XML da NF-e")]
    loja_id: UUID | None = Field(
        default=None, description="Loja que recebe a mercadoria. Vazio = a loja do CNPJ destinatário da nota"
    )


class ItemAtualizar(BaseModel):
    """Correções feitas na conferência, antes de confirmar a nota."""

    produto_id: UUID | None = None
    fator: Annotated[int, Field(ge=1, le=10_000)] | None = None
    numero_lote: str | None = Field(default=None, max_length=40)
    validade: date | None = None


class ItemNotaSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ordem: int
    codigo_fornecedor: str
    ean: str | None
    descricao: str
    ncm: str | None
    cest: str | None
    registro_ms: str | None
    unidade: str
    quantidade: Decimal
    valor_unitario: Decimal
    valor_total: Decimal
    numero_lote: str | None
    validade: date | None
    produto_id: UUID | None
    produto_nome: str | None = None
    produto_controla_lote: bool | None = None
    fator: int


class NotaResumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    loja_id: UUID
    fornecedor_id: UUID
    fornecedor_nome: str
    chave: str
    numero: int
    serie: int
    emitida_em: datetime
    valor_produtos: Decimal
    valor_total: Decimal
    status: str
    criado_em: datetime
    confirmada_em: datetime | None
    quantidade_itens: int
    itens_sem_produto: int


class NotaSaida(NotaResumo):
    itens: list[ItemNotaSaida]


class PrecoFornecedor(BaseModel):
    fornecedor_id: UUID
    fornecedor_nome: str
    custo_unitario: Decimal = Field(description="Custo por unidade de venda na última compra deste fornecedor")
    comprado_em: datetime


class ItemSugestao(BaseModel):
    produto_id: UUID
    nome: str
    apresentacao: str | None
    ean: str | None
    saldo: Decimal
    estoque_minimo: Decimal
    vendido_no_periodo: Decimal
    media_diaria: Decimal
    dias_de_estoque: Decimal | None = Field(description="Quantos dias o saldo dura no ritmo atual. Vazio = sem vendas")
    sugerido: Decimal
    ultimo_custo: Decimal | None
    fornecedores: list[PrecoFornecedor] = Field(description="Último preço de cada fornecedor, do mais barato ao mais caro")


class SugestaoCompras(BaseModel):
    loja_id: UUID
    dias_historico: int
    dias_cobertura: int
    itens: list[ItemSugestao]
    total_estimado: Decimal
