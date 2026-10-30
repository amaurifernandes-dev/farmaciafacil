import calendar
from datetime import date, datetime
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")


def hoje() -> date:
    """Data de hoje no horário de Brasília (validade de lote é por data local)."""
    return datetime.now(FUSO).date()


def mais_meses(dia: date, meses: int) -> date:
    """Mesmo dia `meses` depois; se o mês for mais curto, o último dia dele (31/01 + 1 mês = 28/02)."""
    mes = dia.month - 1 + meses
    ano, mes = dia.year + mes // 12, mes % 12 + 1
    return date(ano, mes, min(dia.day, calendar.monthrange(ano, mes)[1]))
