from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.modules.metas.schemas import Andamento


class DiaDeVendas(BaseModel):
    data: date
    total: Decimal
    quantidade: int


class Soma(BaseModel):
    quantidade: int
    total: Decimal


class MeuCaixa(BaseModel):
    aberto_em: datetime
    vendas: int
    total: Decimal


class PreVendaAberta(BaseModel):
    id: UUID
    numero: int
    total: Decimal
    criado_em: datetime
    entrega: bool


class Balcao(BaseModel):
    """Para quem atende e recebe: o próprio caixa, as pré-vendas esperando e as próprias vendas."""

    meu_caixa: MeuCaixa | None
    pre_vendas_abertas: int
    pre_vendas: list[PreVendaAberta]  # as mais antigas primeiro
    minhas_vendas_hoje: Soma


class ItemRepor(BaseModel):
    produto_id: UUID
    nome: str
    loja_nome: str
    saldo: Decimal
    estoque_minimo: Decimal


class LoteVencendo(BaseModel):
    produto_id: UUID
    produto_nome: str
    numero_lote: str
    loja_nome: str
    quantidade: Decimal
    validade: date
    dias_para_vencer: int


class BlocoEstoque(BaseModel):
    """Para quem cuida do estoque: o que repor, o que vence e o que está chegando."""

    repor: list[ItemRepor]  # os que mais faltam primeiro
    vencendo: list[LoteVencendo]  # os que vencem antes primeiro
    notas_para_conferir: int
    pedidos_compra_abertos: int
    encomendas_pendentes: int


class BlocoFarmacia(BaseModel):
    controlados_hoje: int  # vendas com receita retida hoje
    atendimentos_hoje: int  # serviços farmacêuticos feitos hoje


class Gestao(BaseModel):
    pagar_vencidas: Soma
    pagar_hoje: Soma
    receber_vencidas: Soma
    envios_recusados: int  # vendas sem internet que o servidor recusou, para resolver


class Painel(BaseModel):
    """Números da tela inicial, já calculados no fuso de Brasília."""

    farmacia: str
    uf: str
    hoje: date
    vendas_hoje: Decimal
    quantidade_vendas_hoje: int
    ticket_medio_hoje: Decimal
    vendas_ontem: Decimal
    semana: list[DiaDeVendas]  # últimos 7 dias, do mais antigo até hoje
    caixas_abertos: int
    meu_caixa_aberto: bool
    produtos_ativos: int
    lotes_vencidos: int
    lotes_vencendo: int  # nos próximos dias_alerta_vencimento dias
    dias_alerta_vencimento: int
    clientes: int
    abaixo_do_minimo: int
    encomendas_chegaram: int
    pedidos_novos: int  # do site, WhatsApp ou telefone, esperando a farmácia aceitar  # encomendas que já têm estoque: avisar o cliente
    meta_farmacia: Andamento | None = None  # meta do mês da farmácia toda, se definida
    minha_meta: Andamento | None = None  # meta do mês de quem está usando
    # Blocos que dependem do perfil: vazio quando o perfil não usa aquela parte.
    balcao: Balcao | None = None
    estoque: BlocoEstoque | None = None
    farmacia_bloco: BlocoFarmacia | None = None
    gestao: Gestao | None = None
