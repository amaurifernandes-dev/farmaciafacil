from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

PercentualDesconto = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]
DiasAlerta = Annotated[int, Field(ge=1, le=365)]
DiasPrazo = Annotated[int, Field(ge=1, le=180)]
PontosPorReal = Annotated[Decimal, Field(ge=0, le=1000, max_digits=6, decimal_places=2)]
ValorPonto = Annotated[Decimal, Field(gt=0, le=100, max_digits=8, decimal_places=4)]
MinimoResgate = Annotated[int, Field(ge=1, le=1_000_000)]
ValidadeMeses = Annotated[int, Field(ge=1, le=60)]


class Configuracoes(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    desconto_maximo_caixa: PercentualDesconto
    dias_alerta_vencimento: DiasAlerta
    dias_prazo_padrao: DiasPrazo
    fidelidade_ativa: bool
    pontos_por_real: PontosPorReal
    valor_ponto: ValorPonto
    pontos_minimo_resgate: MinimoResgate
    pontos_validade_meses: ValidadeMeses | None


class ConfiguracoesAtualizar(BaseModel):
    desconto_maximo_caixa: PercentualDesconto | None = None
    dias_alerta_vencimento: DiasAlerta | None = None
    dias_prazo_padrao: DiasPrazo | None = None
    fidelidade_ativa: bool | None = None
    pontos_por_real: PontosPorReal | None = None
    valor_ponto: ValorPonto | None = None
    pontos_minimo_resgate: MinimoResgate | None = None
    pontos_validade_meses: ValidadeMeses | None = Field(default=None, description="Envie null para não expirar")
