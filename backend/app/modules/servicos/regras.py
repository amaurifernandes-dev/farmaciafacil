"""Faixas de referência para avisar o farmacêutico. Não é diagnóstico: só indica quando orientar a procurar o médico.

Fontes: Diretriz Brasileira de Hipertensão (2020) e Diretrizes da Sociedade Brasileira de Diabetes.
"""

from decimal import Decimal


def avaliar(tipo: str, resultados: dict) -> tuple[str, str] | None:
    """Devolve (nível, texto) quando o valor está fora da faixa; nível é 'alerta' ou 'atencao'."""
    if tipo == "pressao":
        sis, dia = int(resultados["sistolica"]), int(resultados["diastolica"])
        if sis >= 180 or dia >= 110:
            return "alerta", "Pressão muito alta (180/110 ou mais): orientar a procurar atendimento médico com urgência."
        if sis >= 140 or dia >= 90:
            return "atencao", "Pressão acima de 140/90: orientar a procurar o médico para avaliação."
        if sis < 90 or dia < 60:
            return "atencao", "Pressão abaixo de 90/60: orientar a observar sintomas e procurar o médico se tiver tontura."
        return None
    if tipo == "glicemia":
        valor = int(resultados["valor"])
        jejum = bool(resultados.get("jejum"))
        if valor < 70:
            return "alerta", "Glicemia abaixo de 70 mg/dL (hipoglicemia): oferecer açúcar e orientar a procurar o médico."
        if valor >= 300:
            return "alerta", "Glicemia acima de 300 mg/dL: orientar a procurar atendimento médico com urgência."
        if (jejum and valor >= 100) or (not jejum and valor >= 200):
            limite = "100 mg/dL em jejum" if jejum else "200 mg/dL fora do jejum"
            return "atencao", f"Glicemia acima de {limite}: orientar a procurar o médico para avaliação."
        return None
    if tipo == "temperatura":
        graus = Decimal(str(resultados["graus"]))
        if graus >= Decimal("39.5"):
            return "alerta", "Febre alta (39,5 °C ou mais): orientar a procurar atendimento médico."
        if graus >= Decimal("37.8"):
            return "atencao", "Febre (37,8 °C ou mais): orientar repouso, hidratação e procurar o médico se persistir."
        if graus < Decimal(35):
            return "atencao", "Temperatura abaixo de 35 °C: orientar a procurar o médico."
        return None
    return None
