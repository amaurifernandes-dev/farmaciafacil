from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

PercentualDesconto = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]
DiasAlerta = Annotated[int, Field(ge=1, le=365)]
DiasPrazo = Annotated[int, Field(ge=1, le=180)]
PontosPorReal = Annotated[Decimal, Field(ge=0, le=1000, max_digits=6, decimal_places=2)]
ValorPonto = Annotated[Decimal, Field(gt=0, le=100, max_digits=8, decimal_places=4)]
MinimoResgate = Annotated[int, Field(ge=1, le=1_000_000)]
ValidadeMeses = Annotated[int, Field(ge=1, le=60)]
EnderecoLoja = Annotated[str, Field(min_length=3, max_length=40, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]
ValidadeReceita = Annotated[int, Field(ge=30, le=365)]
IntervaloPopular = Annotated[int, Field(ge=0, le=90)]
Valor = Annotated[Decimal, Field(ge=0, le=100_000, max_digits=12, decimal_places=2)]


class TaxaBairro(BaseModel):
    bairro: Annotated[str, Field(min_length=2, max_length=60)]
    taxa: Annotated[Decimal, Field(ge=0, le=1000, max_digits=8, decimal_places=2)]


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
    loja_online_ativa: bool
    loja_online_endereco: str | None
    loja_online_loja_id: UUID | None
    loja_online_mensagem: str | None
    whatsapp: str | None
    entrega_ativa: bool
    entrega_minimo: Decimal
    entrega_area: str | None
    entrega_taxa: Decimal
    entrega_gratis_acima: Decimal | None
    entrega_bairros: list[TaxaBairro]
    pix_chave: str | None
    pix_nome: str | None
    pix_cidade: str | None
    pix_no_site: bool
    popular_validade_receita: ValidadeReceita = 180
    popular_intervalo_dias: IntervaloPopular = 30


class ConfiguracoesAtualizar(BaseModel):
    desconto_maximo_caixa: PercentualDesconto | None = None
    dias_alerta_vencimento: DiasAlerta | None = None
    dias_prazo_padrao: DiasPrazo | None = None
    fidelidade_ativa: bool | None = None
    pontos_por_real: PontosPorReal | None = None
    valor_ponto: ValorPonto | None = None
    pontos_minimo_resgate: MinimoResgate | None = None
    pontos_validade_meses: ValidadeMeses | None = Field(default=None, description="Envie null para não expirar")
    loja_online_ativa: bool | None = None
    loja_online_endereco: EnderecoLoja | None = Field(
        default=None, description="Vai no endereço da loja: /loja/<endereço>. Letras minúsculas, números e hífen"
    )
    loja_online_loja_id: UUID | None = Field(default=None, description="De qual loja sai o estoque. Vazio: a matriz")
    loja_online_mensagem: str | None = Field(default=None, max_length=300)
    whatsapp: str | None = Field(default=None, max_length=20)
    entrega_ativa: bool | None = None
    entrega_minimo: Valor | None = None
    entrega_area: str | None = Field(default=None, max_length=200)
    entrega_taxa: Valor | None = Field(default=None, description="Taxa de entrega quando não há lista de bairros")
    entrega_gratis_acima: Valor | None = Field(default=None, description="Pedido a partir deste valor não paga entrega")
    entrega_bairros: Annotated[list[TaxaBairro], Field(max_length=200)] | None = Field(
        default=None, description="Taxa por bairro. Com a lista preenchida, o site só entrega nesses bairros"
    )
    pix_chave: str | None = Field(default=None, max_length=77)
    pix_nome: str | None = Field(default=None, max_length=25, description="Nome de quem recebe, como no banco")
    pix_cidade: str | None = Field(default=None, max_length=15)
    pix_no_site: bool | None = None
    popular_validade_receita: ValidadeReceita | None = Field(default=None, description="Dias que a receita vale")
    popular_intervalo_dias: IntervaloPopular | None = Field(
        default=None, description="Dias até o paciente levar o mesmo remédio de novo. 0 não confere"
    )


# Campos que aceitam vazio (null apaga o valor).
PODEM_FICAR_VAZIOS = {
    "pontos_validade_meses", "loja_online_endereco", "loja_online_loja_id", "loja_online_mensagem", "whatsapp",
    "entrega_area", "entrega_gratis_acima", "pix_chave", "pix_nome", "pix_cidade",
}
