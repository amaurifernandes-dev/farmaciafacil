"""PDVs registrados por chave no navegador, monocaixa e multicaixa."""

from tests.test_vendas import API, _abrir_caixa, _login_caixa, _produto_com_estoque, _registrar_pdv, _venda


def _matriz(client, headers) -> dict:
    return client.get(f"{API}/lojas", headers=headers).json()[0]


def _com_pdv(headers, chave) -> dict:
    return {**headers, "X-Terminal": chave}


def test_computador_sem_registro_nao_abre_caixa(client, farmacia_a):
    resposta = client.post(f"{API}/caixas/abrir", json={"valor_abertura": "0"}, headers=farmacia_a["headers"])
    assert resposta.status_code == 400
    assert "não está registrado" in resposta.json()["detail"]
    assert client.get(f"{API}/terminais/este", headers=farmacia_a["headers"]).status_code == 404
    chave_falsa = _com_pdv(farmacia_a["headers"], "chave-inventada")
    assert client.get(f"{API}/terminais/este", headers=chave_falsa).status_code == 404


def test_primeiro_pdv_vira_central_no_monocaixa(client, farmacia_a):
    h = farmacia_a["headers"]
    pdv1 = _registrar_pdv(client, h, "PDV 01")
    pdv2 = _registrar_pdv(client, h, "PDV 02")

    este = client.get(f"{API}/terminais/este", headers=_com_pdv(h, pdv1)).json()
    assert este["terminal"]["nome"] == "PDV 01"
    assert este["terminal"]["central"] is True
    assert este["loja"]["modo_caixa"] == "mono"
    assert este["pode_receber"] is True

    outro = client.get(f"{API}/terminais/este", headers=_com_pdv(h, pdv2)).json()
    assert outro["pode_receber"] is False
    assert "monocaixa" in outro["motivo"]
    resposta = client.post(f"{API}/caixas/abrir", json={"valor_abertura": "0"}, headers=_com_pdv(h, pdv2))
    assert resposta.status_code == 400
    assert "pré-venda" in resposta.json()["detail"]


def test_multicaixa_cada_pdv_abre_o_seu(client, engine_dono, farmacia_a):
    h = farmacia_a["headers"]
    produto = _produto_com_estoque(client, farmacia_a)
    pdv1 = _registrar_pdv(client, h, "PDV 01")
    pdv2 = _registrar_pdv(client, h, "PDV 02")
    matriz = _matriz(client, h)
    assert client.patch(f"{API}/lojas/{matriz['id']}", json={"modo_caixa": "multi"}, headers=h).status_code == 200

    caixa_h = _login_caixa(client, engine_dono, farmacia_a)
    assert client.post(f"{API}/caixas/abrir", json={"valor_abertura": "0"}, headers=_com_pdv(h, pdv1)).status_code == 201
    assert client.post(f"{API}/caixas/abrir", json={"valor_abertura": "0"}, headers=_com_pdv(caixa_h, pdv2)).status_code == 201

    # Cada venda cai no caixa do PDV em que foi feita.
    v1 = client.post(f"{API}/vendas", json=_venda(produto["id"]), headers=_com_pdv(h, pdv1)).json()
    v2 = client.post(f"{API}/vendas", json=_venda(produto["id"]), headers=_com_pdv(caixa_h, pdv2)).json()
    assert v1["caixa_id"] != v2["caixa_id"]

    # O operador de caixa não usa o caixa aberto por outra pessoa.
    alheio = client.post(f"{API}/vendas", json=_venda(produto["id"]), headers=_com_pdv(caixa_h, pdv1))
    assert alheio.status_code == 403

    abertos = client.get(f"{API}/caixas", params={"situacao": "aberto"}, headers=h).json()
    assert sorted(c["terminal"] for c in abertos) == ["PDV 01", "PDV 02"]
    assert {c["operador"] for c in abertos} == {"Admin", "Caixa"}


