from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from app.shared.campos import Uf, UfOpcional, texto


def _limpo(valor: object) -> object:
    if isinstance(valor, str):
        return valor.strip().upper() or None
    return valor


Conselho = Literal["CRM", "CRMV", "CRO", "CRF", "RMS"]
Nome = Annotated[str, Field(min_length=3, max_length=120)]
def _codigo(maximo: int):
    """Texto opcional em maiúsculas; vazio vira nulo."""
    return Annotated[Annotated[str, Field(max_length=maximo)] | None, BeforeValidator(_limpo), Field(default=None)]


Codigo = _codigo(20)


class ReceitaDados(BaseModel):
    """O que o balconista copia da receita (e do documento de quem compra)."""

    tipo_receituario: Annotated[int, Field(ge=1, le=5)] = Field(
        description="1 controle especial (branca 2 vias), 2 notificação B (azul), 3 notificação especial, "
        "4 notificação A (amarela), 5 antimicrobiano"
    )
    numero_notificacao: Codigo  # número impresso na notificação A, B ou especial
    data_prescricao: date
    prescritor_nome: Nome
    prescritor_conselho: Conselho = "CRM"
    prescritor_numero: Annotated[str, BeforeValidator(_limpo), Field(min_length=1, max_length=20)]
    prescritor_uf: Uf
    uso_prolongado: bool = False
    comprador_nome: texto(120)
    comprador_tipo_documento: Annotated[int, Field(ge=1, le=99)] | None = Field(
        default=None, description="Código do SNGPC; 2 é a carteira de identidade (RG)"
    )
    comprador_documento: Codigo
    comprador_orgao: _codigo(10)
    comprador_uf: UfOpcional
    paciente_nome: texto(120)
    paciente_idade: Annotated[int, Field(ge=0, le=150)] | None = None
    paciente_unidade_idade: Literal[1, 2] = Field(default=1, description="1 anos, 2 meses")
    paciente_sexo: Literal[1, 2] | None = Field(default=None, description="1 masculino, 2 feminino")
    cid: _codigo(8)


class ReceitaSaida(ReceitaDados):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    venda_id: UUID
    uso: int


class LinhaLivro(BaseModel):
    """Uma linha do livro de controlados: um movimento de um lote."""

    data: datetime
    produto_id: UUID
    produto: str
    lista: str
    lote: str
    tipo: str  # entrada, venda, perda, transferencia, devolucao, ajuste
    entrada: Decimal
    saida: Decimal
    saldo: Decimal  # saldo do produto na loja depois deste movimento
    documento: str | None  # nota de compra, venda, motivo da perda
    receita: str | None  # prescritor e notificação (na venda)
    pessoa: str | None  # comprador ou paciente (na venda)


class SaldoControlado(BaseModel):
    lote_id: UUID
    produto_id: UUID
    produto: str
    lista: str
    registro_ms: str | None
    lote: str
    validade: date | None
    quantidade: Decimal


class Pendencia(BaseModel):
    codigo: str
    texto: str
    bloqueia: bool = Field(description="Sem resolver, o arquivo do SNGPC não é gerado")


class Totais(BaseModel):
    entradas: Decimal
    vendas: Decimal
    perdas: Decimal
    transferencias: Decimal


class ResumoControlados(BaseModel):
    loja_id: UUID
    inicio: date
    fim: date
    totais: Totais
    pendencias: list[Pendencia]
    saldos: list[SaldoControlado]
    livro: list[LinhaLivro]
