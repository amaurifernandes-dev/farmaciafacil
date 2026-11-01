from decimal import Decimal

from tests.test_compras import CNPJ_DISTRIBUIDORA, _det, _importar, _validade, _xml
from tests.test_estoque_lojas import _filial, _matriz, _produto

API = "/api/v1"
OUTRA_CHAVE = "35261012345678000195550010000056781000056780"


def _fornecedor(client, farmacia, cnpj=CNPJ_DISTRIBUIDORA, nome="DistriSaúde") -> dict:
    dados = {"razao_social": f"{nome} LTDA", "nome_fantasia": nome, "cnpj": cnpj, "contato": "Carlos",
             "telefone": "(19) 3222-3333", "email": "pedidos@distrisaude.com.br"}
    resposta = client.post(f"{API}/fornecedores", json=dados, headers=farmacia["headers"])
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _produtos(client, farmacia) -> dict:
    return {
        "dipirona": _produto(client, farmacia, nome="Dipirona 500mg", ean="7891234567895"),
        "vitamina": _produto(client, farmacia, nome="Vitamina C", ean="7890000000024"),
        "soro": _produto(client, farmacia, nome="Soro fisiológico", ean="7890000000031"),
        "protetor": _produto(client, farmacia, nome="Protetor solar", ean="7890000000048"),
    }


def _pedido(client, farmacia, fornecedor, itens, **extra):
    corpo = {"fornecedor_id": fornecedor["id"], "itens": itens, **extra}
    return client.post(f"{API}/compras/pedidos", json=corpo, headers=farmacia["headers"])


def _item(produto, quantidade, custo=None):
    return {"produto_id": produto["id"], "quantidade": str(quantidade), "custo_estimado": custo}


def _un(n, ean, descricao, quantidade, unitario="5.00"):
    return _det(n, f"C{ean[-4:]}", ean, descricao, str(quantidade), unitario, unidade="UN",
                lotes=[(f"L{n}", quantidade, _validade())])


def _situacoes(nota) -> dict:
    return {l["nome"]: (l["situacao"], Decimal(l["pedido"]), Decimal(l["na_nota"])) for l in nota["pedido"]["linhas"]}


