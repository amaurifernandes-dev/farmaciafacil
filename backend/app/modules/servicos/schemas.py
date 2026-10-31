from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.shared.campos import Cpf, UfOpcional

TipoServico = Literal["pressao", "glicemia", "temperatura", "injetavel", "outro"]
FormaServico = Literal["dinheiro", "pix", "debito", "credito", "cortesia"]
Preco = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class ServicoCriar(BaseModel):
    nome: Annotated[str, Field(min_length=3, max_length=80)]
    tipo: TipoServico
    preco: Preco = Decimal(0)


class ServicoAtualizar(BaseModel):
    nome: Annotated[str, Field(min_length=3, max_length=80)] | None = None
    preco: Preco | None = None
    ativo: bool | None = None


class ServicoSaida(BaseModel):
    id: UUID
    nome: str
    tipo: TipoServico
    preco: Decimal
    ativo: bool


class Pressao(BaseModel):
    sistolica: Annotated[int, Field(ge=50, le=300)]
    diastolica: Annotated[int, Field(ge=30, le=200)]
    frequencia: Annotated[int, Field(ge=30, le=220)] | None = None  # batimentos por minuto
    braco: Literal["esquerdo", "direito"] | None = None

    @model_validator(mode="after")
    def _maior_que_menor(self):
        if self.diastolica >= self.sistolica:
            raise ValueError("A pressão máxima (sistólica) tem que ser maior que a mínima (diastólica)")
        return self


class Glicemia(BaseModel):
    valor: Annotated[int, Field(ge=10, le=800)]  # mg/dL
    jejum: bool = False


class Temperatura(BaseModel):
    graus: Annotated[Decimal, Field(ge=30, le=45, max_digits=3, decimal_places=1)]


class Injetavel(BaseModel):
    medicamento: Annotated[str, Field(min_length=2, max_length=120)]
    dose: Annotated[str, Field(min_length=1, max_length=40)]
    via: Literal["IM", "SC", "ID"]  # intramuscular, subcutânea, intradérmica
    local: Annotated[str, Field(max_length=60)] | None = None
    lote: Annotated[str, Field(max_length=40)] | None = None
    validade: date | None = None
    prescritor: Annotated[str, Field(min_length=3, max_length=120)]
    prescritor_crm: Annotated[str, Field(min_length=3, max_length=20)]
    prescritor_uf: UfOpcional = None
    receita_data: date


class Outro(BaseModel):
    descricao: Annotated[str, Field(min_length=3, max_length=500)]


MODELOS = {"pressao": Pressao, "glicemia": Glicemia, "temperatura": Temperatura, "injetavel": Injetavel,
           "outro": Outro}


class AtendimentoCriar(BaseModel):
    servico_id: UUID
    loja_id: UUID | None = None
    cliente_id: UUID | None = None
    paciente_nome: Annotated[str, Field(min_length=3, max_length=120)] | None = None
    paciente_cpf: Cpf = None
    paciente_nascimento: date | None = None
    resultados: dict = Field(default_factory=dict)
    orientacao: Annotated[str, Field(max_length=1000)] | None = None
    forma_pagamento: FormaServico = "dinheiro"
    valor: Preco | None = None  # vazio: o preço do serviço

    @model_validator(mode="after")
    def _paciente(self):
        if self.cliente_id is None and not self.paciente_nome:
            raise ValueError("Escolha o cliente ou informe o nome do paciente")
        return self


class Cancelar(BaseModel):
    motivo: Annotated[str, Field(min_length=3, max_length=200)]


class Aviso(BaseModel):
    nivel: Literal["alerta", "atencao"]
    texto: str


class AtendimentoSaida(BaseModel):
    id: UUID
    numero: int
    criado_em: datetime
    loja_id: UUID
    loja_nome: str
    servico_id: UUID
    servico_nome: str
    tipo: TipoServico
    cliente_id: UUID | None
    paciente_nome: str
    paciente_cpf: str | None
    paciente_nascimento: date | None
    farmaceutico: str
    farmaceutico_crf: str | None
    resultados: dict
    resultado_texto: str
    aviso: Aviso | None
    orientacao: str | None
    valor: Decimal
    forma_pagamento: FormaServico
    status: Literal["registrado", "cancelado"]
    motivo_cancelamento: str | None


class ListaAtendimentos(BaseModel):
    itens: list[AtendimentoSaida]
    total_recebido: Decimal
    por_servico: dict[str, int]