def test_um_caixa_por_pdv(client, engine_dono, farmacia_a):
    _abrir_caixa(client, farmacia_a)
    caixa_h = _com_pdv(_login_caixa(client, engine_dono, farmacia_a), farmacia_a["headers"]["X-Terminal"])
    resposta = client.post(f"{API}/caixas/abrir", json={"valor_abertura": "0"}, headers=caixa_h)
    assert resposta.status_code == 409


def test_revincular_tira_acesso_do_computador_antigo(client, farmacia_a):
    h = farmacia_a["headers"]
    antiga = _registrar_pdv(client, h)
    terminal_id = client.get(f"{API}/terminais/este", headers=_com_pdv(h, antiga)).json()["terminal"]["id"]

    nova = client.post(f"{API}/terminais/{terminal_id}/vincular", headers=h).json()["chave"]
    assert client.get(f"{API}/terminais/este", headers=_com_pdv(h, antiga)).status_code == 404
    assert client.get(f"{API}/terminais/este", headers=_com_pdv(h, nova)).status_code == 200

    client.post(f"{API}/terminais/{terminal_id}/desvincular", headers=h)
    assert client.get(f"{API}/terminais/este", headers=_com_pdv(h, nova)).status_code == 404


def test_pdv_desativado_nao_abre_caixa(client, farmacia_a):
    h = farmacia_a["headers"]
    chave = _registrar_pdv(client, h)
    terminal_id = client.get(f"{API}/terminais/este", headers=_com_pdv(h, chave)).json()["terminal"]["id"]
    client.patch(f"{API}/terminais/{terminal_id}", json={"ativo": False}, headers=h)
    resposta = client.post(f"{API}/caixas/abrir", json={"valor_abertura": "0"}, headers=_com_pdv(h, chave))
    assert resposta.status_code == 400


def test_chave_de_outra_farmacia_nao_vale(client, farmacia_a, farmacia_b):
    chave_a = _registrar_pdv(client, farmacia_a["headers"])
    resposta = client.get(f"{API}/terminais/este", headers=_com_pdv(farmacia_b["headers"], chave_a))
    assert resposta.status_code == 404
    assert client.get(f"{API}/terminais", headers=farmacia_b["headers"]).json() == []


def test_central_precisa_ser_da_loja(client, farmacia_a):
    h = farmacia_a["headers"]
    filial = client.post(f"{API}/lojas", json=FILIAL, headers=h).json()
    pdv_filial = client.post(f"{API}/terminais", json={"loja_id": filial["id"], "nome": "PDV 01"}, headers=h).json()
    matriz = _matriz(client, h)
    resposta = client.patch(f"{API}/lojas/{matriz['id']}", json={"terminal_central_id": pdv_filial["id"]}, headers=h)
    assert resposta.status_code == 400


def test_caixa_aberto_registra_loja_do_pdv(client, farmacia_a):
    h = farmacia_a["headers"]
    filial = client.post(f"{API}/lojas", json=FILIAL, headers=h).json()
    terminal = client.post(f"{API}/terminais", json={"loja_id": filial["id"], "nome": "PDV Filial"}, headers=h).json()
    assert terminal["central"] is True
    chave = client.post(f"{API}/terminais/{terminal['id']}/vincular", headers=h).json()["chave"]
    caixa = client.post(f"{API}/caixas/abrir", json={"valor_abertura": "0"}, headers=_com_pdv(h, chave)).json()
    assert caixa["loja_id"] == filial["id"]
    assert caixa["terminal_id"] == terminal["id"]
    resumo = client.get(f"{API}/caixas/atual", headers=_com_pdv(h, chave)).json()
    assert resumo["loja"] == "Filial Centro"
    assert resumo["terminal"] == "PDV Filial"


FILIAL = {
    "nome": "Filial Centro",
    "razao_social": "Farmácia Exemplo LTDA",
    "nome_fantasia": "Farmácia Exemplo Centro",
    "cnpj": "11.222.333/0001-81",
    "uf": "sp",
    "cidade": "São Roque",
}
