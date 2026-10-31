from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

Escopo = Literal["geral", "parcial"]


class InventarioCriar(BaseModel):
    loja_id: UUID | None = Field(default=None, description="Vazio = matriz")
    descricao: Annotated[str, Field(min_length=3, max_length=80)] = "Inventário geral"
    escopo: Escopo = "parcial"


class Contar(BaseModel):
    """Uma bipada (somar 1) ou a quantidade digitada (somar ou trocar pelo total)."""

    codigo: Annotated[str, Field(min_length=1, max_length=14)] | None = None
    produto_id: UUID | None = None
    quantidade: Annotated[Decimal, Field(ge=-9999, le=99999, max_digits=12, decimal_places=3)] = Decimal(1)
    modo: Literal["somar", "definir"] = "somar"

    @model_validator(mode="after")
    def _um_produto(self):
        if (self.codigo is None) == (self.produto_id is None):
            raise ValueError("Informe o código de barras ou o produto")
        if self.modo == "definir" and self.quantidade < 0:
            raise ValueError("A quantidade contada não pode ser negativa")
        if self.modo == "somar" and self.quantidade == 0:
            raise ValueError("Informe uma quantidade diferente de zero")
        return self


class ItemSaida(BaseModel):
    produto_id: UUID
    nome: str
    apresentacao: str | None
    ean: str | None
    quantidade: Decimal
    contado: bool
    # Só quem cuida do estoque vê o saldo do sistema: quem conta, conta "às cegas".
    saldo_sistema: Decimal | None
    diferenca: Decimal | None
    custo_unitario: Decimal | None
    valor_diferenca: Decimal | None
    atualizado_em: datetime


class Resumo(BaseModel):
    produtos_contados: int
    unidades_contadas: Decimal
    com_diferenca: int | None
    valor_sobra: Decimal | None
    valor_falta: Decimal | None
    sem_custo: int | None  # produtos com diferença sem preço de custo no cadastro
    nao_contados: int | None  # inventário geral: produtos com saldo que ninguém contou (vão para zero)


class InventarioSaida(BaseModel):
    id: UUID
    loja_id: UUID
    loja_nome: str
    descricao: str
    escopo: Escopo
    status: str
    aberto_por: str
    criado_em: datetime
    finalizado_por: str | None
    finalizado_em: datetime | None
    produtos_ajustados: int | None
    valor_sobra: Decimal | None
    valor_falta: Decimal | None


class InventarioDetalhe(InventarioSaida):
    resumo: Resumo
    itens: list[ItemSaida]
    nao_contados: list[ItemSaida] | None
    ve_saldo: bool
