from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class DiaDeVendas(BaseModel):
    data: date
    total: Decimal
    quantidade: int


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