def test_pedido_guardado_e_conferido_quando_a_nota_chega(client, farmacia_a):
    h = farmacia_a["headers"]
    matriz = _matriz(client, farmacia_a)
    p = _produtos(client, farmacia_a)
    fornecedor = _fornecedor(client, farmacia_a)

    resposta = _pedido(client, farmacia_a, fornecedor, [
        _item(p["dipirona"], 20, "2.50"), _item(p["vitamina"], 10, "6.00"), _item(p["soro"], 5),
    ])
    assert resposta.status_code == 201, resposta.text
    pedido = resposta.json()
    assert (pedido["numero"], pedido["status"], pedido["loja_id"]) == (1, "aberto", matriz["id"])
    assert pedido["total_estimado"] == "110.00"  # o soro ainda não tem custo
    assert pedido["whatsapp"] == "551932223333"
    assert pedido["email"] == "pedidos@distrisaude.com.br"
    assert "Pedido de compra nº 1" in pedido["texto"] and "- 20 x Dipirona 500mg (EAN 7891234567895)" in pedido["texto"]
    assert [Decimal(i["falta_receber"]) for i in pedido["itens"]] == [20, 10, 5]

    enviado = client.post(f"{API}/compras/pedidos/{pedido['id']}/enviado", headers=h).json()
    assert enviado["status"] == "enviado" and enviado["enviado_em"]

    # Chega a primeira nota: a dipirona veio certa (2 displays de 10), a vitamina veio a menos,
    # o soro não veio e veio um protetor que ninguém pediu.
    xml = _xml(
        _det(1, "A1", "17891234567892", "DIPIRONA DISPLAY C/10", "2", "25.00", ean_trib="7891234567895",
             lotes=[("D1", 2, _validade())], qtrib="20", utrib="UN")
        + _un(2, "7890000000024", "VITAMINA C", 6)
        + _un(3, "7890000000048", "PROTETOR SOLAR", 3)
    )
    resposta = _importar(client, farmacia_a, xml)
    assert resposta.status_code == 201, resposta.text
    nota = resposta.json()
    assert (nota["pedido_id"], nota["pedido_numero"]) == (pedido["id"], 1)
    assert _situacoes(nota) == {
        "Dipirona 500mg": ("ok", 20, 20),
        "Vitamina C": ("faltou", 10, 6),
        "Soro fisiológico": ("nao_veio", 5, 0),
        "Protetor solar": ("fora_do_pedido", 0, 3),
    }
    assert nota["pedido"]["tudo_certo"] is False
    listada = client.get(f"{API}/compras/notas", headers=h).json()[0]
    assert listada["pedido_numero"] == 1

    assert client.post(f"{API}/compras/notas/{nota['id']}/confirmar", headers=h).status_code == 200
    pedido = client.get(f"{API}/compras/pedidos/{pedido['id']}", headers=h).json()
    assert pedido["status"] == "parcial"
    assert [(Decimal(i["recebido"]), Decimal(i["falta_receber"])) for i in pedido["itens"]] == [(20, 0), (6, 4), (0, 5)]
    assert [n["numero"] for n in pedido["notas"]] == [1234]

    # Ainda aberto, o pedido não pode mais ser cancelado: parte já chegou.
    assert client.post(f"{API}/compras/pedidos/{pedido['id']}/cancelar", headers=h).status_code == 400

    # A segunda nota completa a vitamina e traz soro a mais.
    xml = _xml(_un(1, "7890000000024", "VITAMINA C", 4) + _un(2, "7890000000031", "SORO", 6), chave=OUTRA_CHAVE)
    nota = _importar(client, farmacia_a, xml).json()
    assert nota["pedido_id"] == pedido["id"]
    situacoes = _situacoes(nota)
    assert situacoes["Vitamina C"] == ("ok", 4, 4)
    assert situacoes["Soro fisiológico"] == ("sobrou", 5, 6)
    assert situacoes["Dipirona 500mg"] == ("ok", 0, 0)
    client.post(f"{API}/compras/notas/{nota['id']}/confirmar", headers=h)
    pedido = client.get(f"{API}/compras/pedidos/{pedido['id']}", headers=h).json()
    assert pedido["status"] == "recebido"

    # Recebido sai da lista de abertos e não aceita mais nota.
    abertos = client.get(f"{API}/compras/pedidos", params={"status": "abertos"}, headers=h).json()
    assert abertos == []
    todos = client.get(f"{API}/compras/pedidos", headers=h).json()
    assert [(x["numero"], x["status"], x["fornecedor_nome"]) for x in todos] == [(1, "recebido", "DistriSaúde")]


def test_nota_sem_pedido_e_troca_de_pedido(client, farmacia_a):
    h = farmacia_a["headers"]
    p = _produtos(client, farmacia_a)
    fornecedor = _fornecedor(client, farmacia_a)
    outro = _fornecedor(client, farmacia_a, cnpj="11222333000181", nome="MedFarma")
    filial = _filial(client, farmacia_a, cnpj="11444777000161")

    # Pedido para a filial: a nota que chega na matriz não liga nele sozinha.
    para_filial = _pedido(client, farmacia_a, fornecedor, [_item(p["vitamina"], 4)], loja_id=filial["id"]).json()
    do_outro = _pedido(client, farmacia_a, outro, [_item(p["vitamina"], 4)]).json()
    nota = _importar(client, farmacia_a, _xml(_un(1, "7890000000024", "VITAMINA C", 4))).json()
    assert nota["pedido_id"] is None and nota["pedido"] is None

    ligar = f"{API}/compras/notas/{nota['id']}/pedido"
    assert client.patch(ligar, json={"pedido_id": do_outro["id"]}, headers=h).status_code == 400  # outro fornecedor
    resposta = client.patch(ligar, json={"pedido_id": para_filial["id"]}, headers=h)
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["pedido"]["tudo_certo"] is True
    resposta = client.patch(ligar, json={"pedido_id": None}, headers=h)
    assert resposta.json()["pedido"] is None

    # Pedido cancelado não recebe nota.
    cancelado = client.post(f"{API}/compras/pedidos/{para_filial['id']}/cancelar", headers=h).json()
    assert cancelado["status"] == "cancelado"
    assert client.patch(ligar, json={"pedido_id": para_filial["id"]}, headers=h).status_code == 400
    assert client.post(f"{API}/compras/pedidos/{para_filial['id']}/enviado", headers=h).status_code == 409

    # Depois de confirmada, a nota não troca de pedido.
    client.post(f"{API}/compras/notas/{nota['id']}/confirmar", headers=h)
    assert client.patch(ligar, json={"pedido_id": None}, headers=h).status_code == 409


