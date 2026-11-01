"""Em que pé está a licença num certo dia: normal, avisando, em tolerância ou encerrada."""

from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel

from app.licenca.formato import Licenca

# Quantos dias antes de vencer o sistema começa a avisar.
DIAS_AVISO = 5

Estado = Literal["sem_licenca", "normal", "avisando", "tolerancia", "encerrada", "outro_servidor", "relogio"]


class Situacao(BaseModel):
    estado: Estado
    bloqueia: bool
    mensagem: str
    # Dias até vencer (normal/avisando) ou até encerrar (tolerância).
    dias: int | None = None
    encerra_em: date | None = None


def _plural(n: int) -> str:
    return "1 dia" if n == 1 else f"{n} dias"


def situacao(licenca: Licenca | None, hoje: date, maquina: str | None = None) -> Situacao:
    if licenca is None:
        return Situacao(
            estado="sem_licenca", bloqueia=True, mensagem="O FarmáciaFácil ainda não tem licença neste servidor"
        )
    if licenca.maquina and licenca.maquina != maquina:
        return Situacao(
            estado="outro_servidor",
            bloqueia=True,
            mensagem="Esta licença foi ativada em outro servidor. Peça a troca de computador para quem vendeu o sistema",
        )
    if licenca.vence is None:
        return Situacao(estado="normal", bloqueia=False, mensagem="Licença vitalícia")

    encerra = licenca.vence + timedelta(days=licenca.tolerancia_dias)
    faltam = (licenca.vence - hoje).days
    if faltam < 0 and hoje > encerra:
        return Situacao(
            estado="encerrada",
            bloqueia=True,
            mensagem=f"A licença venceu em {licenca.vence:%d/%m/%Y} e o prazo de tolerância acabou. Renove para continuar",
            encerra_em=encerra,
        )
    if faltam < 0:
        resta = (encerra - hoje).days + 1
        return Situacao(
            estado="tolerancia",
            bloqueia=False,
            mensagem=f"A licença venceu em {licenca.vence:%d/%m/%Y}. O sistema para em {_plural(resta)} se não for renovada",
            dias=resta,
            encerra_em=encerra,
        )
    if faltam < DIAS_AVISO:
        texto = "hoje" if faltam == 0 else f"em {_plural(faltam)}"
        return Situacao(
            estado="avisando",
            bloqueia=False,
            mensagem=f"A licença vence {texto} ({licenca.vence:%d/%m/%Y}). Renove para não parar",
            dias=faltam,
            encerra_em=encerra,
        )
    return Situacao(
        estado="normal",
        bloqueia=False,
        mensagem=f"Licença em dia até {licenca.vence:%d/%m/%Y}",
        dias=faltam,
        encerra_em=encerra,
    )


RELOGIO = Situacao(
    estado="relogio",
    bloqueia=True,
    mensagem="A data deste computador está atrasada. Acerte a data e a hora do servidor para continuar",
)
