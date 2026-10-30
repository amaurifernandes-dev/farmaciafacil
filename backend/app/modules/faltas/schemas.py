from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

Situacao = Literal["encomendas", "chegaram", "avisados", "faltas", "encerradas", "todas"]


class FaltaCriar(BaseModel):
    produto_id: UUID | None = None
    descricao: Annotated[str, Field(max_length=200)] | None = Field(
        default=None, description="Obrigatória quando o produto não é cadastrado"
    )
    quantidade: Annotated[Decimal, Field(gt=0, le=9999, max_digits=12, decimal_places=3)] = Decimal(1)
    cliente_id: UUID | None = None
    contato_nome: Annotated[str, Field(max_length=120)] | None = None
    contato_telefone: Annotated[str, Field(max_length=20)] | None = None
    observacao: Annotated[str, Field(max_length=300)] | None = None
    loja_id: UUID | None = Field(default=None, description="Vazio: a loja do caixa, ou a matriz")
    origem: Literal["balcao", "pdv"] = "balcao"

    @model_validator(mode="after")
    def _produto_ou_descricao(self):
        if self.produto_id is None and not (self.descricao or "").strip():
            raise ValueError("Escolha o produto ou escreva o que o cliente pediu")
        return self


class FaltaSaida(BaseModel):
    id: UUID
    loja_id: UUID
    loja_nome: str
    produto_id: UUID | None
    descricao: str
    quantidade: Decimal
    cliente_id: UUID | None
    nome: str | None = Field(description="Quem pediu: o cliente cadastrado ou o nome anotado")
    telefone: str | None
    observacao: str | None
    status: str
    origem: str
    encomenda: bool = Field(description="Tem alguém para avisar quando chegar")
    saldo: Decimal | None = Field(description="Quanto a loja tem agora. Vazio: produto não cadastrado")
    chegou: bool = Field(description="Encomenda esperando e a loja já tem a quantidade pedida")
    usuario_nome: str
    criado_em: datetime
    avisado_em: datetime | None
    finalizada_em: datetime | None


class MaisPedido(BaseModel):
    produto_id: UUID | None
    descricao: str
    vezes: int
    quantidade: Decimal


class ResumoFaltas(BaseModel):
    encomendas: int = Field(description="Encomendas esperando o produto chegar")
    chegaram: int = Field(description="Encomendas que já podem ser avisadas")
    avisados: int = Field(description="Avisados que ainda não buscaram")
    faltas_30_dias: int
    mais_pedidos: list[MaisPedido] = Field(description="O que mais faltou nos últimos 30 dias")


class ListaFaltas(BaseModel):
    resumo: ResumoFaltas
    itens: list[FaltaSaida]
