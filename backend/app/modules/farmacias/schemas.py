from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

PercentualDesconto = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]
DiasAlerta = Annotated[int, Field(ge=1, le=365)]
DiasPrazo = Annotated[int, Field(ge=1, le=180)]


class Configuracoes(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    desconto_maximo_caixa: PercentualDesconto
    dias_alerta_vencimento: DiasAlerta
    dias_prazo_padrao: DiasPrazo


class ConfiguracoesAtualizar(BaseModel):
    desconto_maximo_caixa: PercentualDesconto | None = None
    dias_alerta_vencimento: DiasAlerta | None = None
    dias_prazo_padrao: DiasPrazo | None = None
