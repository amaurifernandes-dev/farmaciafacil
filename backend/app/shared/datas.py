from datetime import date, datetime
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")


def hoje() -> date:
    """Data de hoje no horário de Brasília (validade de lote é por data local)."""
    return datetime.now(FUSO).date()
