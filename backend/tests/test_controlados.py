import uuid
import xml.etree.ElementTree as ET
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.security import gerar_hash_senha
from app.modules.auth.models import Usuario
from app.shared.datas import hoje
from tests.test_compras import _det, _importar, _validade, _xml
from tests.test_estoque_lojas import _lotes, _matriz
from tests.test_vendas import _abrir_caixa

API = "/api/v1"
NS = {"s": "urn:sngpc-schema"}
CPF_FARMACEUTICO = "52998224725"


def _controlado(client, farmacia, nome, controle, ean, registro="1234567890123", quantidade=10, **extra):
    corpo = {"nome": nome, "preco_venda": "30.00", "ean": ean, "tipo": "medicamento", "controle": controle,
             "registro_ms": registro, "vende_online": True, **extra}
    resposta = client.post(f"{API}/produtos", json=corpo, headers=farmacia["headers"])
    assert resposta.status_code == 201, resposta.text
    produto = resposta.json()
    if quantidade:
        item = {"produto_id": produto["id"], "numero_lote": "CTRL1", "quantidade": str(quantidade),
                "validade": _validade(300)}
        assert client.post(f"{API}/estoque/entradas", json={"itens": [item]},
                           headers=farmacia["headers"]).status_code == 201
    return produto


def _receita_b(**extra):
    return {
        "tipo_receituario": 2, "numero_notificacao": "sp 1234567", "data_prescricao": (hoje() - timedelta(days=3)).isoformat(),
        "prescritor_nome": "Dra. Paula Lima", "prescritor_conselho": "CRM", "prescritor_numero": "123456",
        "prescritor_uf": "sp", "comprador_nome": "José da Silva", "comprador_documento": "12.345.678-9",
        "comprador_orgao": "ssp", "comprador_uf": "SP", **extra,
    }


def _receita_atb(**extra):
    return {
        "tipo_receituario": 5, "data_prescricao": (hoje() - timedelta(days=2)).isoformat(),
        "prescritor_nome": "Dr. Carlos Mota", "prescritor_numero": "98765", "prescritor_uf": "SP",
        "paciente_nome": "Ana Mota", "paciente_idade": 34, "paciente_sexo": 2, **extra,
    }


def _vender(client, farmacia, itens, receita=None, esperado=201):
    total = sum(30 * float(q) for _, q in itens)
    corpo = {
        "chave_idempotencia": str(uuid.uuid4()),
        "itens": [{"produto_id": p["id"], "quantidade": str(q)} for p, q in itens],
        "pagamentos": [{"forma": "dinheiro", "valor": f"{total:.2f}"}],
    }
    if receita is not None:
        corpo["receita"] = receita
    resposta = client.post(f"{API}/vendas", json=corpo, headers=farmacia["headers"])
    assert resposta.status_code == esperado, resposta.text
    return resposta.json()


def test_controlado_fica_fora_do_site(client, farmacia_a):
    produto = _controlado(client, farmacia_a, "Clonazepam 2mg", "B1", "7891000000011", quantidade=0)
    assert (produto["controle"], produto["vende_online"], produto["embalagem_sngpc"]) == ("B1", False, "caixa")
    alterado = client.patch(f"{API}/produtos/{produto['id']}", json={"vende_online": True},
                            headers=farmacia_a["headers"]).json()
    assert alterado["vende_online"] is False
    assert client.post(f"{API}/produtos", json={"nome": "X", "preco_venda": "1.00", "controle": "Z9"},
                       headers=farmacia_a["headers"]).status_code == 422


def test_venda_de_controlado_pede_a_receita_certa(client, farmacia_a):
    clonazepam = _controlado(client, farmacia_a, "Clonazepam 2mg", "B1", "7891000000011")
    amoxicilina = _controlado(client, farmacia_a, "Amoxicilina 500mg", "ATB", "7891000000028")
    _abrir_caixa(client, farmacia_a)

    def recusa(itens, receita, trecho):
        erro = _vender(client, farmacia_a, itens, receita, esperado=400)["detail"]
        assert trecho in erro, erro

    recusa([(clonazepam, 1)], None, "notificação B")
    recusa([(clonazepam, 1)], _receita_b(tipo_receituario=1), "pede notificação B")
    recusa([(clonazepam, 1)], _receita_b(numero_notificacao=None), "número da notificação")
    recusa([(clonazepam, 1)], _receita_b(data_prescricao=(hoje() - timedelta(days=31)).isoformat()), "vencida")
    recusa([(clonazepam, 1)], _receita_b(data_prescricao=(hoje() + timedelta(days=1)).isoformat()), "futuro")
    recusa([(clonazepam, 1)], _receita_b(comprador_documento=None, comprador_orgao=None), "documento, órgão")
    recusa([(clonazepam, "0.5")], _receita_b(), "caixa ou frasco inteiro")
    recusa([(clonazepam, 1), (amoxicilina, 1)], _receita_b(), "receitas diferentes")
    # Antibiótico: a receita vale 10 dias e precisa da idade e do sexo do paciente.
    recusa([(amoxicilina, 1)], _receita_atb(paciente_sexo=None), "idade e o sexo")
    recusa([(amoxicilina, 1)], _receita_atb(data_prescricao=(hoje() - timedelta(days=11)).isoformat()), "10 dias")

    _vender(client, farmacia_a, [(clonazepam, 2)], _receita_b())
    _vender(client, farmacia_a, [(amoxicilina, 1)], _receita_atb())
    assert _lotes(client, farmacia_a, clonazepam, _matriz(client, farmacia_a)["id"]) == {"CTRL1": 8}