def test_cancelar_pedido_solta_a_nota_pendente(client, farmacia_a):
    h = farmacia_a["headers"]
    p = _produtos(client, farmacia_a)
    fornecedor = _fornecedor(client, farmacia_a)
    pedido = _pedido(client, farmacia_a, fornecedor, [_item(p["vitamina"], 4)]).json()
    nota = _importar(client, farmacia_a, _xml(_un(1, "7890000000024", "VITAMINA C", 4))).json()
    assert nota["pedido_id"] == pedido["id"]
    client.post(f"{API}/compras/pedidos/{pedido['id']}/cancelar", headers=h)
    assert client.get(f"{API}/compras/notas/{nota['id']}", headers=h).json()["pedido_id"] is None


def test_validacoes_do_pedido(client, farmacia_a, farmacia_b):
    p = _produtos(client, farmacia_a)
    fornecedor = _fornecedor(client, farmacia_a)
    repetido = _pedido(client, farmacia_a, fornecedor, [_item(p["vitamina"], 1), _item(p["vitamina"], 2)])
    assert repetido.status_code == 400
    assert _pedido(client, farmacia_a, fornecedor, []).status_code == 422
    assert _pedido(client, farmacia_a, fornecedor, [_item(p["vitamina"], 0)]).status_code == 422

    # Outra farmácia não vê nem usa o pedido, o fornecedor ou os produtos.
    pedido = _pedido(client, farmacia_a, fornecedor, [_item(p["vitamina"], 1)]).json()
    assert client.get(f"{API}/compras/pedidos/{pedido['id']}", headers=farmacia_b["headers"]).status_code == 404
    assert client.get(f"{API}/compras/pedidos", headers=farmacia_b["headers"]).json() == []
    assert _pedido(client, farmacia_b, fornecedor, [_item(p["vitamina"], 1)]).status_code == 404

    # Os números seguem por farmácia.
    fornecedor_b = _fornecedor(client, farmacia_b)
    vitamina_b = _produto(client, farmacia_b, nome="Vitamina C", ean="7890000000024")
    assert _pedido(client, farmacia_b, fornecedor_b, [_item(vitamina_b, 1)]).json()["numero"] == 1
    assert _pedido(client, farmacia_a, fornecedor, [_item(p["vitamina"], 1)]).json()["numero"] == 2


def test_caixa_nao_mexe_em_pedido_de_compra(client, farmacia_a):
    h = farmacia_a["headers"]
    dados = {"nome": "Julia", "email": "julia@farmacia.com", "papel": "caixa", "senha": "senha-boa-123"}
    assert client.post(f"{API}/usuarios", json=dados, headers=h).status_code == 201
    login = client.post(f"{API}/auth/login", json={"email": dados["email"], "senha": dados["senha"]}).json()
    caixa = {"headers": {"Authorization": f"Bearer {login['access_token']}"}}
    fornecedor = _fornecedor(client, farmacia_a)
    vitamina = _produto(client, farmacia_a, nome="Vitamina C", ean="7890000000024")
    assert _pedido(client, caixa, fornecedor, [_item(vitamina, 1)]).status_code == 403
    assert client.get(f"{API}/compras/pedidos", headers=caixa["headers"]).status_code == 403
