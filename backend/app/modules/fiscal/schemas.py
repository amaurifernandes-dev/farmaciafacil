from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.produtos.schemas import Cfop, IcmsSituacao, PisCofinsSituacao
from app.shared.campos import Cpf

Ambiente = Literal["homologacao", "producao"]
Regime = Literal["simples", "presumido", "real"]


class ConfiguracaoFiscalDados(BaseModel):
    ambiente: Ambiente = "homologacao"
    emitir_automaticamente: bool = Field(default=True, description="Emite a NFC-e ao finalizar cada venda")
    cfop_padrao: Cfop = "5102"
    icms_situacao_tributaria_padrao: IcmsSituacao = Field(
        default="102", description="CSOSN no Simples Nacional (ex.: 102, 500) ou CST no regime normal"
    )
    pis_cofins_situacao_tributaria_padrao: PisCofinsSituacao = "49"
    regime: Regime = Field(default="simples", description="Simples Nacional, lucro presumido ou lucro real")
    perfil_efd: Literal["A", "B", "C"] = "A"
    contador_nome: str | None = Field(default=None, max_length=120)
    contador_cpf: Cpf = None
    contador_crc: str | None = Field(default=None, max_length=15)
    contador_email: str | None = Field(default=None, max_length=254)


class ConfiguracaoFiscalSaida(ConfiguracaoFiscalDados):
    model_config = ConfigDict(from_attributes=True)

    atualizado_em: datetime


class NotaFiscalSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    venda_id: UUID
    ambiente: str
    status: str
    tentativas: int
    numero: str | None
    serie: str | None
    chave: str | None
    status_sefaz: str | None
    mensagem: str | None
    url_danfe: str | None
    url_xml: str | None
    url_qrcode: str | None
    url_consulta: str | None
    url_xml_cancelamento: str | None
    autorizada_em: datetime | None
    cancelada_em: datetime | None



class LinhaCfop(BaseModel):
    cfop: str
    cst: str
    valor: Decimal
    icms: Decimal
    icms_st: Decimal


class ResumoSaidas(BaseModel):
    vendas: int
    total_vendido: Decimal
    nfce_autorizadas: int
    valor_nfce: Decimal
    nfce_canceladas: int
    por_cfop: list[LinhaCfop]


class ResumoEntradas(BaseModel):
    notas: int
    valor_total: Decimal
    icms: Decimal
    icms_st: Decimal
    ipi: Decimal
    por_cfop: list[LinhaCfop]


class ReceitaPgdas(BaseModel):
    normal: Decimal
    icms_st: Decimal
    monofasico: Decimal
    st_e_monofasico: Decimal
    total: Decimal


class Pendencia(BaseModel):
    tipo: str
    texto: str
    quantidade: int


class Fechamento(BaseModel):
    mes: str
    inicio: date
    fim: date
    loja_id: UUID
    loja_nome: str
    cnpj: str
    regime: str
    saidas: ResumoSaidas
    entradas: ResumoEntradas
    pgdas: ReceitaPgdas
    pendencias: list[Pendencia]
    sped_disponivel: bool