def test_perda_de_controlado_pede_o_motivo_da_anvisa(client, farmacia_a):
    clonazepam = _controlado(client, farmacia_a, "Clonazepam 2mg", "B1", "7891000000011")
    lote = client.get(f"{API}/estoque/lotes", params={"produto_id": clonazepam["id"]},
                      headers=farmacia_a["headers"]).json()[0]
    perda = {"lote_id": lote["id"], "quantidade": "1", "motivo": "Caixa amassada"}
    resposta = client.post(f"{API}/estoque/perdas", json=perda, headers=farmacia_a["headers"])
    assert resposta.status_code == 400 and "motivo da perda" in resposta.json()["detail"]
    resposta = client.post(f"{API}/estoque/perdas", json={**perda, "motivo_sngpc": 2}, headers=farmacia_a["headers"])
    assert resposta.status_code == 201 and resposta.json()["motivo_sngpc"] == 2
    # Ajuste de inventário não existe para a Anvisa.
    ajuste = {"lote_id": lote["id"], "nova_quantidade": "5", "motivo": "Contagem"}
    assert client.post(f"{API}/estoque/ajustes", json=ajuste, headers=farmacia_a["headers"]).status_code == 400


def test_livro_e_arquivos_do_sngpc(client, farmacia_a):
    h = farmacia_a["headers"]
    matriz = _matriz(client, farmacia_a)
    clonazepam = _controlado(client, farmacia_a, "Clonazepam 2mg", "B1", "7891234567895", quantidade=0)
    _controlado(client, farmacia_a, "Sem registro", "C1", "7891000000035", registro=None, quantidade=0)

    # Compra pela nota: 3 caixas no lote AB12.
    nota = _importar(client, farmacia_a, _xml(
        _det(1, "A1", "7891234567895", "CLONAZEPAM 2MG", "3", "10.00", lotes=[("ab12", 3, _validade(200))])
    )).json()
    assert client.post(f"{API}/compras/notas/{nota['id']}/confirmar", headers=h).status_code == 200
    # E 2 caixas lançadas à mão, sem nota.
    _entrada = {"produto_id": clonazepam["id"], "numero_lote": "XY9", "quantidade": "2", "validade": _validade(250)}
    assert client.post(f"{API}/estoque/entradas", json={"itens": [_entrada]}, headers=h).status_code == 201

    _abrir_caixa(client, farmacia_a)
    _vender(client, farmacia_a, [(clonazepam, 1)], _receita_b(uso_prolongado=True))
    lote = next(l for l in client.get(f"{API}/estoque/lotes", params={"produto_id": clonazepam["id"]}, headers=h).json()
                if l["numero_lote"] == "XY9")
    perda = {"lote_id": lote["id"], "quantidade": "1", "motivo": "Venceu", "motivo_sngpc": 3}
    assert client.post(f"{API}/estoque/perdas", json=perda, headers=h).status_code == 201

    resumo = client.get(f"{API}/controlados", headers=h)
    assert resumo.status_code == 200, resumo.text
    resumo = resumo.json()
    assert {k: float(v) for k, v in resumo["totais"].items()} == {
        "entradas": 5, "vendas": 1, "perdas": 1, "transferencias": 0}
    livro = [(l["tipo"], float(l["entrada"]), float(l["saida"]), float(l["saldo"])) for l in resumo["livro"]]
    assert livro == [("entrada", 3, 0, 3), ("entrada", 2, 0, 5), ("venda", 0, 1, 4), ("perda", 0, 1, 3)]
    assert resumo["livro"][0]["documento"] == "NF 1234 de DistriSaúde"
    assert resumo["livro"][2]["receita"].startswith("Notificação B (azul) nº SP 1234567")
    assert resumo["livro"][2]["pessoa"] == "José da Silva"
    assert resumo["livro"][3]["documento"] == "Vencimento: Venceu"
    codigos = {p["codigo"]: p["bloqueia"] for p in resumo["pendencias"]}
    assert codigos == {"sem_cpf": True, "entrada_sem_nota": False}
    assert {(s["lote"], float(s["quantidade"])) for s in resumo["saldos"]} == {("AB12", 2), ("XY9", 1)}

    # Sem o CPF do farmacêutico, não gera o arquivo.
    resposta = client.get(f"{API}/controlados/sngpc", headers=h)
    assert resposta.status_code == 400 and "CPF do farmacêutico" in resposta.json()["detail"]
    assert client.patch(f"{API}/lojas/{matriz['id']}", json={"responsavel_cpf": "529.982.247-25"},
                        headers=h).status_code == 200

    resposta = client.get(f"{API}/controlados/sngpc", headers=h)
    assert resposta.status_code == 200, resposta.text
    assert resposta.headers["content-disposition"].endswith(f'-{hoje():%Y%m%d}.xml"')
    assert resposta.content.startswith(b'<?xml version="1.0" encoding="ISO-8859-1"?>')
    raiz = ET.fromstring(resposta.content)
    assert raiz.tag == "{urn:sngpc-schema}mensagemSNGPC"
    assert raiz.findtext("s:cabecalho/s:cnpjEmissor", namespaces=NS) == matriz["cnpj"]
    assert raiz.findtext("s:cabecalho/s:cpfTransmissor", namespaces=NS) == CPF_FARMACEUTICO
    medicamentos = raiz.find("s:corpo/s:medicamentos", NS)
    assert [e.tag.split("}")[1] for e in medicamentos] == [
        "entradaMedicamentos", "saidaMedicamentoVendaAoConsumidor", "saidaMedicamentoPerda"]
    entrada = medicamentos.find("s:entradaMedicamentos", NS)
    assert entrada.findtext("s:notaFiscalEntradaMedicamento/s:numeroNotaFiscal", namespaces=NS) == "1234"
    assert entrada.findtext("s:notaFiscalEntradaMedicamento/s:cnpjOrigem", namespaces=NS) == "12345678000195"
    item = entrada.find("s:medicamentoEntrada", NS)
    assert [c.text for c in item] == ["2", "1234567890123", "AB12", "3", "1"]
    venda = medicamentos.find("s:saidaMedicamentoVendaAoConsumidor", NS)
    assert venda.findtext("s:tipoReceituarioMedicamento", namespaces=NS) == "2"
    assert venda.findtext("s:numeroNotificacaoMedicamento", namespaces=NS) == "SP 1234567"
    assert venda.findtext("s:prescritorMedicamento/s:UFConselho", namespaces=NS) == "SP"
    assert venda.findtext("s:compradorMedicamento/s:tipoDocumento", namespaces=NS) == "2"
    assert venda.findtext("s:compradorMedicamento/s:orgaoExpedidor", namespaces=NS) == "SSP"
    assert [c.text for c in venda.find("s:medicamentoVenda", NS)] == ["S", "1234567890123", "AB12", "1", "1"]
    perda_xml = medicamentos.find("s:saidaMedicamentoPerda", NS)
    assert perda_xml.findtext("s:motivoPerdaMedicamento", namespaces=NS) == "3"
    assert perda_xml.findtext("s:medicamentoPerda/s:numeroLoteMedicamento", namespaces=NS) == "XY9"

    inventario = client.get(f"{API}/controlados/inventario", headers=h)
    assert inventario.status_code == 200, inventario.text
    raiz = ET.fromstring(inventario.content)
    assert raiz.tag == "{urn:sngpc-schema}mensagemSNGPCInventario"
    assert raiz.findtext("s:cabecalho/s:data", namespaces=NS) == hoje().isoformat()
    lotes = {i.findtext("s:numeroLoteMedicamento", namespaces=NS): i.findtext("s:quantidadeMedicamento", namespaces=NS)
             for i in raiz.iterfind("s:corpo/s:medicamentos/s:entradaMedicamentos/s:medicamentoEntrada", NS)}
    assert lotes == {"AB12": "2", "XY9": "1"}


