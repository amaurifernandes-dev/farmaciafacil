"""Contas da Farmácia Popular: o governo paga até o valor de referência; o paciente paga o resto."""

from decimal import Decimal

CENTAVO = Decimal("0.01")


def parte_do_governo(valor_por_unidade: Decimal | None, quantidade: Decimal, total_do_item: Decimal) -> Decimal:
    """O governo paga o valor de referência por unidade, nunca mais do que o preço cobrado."""
    if valor_por_unidade is None:
        return Decimal(0)
    return min(total_do_item, (valor_por_unidade * quantidade).quantize(CENTAVO))
