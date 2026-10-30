def cnpj_valido(cnpj: str) -> bool:
    """Confere os dois dígitos verificadores. Espera só os 14 dígitos."""
    if len(cnpj) != 14 or not cnpj.isdigit() or cnpj == cnpj[0] * 14:
        return False
    for tamanho in (12, 13):
        pesos = list(range(tamanho - 7, 1, -1)) + list(range(9, 1, -1))
        soma = sum(int(cnpj[i]) * pesos[i] for i in range(tamanho))
        resto = soma % 11
        digito = 0 if resto < 2 else 11 - resto
        if digito != int(cnpj[tamanho]):
            return False
    return True
