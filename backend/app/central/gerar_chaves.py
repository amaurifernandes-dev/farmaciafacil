"""Gera o par de chaves das licenças. Rode uma vez só, ao instalar a central.

    python -m app.central.gerar_chaves

A privada vai na variável CENTRAL_CHAVE_PRIVADA da central (e em mais lugar nenhum).
A pública vai na variável LICENCA_CHAVE_PUBLICA de cada instalação do FarmáciaFácil.
Trocar o par invalida todas as licenças já emitidas.
"""

from app.licenca.formato import gerar_par

if __name__ == "__main__":
    privada, publica = gerar_par()
    print("CENTRAL_CHAVE_PRIVADA=" + privada)
    print("LICENCA_CHAVE_PUBLICA=" + publica)
