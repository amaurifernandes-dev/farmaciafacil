from app.modules.servicos.regras import avaliar
from tests.test_comissoes import _atendente
from tests.test_vendas import _abrir_caixa

API = "/api/v1"


def _catalogo(client, farmacia):
    return {s["tipo"]: s for s in client.get(f"{API}/servicos", headers=farmacia["headers"]).json()}


def _com_crf(client, farmacia, crf="SP 12345"):
    eu = client.get(f"{API}/auth/eu", headers=farmacia["headers"]).json()
    resposta = client.patch(f"{API}/usuarios/{eu['usuario_id']}", json={"crf": crf}, headers=farmacia["headers"])
    assert resposta.status_code == 200, resposta.text
    return eu


def _registrar(client, farmacia, esperado=201, **corpo):
    resposta = client.post(f"{API}/servicos/atendimentos", json=corpo, headers=farmacia["headers"])
    assert resposta.status_code == esperado, resposta.text
    return resposta.json()


def test_faixas_de_referencia():
    assert avaliar("pressao", {"sistolica": 120, "diastolica": 80}) is None
    assert avaliar("pressao", {"sistolica": 150, "diastolica": 85})[0] == "atencao"
    assert avaliar("pressao", {"sistolica": 185, "diastolica": 100})[0] == "alerta"
    assert avaliar("pressao", {"sistolica": 85, "diastolica": 55})[0] == "atencao"
    assert avaliar("glicemia", {"valor": 95, "jejum": True}) is None
    assert avaliar("glicemia", {"valor": 110, "jejum": True})[0] == "atencao"
    assert avaliar("glicemia", {"valor": 150, "jejum": False}) is None
    assert avaliar("glicemia", {"valor": 60})[0] == "alerta"
    assert avaliar("temperatura", {"graus": "38.2"})[0] == "atencao"
    assert avaliar("injetavel", {"medicamento": "X"}) is None


