from datetime import timedelta
from decimal import Decimal

import pytest

from app.modules.financeiro import boleto
from app.shared.datas import hoje
from tests.test_financeiro import API

# Exemplo público de boleto do Banco do Brasil (R$ 1,00).
LINHA_BB = "00190.50095 40144.816069 06809.350314 3 37370000000100"


def _boleto(valor: str, vencimento, banco="341") -> str:
    """Monta o código de barras (44 números) de um boleto bancário válido."""
    fator = 1000 + (vencimento - boleto.BASE_NOVA).days
    sem_dv = f"{banco}9{fator:04d}{int(Decimal(valor) * 100):010d}" + "1" * 25
    dv = boleto._mod11_bancario(sem_dv)
    return sem_dv[:4] + str(dv) + sem_dv[4:]


def _conta_de_luz(valor: str) -> str:
    """Código de barras (44) de uma conta de energia, com o valor no código (identificador 6)."""
    sem_dv = f"836{int(Decimal(valor) * 100):011d}" + "0" * 29
    dv = boleto._mod10(sem_dv)
    return sem_dv[:3] + str(dv) + sem_dv[3:]


def test_le_a_linha_do_banco_do_brasil():
    lido = boleto.ler(LINHA_BB)
    assert lido.tipo == "bancario"
    assert lido.banco_nome == "Banco do Brasil"
    assert lido.valor == Decimal("1.00")
    assert lido.linha_digitavel == LINHA_BB
    # O código de barras do leitor dá o mesmo boleto.
    assert boleto.ler(lido.codigo_barras).linha_digitavel == LINHA_BB


def test_vencimento_depois_da_virada_do_fator():
    vencimento = hoje() + timedelta(days=10)
    lido = boleto.ler(_boleto("1234.56", vencimento))
    assert lido.vencimento == vencimento
    assert lido.valor == Decimal("1234.56")
    assert lido.banco_nome == "Itaú"
    # E a linha digitável montada volta para o mesmo código.
    assert boleto.ler(lido.linha_digitavel).codigo_barras == lido.codigo_barras


def test_conta_de_consumo():
    barras = _conta_de_luz("187.45")
    lido = boleto.ler(barras)
    assert lido.tipo == "arrecadacao"
    assert lido.segmento == "Energia elétrica e gás"
    assert lido.valor == Decimal("187.45")
    assert lido.vencimento is None
    assert len(boleto.so_numeros(lido.linha_digitavel)) == 48
    assert boleto.ler(lido.linha_digitavel).codigo_barras == barras


@pytest.mark.parametrize(
    "codigo, trecho",
    [
        ("00190.50095 40144.816069 06809.350314 3 37370000000101", "geral"),  # valor trocado
        ("00190.50094 40144.816069 06809.350314 3 37370000000100", "1º bloco"),
        ("123", "3 números"),
    ],
)
def test_codigo_errado_explica(codigo, trecho):
    with pytest.raises(boleto.BoletoInvalido, match=trecho):
        boleto.ler(codigo)


def test_lancar_boleto_e_nao_lancar_duas_vezes(client, farmacia_a):
    h = farmacia_a["headers"]
    vencimento = hoje() + timedelta(days=3)
    codigo = _boleto("350.00", vencimento)

    lido = client.post(f"{API}/financeiro/boletos/ler", json={"codigo": codigo}, headers=h)
    assert lido.status_code == 200, lido.text
    assert lido.json()["valor"] == "350.00"
    assert lido.json()["vencimento"] == vencimento.isoformat()
    assert lido.json()["ja_lancada"] is None

    conta = {"tipo": "pagar", "descricao": "Distribuidora Santa Cruz", "categoria": "fornecedores",
             "valor_total": "350.00", "primeiro_vencimento": vencimento.isoformat(),
             "codigo_barras": lido.json()["linha_digitavel"]}
    criada = client.post(f"{API}/financeiro/contas", json=conta, headers=h)
    assert criada.status_code == 201, criada.text
    assert criada.json()[0]["codigo_barras"] == codigo
    assert criada.json()[0]["linha_digitavel"] == lido.json()["linha_digitavel"]

    # O mesmo boleto de novo: avisa na leitura e recusa no lançamento.
    de_novo = client.post(f"{API}/financeiro/boletos/ler", json={"codigo": codigo}, headers=h).json()
    assert de_novo["ja_lancada"]["id"] == criada.json()[0]["id"]
    repetida = client.post(f"{API}/financeiro/contas", json=conta, headers=h)
    assert repetida.status_code == 409
    assert "já foi lançado" in repetida.json()["detail"]

    # Cancelada, o boleto pode ser lançado de novo.
    client.post(f"{API}/financeiro/contas/{criada.json()[0]['id']}/cancelar", headers=h)
    assert client.post(f"{API}/financeiro/contas", json=conta, headers=h).status_code == 201


