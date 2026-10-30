from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.produtos.schemas import Cfop, IcmsSituacao, PisCofinsSituacao

Ambiente = Literal["homologacao", "producao"]


class ConfiguracaoFiscalDados(BaseModel):
    ambiente: Ambiente = "homologacao"
    emitir_automaticamente: bool = Field(default=True, description="Emite a NFC-e ao finalizar cada venda")
    cfop_padrao: Cfop = "5102"
    icms_situacao_tributaria_padrao: IcmsSituacao = Field(
        default="102", description="CSOSN no Simples Nacional (ex.: 102, 500) ou CST no regime normal"
    )
    pis_cofins_situacao_tributaria_padrao: PisCofinsSituacao = "49"


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

