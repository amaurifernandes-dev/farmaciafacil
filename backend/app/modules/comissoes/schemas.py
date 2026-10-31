from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class Vendedor(BaseModel):
    usuario_id: UUID
    nome: str
    papel: str
    recebe_comissao: bool
    vendas: int
    vendido: Decimal
    comissao: Decimal
    ticket_medio: Decimal
    percentual: Decimal  # comissão / vendido, para comparar


class RelatorioComissoes(BaseModel):
    inicio: date
    fim: date
    comissao_padrao: Decimal
    vendedores: list[Vendedor]
    total_vendido: Decimal
    total_comissao: Decimal


class VendaDoVendedor(BaseModel):
    venda_id: UUID
    numero: int
    finalizada_em: datetime
    vendido: Decimal
    comissao: Decimal
    pre_venda: bool  # veio de pré-venda (outra pessoa passou no caixa)


class ProdutoDoVendedor(BaseModel):
    produto_id: UUID
    descricao: str
    quantidade: Decimal
    vendido: Decimal
    percentual: Decimal
    comissao: Decimal


class DetalheVendedor(BaseModel):
    inicio: date
    fim: date
    vendedor: Vendedor
    vendas: list[VendaDoVendedor]
    produtos: list[ProdutoDoVendedor]
