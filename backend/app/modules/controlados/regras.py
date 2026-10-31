"""O que a lei pede na venda de remédio controlado (Portaria 344/98 e RDC 20/2011 dos antibióticos)."""

from datetime import date, timedelta
from decimal import Decimal

from app.modules.controlados.schemas import ReceitaDados
from app.modules.produtos.models import Produto
from app.shared.erros import ErroDeNegocio

# Receita que cada lista pede, com os códigos do SNGPC.
RECEITUARIO = {
    "A1": 4, "A2": 4, "A3": 4,  # notificação A (amarela)
    "B1": 2, "B2": 2,  # notificação B (azul)
    "C2": 3,  # notificação especial (retinoides)
    "C1": 1, "C4": 1, "C5": 1,  # receita de controle especial em 2 vias
    "ATB": 5,  # receita de antimicrobiano em 2 vias
}
NOME_RECEITUARIO = {
    1: "receita de controle especial (2 vias)",
    2: "notificação B (azul)",
    3: "notificação de receita especial",
    4: "notificação A (amarela)",
    5: "receita de antibiótico (2 vias)",
}
COM_NUMERO = (2, 3, 4)  # notificações têm número impresso
DIAS_VALIDADE = {5: 10}  # antibiótico vale 10 dias; as demais, 30
VALIDADE_PADRAO = 30


def receituario_da_venda(produtos: list[Produto]) -> int | None:
    """O tipo de receita que a venda pede, ou None se não tem controlado."""
    controlados = [p for p in produtos if p.controle]
    if not controlados:
        return None
    for produto in controlados:
        if produto.controle == "C3":
            raise ErroDeNegocio(f"{produto.nome} é da lista C3 (talidomida) e não é vendido em farmácia")
    tipos = {RECEITUARIO[p.controle] for p in controlados}
    if len(tipos) > 1:
        nomes = ", ".join(NOME_RECEITUARIO[t] for t in sorted(tipos))
        raise ErroDeNegocio(f"Os remédios desta venda pedem receitas diferentes ({nomes}). Faça uma venda para cada receita.")
    return tipos.pop()


def validar_quantidade(produto: Produto, quantidade: Decimal) -> None:
    if produto.controle and quantidade != quantidade.to_integral_value():
        raise ErroDeNegocio(f"{produto.nome} é controlado: venda em caixa ou frasco inteiro")


def validar_receita(tipo: int, receita: ReceitaDados | None, hoje: date) -> None:
    if receita is None:
        raise ErroDeNegocio(f"Esta venda tem remédio controlado. Preencha os dados da {NOME_RECEITUARIO[tipo]}.")
    if receita.tipo_receituario != tipo:
        raise ErroDeNegocio(
            f"Este remédio pede {NOME_RECEITUARIO[tipo]}, e não {NOME_RECEITUARIO[receita.tipo_receituario]}"
        )
    if tipo in COM_NUMERO and not receita.numero_notificacao:
        raise ErroDeNegocio("Informe o número da notificação")
    if receita.data_prescricao > hoje:
        raise ErroDeNegocio("A data da receita está no futuro")
    dias = DIAS_VALIDADE.get(tipo, VALIDADE_PADRAO)
    if receita.data_prescricao + timedelta(days=dias) < hoje:
        raise ErroDeNegocio(f"Receita vencida: vale {dias} dias a partir da data em que foi escrita")
    if tipo == 5:
        if receita.paciente_idade is None or receita.paciente_sexo is None:
            raise ErroDeNegocio("No antibiótico, informe a idade e o sexo do paciente")
    else:
        faltando = [
            nome
            for nome, valor in (
                ("nome", receita.comprador_nome),
                ("documento", receita.comprador_documento),
                ("órgão que emitiu o documento", receita.comprador_orgao),
                ("estado do documento", receita.comprador_uf),
            )
            if not valor
        ]
        if faltando:
            raise ErroDeNegocio(f"Informe os dados de quem está comprando: {', '.join(faltando)}")
