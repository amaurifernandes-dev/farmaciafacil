from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
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
    pedido_id: UUID | None = None
    pedido_numero: int | None = None


class NotaSaida(NotaResumo):
    itens: list[ItemNotaSaida]
    pedido: "ConferenciaPedido | None" = None


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
    faltas_no_periodo: Decimal = Field(description="Quanto pediram e não tinha (anotado na lista de faltas)")
    encomendas_abertas: Decimal = Field(description="Quanto os clientes encomendaram e estão esperando")
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


# --- Pedidos de compra ---

StatusPedido = Literal["aberto", "enviado", "parcial", "recebido", "cancelado"]


class ItemPedidoCriar(BaseModel):
    produto_id: UUID
    quantidade: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=3)]
    custo_estimado: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4)] | None = None


class PedidoCompraCriar(BaseModel):
    fornecedor_id: UUID
    loja_id: UUID | None = Field(default=None, description="Loja que vai receber. Vazio = a matriz")
    itens: Annotated[list[ItemPedidoCriar], Field(min_length=1, max_length=200)]
    observacao: str | None = Field(default=None, max_length=500)


class ItemPedidoSaida(BaseModel):
    produto_id: UUID
    nome: str
    ean: str | None
    quantidade: Decimal
    recebido: Decimal
    falta_receber: Decimal
    custo_estimado: Decimal | None


class PedidoCompraResumo(BaseModel):
    id: UUID
    numero: int
    loja_id: UUID
    loja_nome: str
    fornecedor_id: UUID
    fornecedor_nome: str
    status: StatusPedido
    criado_em: datetime
    enviado_em: datetime | None
    quantidade_itens: int
    total_estimado: Decimal


class PedidoCompraSaida(PedidoCompraResumo):
    observacao: str | None
    criado_por: str
    itens: list[ItemPedidoSaida]
    notas: list[NotaResumo] = Field(description="Notas que deram baixa (ou vão dar) neste pedido")
    texto: str = Field(description="Mensagem pronta para mandar ao fornecedor")
    whatsapp: str | None = Field(description="Telefone do fornecedor no formato do wa.me")
    email: str | None


class LinhaConferencia(BaseModel):
    produto_id: UUID
    nome: str
    pedido: Decimal = Field(description="Quanto ainda faltava receber deste pedido")
    na_nota: Decimal = Field(description="Unidades de venda que vieram nesta nota")
    situacao: Literal["ok", "faltou", "sobrou", "fora_do_pedido", "nao_veio"]


class ConferenciaPedido(BaseModel):
    pedido_id: UUID
    numero: int
    status: StatusPedido
    linhas: list[LinhaConferencia]
    tudo_certo: bool


class NotaPedido(BaseModel):
    pedido_id: UUID | None = Field(description="Pedido que esta nota atende. Vazio = nenhum")


NotaSaida.model_rebuild()