def test_produto_sem_registro_ms_bloqueia_o_arquivo(client, farmacia_a):
    matriz = _matriz(client, farmacia_a)
    client.patch(f"{API}/lojas/{matriz['id']}", json={"responsavel_cpf": CPF_FARMACEUTICO}, headers=farmacia_a["headers"])
    _controlado(client, farmacia_a, "Sem registro", "C1", "7891000000035", registro=None, quantidade=2)
    resposta = client.get(f"{API}/controlados/inventario", headers=farmacia_a["headers"])
    assert resposta.status_code == 400 and "Sem registro" in resposta.json()["detail"]


def test_caixa_nao_ve_o_livro(client, engine_dono, farmacia_a, farmacia_b):
    with Session(engine_dono) as db:
        db.add(Usuario(farmacia_id=farmacia_a["id"], nome="Caixa", email="caixa@farmacia.com",
                       senha_hash=gerar_hash_senha("senha-forte"), papel="caixa"))
        db.commit()
    token = client.post(f"{API}/auth/login", json={"email": "caixa@farmacia.com", "senha": "senha-forte"}).json()
    assert client.get(f"{API}/controlados", headers={"Authorization": f"Bearer {token['access_token']}"}).status_code == 403
    # Cada farmácia só vê o próprio livro.
    _controlado(client, farmacia_a, "Clonazepam 2mg", "B1", "7891000000011")
    assert client.get(f"{API}/controlados", headers=farmacia_b["headers"]).json()["saldos"] == []