def test_registra_servicos_e_entra_no_caixa(client, farmacia_a):
    h = farmacia_a["headers"]
    catalogo = _catalogo(client, farmacia_a)  # já vem com os serviços comuns
    assert set(catalogo) == {"pressao", "glicemia", "temperatura", "injetavel"}
    pressao, glicemia, injetavel = catalogo["pressao"], catalogo["glicemia"], catalogo["injetavel"]

    # Sem CRF não registra: ele vai na declaração.
    resposta = _registrar(client, farmacia_a, 400, servico_id=pressao["id"], paciente_nome="José",
                          resultados={"sistolica": 120, "diastolica": 80}, forma_pagamento="pix")
    assert "CRF" in resposta["detail"]
    _com_crf(client, farmacia_a)

    cliente = client.post(f"{API}/clientes", json={"nome": "Maria Souza", "cpf": "52998224725",
                                                   "data_nascimento": "1950-03-10"}, headers=h).json()
    # Dinheiro precisa do caixa aberto.
    _registrar(client, farmacia_a, 400, servico_id=pressao["id"], cliente_id=cliente["id"],
               resultados={"sistolica": 150, "diastolica": 95})
    caixa = _abrir_caixa(client, farmacia_a)
    a1 = _registrar(client, farmacia_a, servico_id=pressao["id"], cliente_id=cliente["id"],
                    resultados={"sistolica": 150, "diastolica": 95, "frequencia": 78, "braco": "esquerdo"},
                    orientacao="Procurar o cardiologista.")
    assert (a1["numero"], a1["paciente_nome"], a1["paciente_cpf"], a1["valor"], a1["farmaceutico_crf"]) == (
        1, "Maria Souza", "52998224725", "5.00", "SP 12345")
    assert a1["resultado_texto"] == "150 x 95 mmHg, 78 bpm (braço esquerdo)"
    assert a1["aviso"]["nivel"] == "atencao"

    a2 = _registrar(client, farmacia_a, servico_id=glicemia["id"], paciente_nome="João Avulso",
                    resultados={"valor": 98, "jejum": True}, forma_pagamento="pix", valor="8.00")
    assert (a2["numero"], a2["valor"], a2["aviso"], a2["resultado_texto"]) == (2, "8.00", None, "98 mg/dL (em jejum)")
    _registrar(client, farmacia_a, servico_id=pressao["id"], cliente_id=cliente["id"], forma_pagamento="cortesia",
               resultados={"sistolica": 130, "diastolica": 85})

    # Resultado conferido pelo tipo do serviço.
    resposta = _registrar(client, farmacia_a, 400, servico_id=pressao["id"], paciente_nome="Fulano",
                          resultados={"sistolica": 80, "diastolica": 120}, forma_pagamento="pix")
    assert "sistólica" in resposta["detail"]
    _registrar(client, farmacia_a, 400, servico_id=injetavel["id"], paciente_nome="Fulano", forma_pagamento="pix",
               resultados={"medicamento": "Dipirona", "dose": "2 ml", "via": "IM"})  # falta a receita
    inj = _registrar(client, farmacia_a, servico_id=injetavel["id"], paciente_nome="Fulano", forma_pagamento="debito",
                     resultados={"medicamento": "Dipirona 500mg/ml", "dose": "2 ml", "via": "IM", "local": "glúteo",
                                 "lote": "AB12", "prescritor": "Dra. Ana", "prescritor_crm": "123456",
                                 "prescritor_uf": "sp", "receita_data": "2026-10-30"})
    assert inj["resultados"]["prescritor_uf"] == "SP"

    # O dinheiro do serviço está na gaveta.
    resumo = client.get(f"{API}/caixas/{caixa['id']}", headers=h).json()
    assert (resumo["servicos_dinheiro"], resumo["dinheiro_esperado"]) == ("5.00", "105.00")

    lista = client.get(f"{API}/servicos/atendimentos", headers=h).json()
    assert (len(lista["itens"]), lista["total_recebido"]) == (4, "28.00")
    assert lista["por_servico"] == {"Aferição de pressão arterial": 2, "Teste de glicemia capilar": 1,
                                    "Aplicação de injetável": 1}
    assert len(client.get(f"{API}/servicos/atendimentos", params={"busca": "joão"}, headers=h).json()["itens"]) == 1
    historico = client.get(f"{API}/servicos/cliente/{cliente['id']}", headers=h).json()
    assert [a["resultado_texto"] for a in historico] == ["130 x 85 mmHg", "150 x 95 mmHg, 78 bpm (braço esquerdo)"]

    # Cancelar tira do caixa.
    assert client.post(f"{API}/servicos/atendimentos/{a1['id']}/cancelar", json={"motivo": "Lançado errado"},
                       headers=h).json()["status"] == "cancelado"
    assert client.get(f"{API}/caixas/{caixa['id']}", headers=h).json()["servicos_dinheiro"] == "0"
    assert client.post(f"{API}/servicos/atendimentos/{a1['id']}/cancelar", json={"motivo": "De novo"},
                       headers=h).status_code == 409


def test_catalogo_e_permissoes(client, farmacia_a, farmacia_b):
    h = farmacia_a["headers"]
    bruna, _ = _atendente(client, farmacia_a)
    catalogo = _catalogo(client, farmacia_a)
    assert client.post(f"{API}/servicos/atendimentos", json={}, headers=bruna).status_code == 403
    assert client.get(f"{API}/servicos/atendimentos", headers=bruna).status_code == 403
    assert client.post(f"{API}/servicos", json={"nome": "Curativo", "tipo": "outro"}, headers=bruna).status_code == 403

    novo = client.post(f"{API}/servicos", json={"nome": "Curativo simples", "tipo": "outro", "preco": "12"}, headers=h)
    assert novo.status_code == 201, novo.text
    assert client.post(f"{API}/servicos", json={"nome": "curativo simples", "tipo": "outro"},
                       headers=h).status_code == 409
    temperatura = catalogo["temperatura"]
    client.patch(f"{API}/servicos/{temperatura['id']}", json={"ativo": False}, headers=h)
    assert "temperatura" not in _catalogo(client, farmacia_a)
    assert len(client.get(f"{API}/servicos", params={"todos": True}, headers=h).json()) == 5
    _com_crf(client, farmacia_a)
    _registrar(client, farmacia_a, 400, servico_id=temperatura["id"], paciente_nome="Ana",
               resultados={"graus": "36.5"}, forma_pagamento="pix")

    # CRF pode ser apagado com texto vazio.
    eu = _com_crf(client, farmacia_a, "")
    assert next(u for u in client.get(f"{API}/usuarios", headers=h).json() if u["id"] == eu["usuario_id"])["crf"] is None

    # Outra farmácia tem o próprio catálogo e não vê os atendimentos.
    assert all(s["id"] != novo.json()["id"] for s in client.get(f"{API}/servicos", headers=farmacia_b["headers"]).json())