def test_boleto_invalido_e_regras(client, farmacia_a):
    h = farmacia_a["headers"]
    ruim = client.post(f"{API}/financeiro/boletos/ler", json={"codigo": "1234"}, headers=h)
    assert ruim.status_code == 400
    base = {"descricao": "Teste", "valor_total": "10.00", "primeiro_vencimento": hoje().isoformat(),
            "codigo_barras": LINHA_BB}
    receber = client.post(f"{API}/financeiro/contas", json={**base, "tipo": "receber", "categoria": "outras"}, headers=h)
    assert receber.status_code == 400
    parcelado = client.post(
        f"{API}/financeiro/contas", json={**base, "tipo": "pagar", "categoria": "outras", "parcelas": 2}, headers=h
    )
    assert parcelado.status_code == 400


def test_liga_boleto_a_conta_que_ja_existia(client, farmacia_a):
    h = farmacia_a["headers"]
    vencimento = hoje() + timedelta(days=12)
    conta = client.post(f"{API}/financeiro/contas", json={
        "tipo": "pagar", "descricao": "Nota 123 parcela 1", "categoria": "fornecedores",
        "valor_total": "980.00", "primeiro_vencimento": (vencimento - timedelta(days=2)).isoformat(),
    }, headers=h).json()[0]
    codigo = _boleto("980.00", vencimento)

    lido = client.post(f"{API}/financeiro/boletos/ler", json={"codigo": codigo}, headers=h).json()
    assert [c["id"] for c in lido["parecidas"]] == [conta["id"]]

    ligada = client.patch(f"{API}/financeiro/contas/{conta['id']}",
                          json={"codigo_barras": codigo, "vencimento": vencimento.isoformat()}, headers=h)
    assert ligada.status_code == 200, ligada.text
    assert ligada.json()["codigo_barras"] == codigo
    # Já com boleto, não aparece mais como parecida.
    assert client.post(f"{API}/financeiro/boletos/ler", json={"codigo": codigo}, headers=h).json()["parecidas"] == []
    # Texto vazio tira o boleto.
    tirado = client.patch(f"{API}/financeiro/contas/{conta['id']}", json={"codigo_barras": ""}, headers=h)
    assert tirado.json()["codigo_barras"] is None


def test_semana_a_pagar(client, farmacia_a):
    h = farmacia_a["headers"]
    for dias, valor in ((-2, "50.00"), (0, "30.00"), (3, "70.00"), (3, "5.00"), (10, "999.00")):
        client.post(f"{API}/financeiro/contas", json={
            "tipo": "pagar", "descricao": f"Conta {valor}", "categoria": "outras", "valor_total": valor,
            "primeiro_vencimento": (hoje() + timedelta(days=dias)).isoformat(),
        }, headers=h)
    semana = client.get(f"{API}/financeiro/semana", headers=h).json()
    assert semana["total_vencidas"] == "50.00"
    assert [(d["dia"], d["total"]) for d in semana["dias"]] == [
        (hoje().isoformat(), "30.00"),
        ((hoje() + timedelta(days=3)).isoformat(), "75.00"),
    ]
    assert semana["total_semana"] == "105.00"
    gestao = client.get(f"{API}/painel", headers=h).json()["gestao"]
    assert gestao["pagar_semana"] == {"quantidade": 2, "total": "75.00"}
