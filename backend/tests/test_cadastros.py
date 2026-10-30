"""Clientes, fornecedores, usuários, lojas e configurações gerais."""

from tests.test_caixas_pdv import FILIAL
from tests.test_vendas import API, _abrir_caixa, _login_caixa, _produto_com_estoque, _venda


def test_cliente_minimo_e_consentimento(client, farmacia_a):
    h = farmacia_a["headers"]
    resposta = client.post(f"{API}/clientes", json={"nome": "Maria", "cpf": "", "telefone": ""}, headers=h)
    assert resposta.status_code == 201, resposta.text
    cliente = resposta.json()
    assert cliente["cpf"] is None
    assert cliente["aceita_ofertas"] is False
    assert cliente["consentimento_em"] is None

    autorizou = client.patch(f"{API}/clientes/{cliente['id']}", json={"aceita_ofertas": True}, headers=h).json()
    assert autorizou["consentimento_em"] is not None
    retirou = client.patch(f"{API}/clientes/{cliente['id']}", json={"aceita_ofertas": False}, headers=h).json()
    assert retirou["consentimento_em"] is None


def test_cliente_cpf_valido_e_unico(client, farmacia_a, farmacia_b):
    h = farmacia_a["headers"]
    assert client.post(f"{API}/clientes", json={"nome": "X", "cpf": "123.456.789-00"}, headers=h).status_code == 422
    dados = {"nome": "João", "cpf": "529.982.247-25", "telefone": "(11) 98888-7777", "uf": "sp"}
    criado = client.post(f"{API}/clientes", json=dados, headers=h).json()
    assert criado["cpf"] == "52998224725"
    assert criado["telefone"] == "11988887777"
    assert criado["uf"] == "SP"
    assert client.post(f"{API}/clientes", json=dados, headers=h).status_code == 409
    # Outra farmácia pode ter o mesmo cliente, e não vê o da primeira.
    assert client.post(f"{API}/clientes", json=dados, headers=farmacia_b["headers"]).status_code == 201
    assert client.get(f"{API}/clientes/{criado['id']}", headers=farmacia_b["headers"]).status_code == 404


def test_busca_de_clientes(client, farmacia_a):
    h = farmacia_a["headers"]
    client.post(f"{API}/clientes", json={"nome": "Ana Souza", "telefone": "11977776666"}, headers=h)
    client.post(f"{API}/clientes", json={"nome": "Bruno Lima", "cpf": "52998224725"}, headers=h)
    assert [c["nome"] for c in client.get(f"{API}/clientes?busca=souza", headers=h).json()["itens"]] == ["Ana Souza"]
    assert [c["nome"] for c in client.get(f"{API}/clientes?busca=529.982", headers=h).json()["itens"]] == []
    assert [c["nome"] for c in client.get(f"{API}/clientes?busca=52998224725", headers=h).json()["itens"]] == ["Bruno Lima"]
    assert [c["nome"] for c in client.get(f"{API}/clientes?busca=7777", headers=h).json()["itens"]] == ["Ana Souza"]


def test_fornecedor(client, engine_dono, farmacia_a):
    h = farmacia_a["headers"]
    dados = {"razao_social": "Distribuidora Saúde LTDA", "cnpj": "11.222.333/0001-81", "contato": "Carlos"}
    criado = client.post(f"{API}/fornecedores", json=dados, headers=h)
    assert criado.status_code == 201, criado.text
    assert criado.json()["cnpj"] == "11222333000181"
    assert client.post(f"{API}/fornecedores", json=dados, headers=h).status_code == 409
    assert client.post(f"{API}/fornecedores", json={**dados, "cnpj": "11222333000182"}, headers=h).status_code == 422

    desativado = client.patch(f"{API}/fornecedores/{criado.json()['id']}", json={"ativo": False}, headers=h).json()
    assert desativado["ativo"] is False
    assert client.get(f"{API}/fornecedores", headers=h).json()["total"] == 0

    caixa = _login_caixa(client, engine_dono, farmacia_a)
    assert client.post(f"{API}/fornecedores", json={"razao_social": "Outro"}, headers=caixa).status_code == 403


def test_usuarios(client, farmacia_a, farmacia_b):
    h = farmacia_a["headers"]
    novo = client.post(
        f"{API}/usuarios",
        json={"nome": "Paula", "email": "Paula@Farmacia.com", "papel": "atendente", "senha": "senha-boa-123"},
        headers=h,
    )
    assert novo.status_code == 201, novo.text
    assert novo.json()["email"] == "paula@farmacia.com"
    assert [u["nome"] for u in client.get(f"{API}/usuarios", headers=h).json()] == ["Admin", "Paula"]
    assert client.get(f"{API}/usuarios", headers=farmacia_b["headers"]).json()[0]["nome"] == "Admin"
    assert len(client.get(f"{API}/usuarios", headers=farmacia_b["headers"]).json()) == 1

    # E-mail é o login: não pode repetir nem em outra farmácia.
    repetido = {"nome": "Outra", "email": "paula@farmacia.com", "papel": "caixa", "senha": "senha-boa-123"}
    assert client.post(f"{API}/usuarios", json=repetido, headers=farmacia_b["headers"]).status_code == 409

    login = client.post(f"{API}/auth/login", json={"email": "paula@farmacia.com", "senha": "senha-boa-123"}).json()
    paula = {"Authorization": f"Bearer {login['access_token']}"}
    assert login["papel"] == "atendente"
    assert client.get(f"{API}/usuarios", headers=paula).status_code == 403
    assert client.post(f"{API}/caixas/abrir", json={"valor_abertura": "0"}, headers=paula).status_code == 400

    client.patch(f"{API}/usuarios/{novo.json()['id']}", json={"ativo": False}, headers=h)
    assert client.post(f"{API}/auth/login", json={"email": "paula@farmacia.com", "senha": "senha-boa-123"}).status_code == 401


def test_admin_nao_se_tranca_para_fora(client, farmacia_a):
    h = farmacia_a["headers"]
    eu = client.get(f"{API}/auth/eu", headers=h).json()
    assert client.patch(f"{API}/usuarios/{eu['usuario_id']}", json={"ativo": False}, headers=h).status_code == 400
    assert client.patch(f"{API}/usuarios/{eu['usuario_id']}", json={"papel": "caixa"}, headers=h).status_code == 400
    assert client.patch(f"{API}/usuarios/{eu['usuario_id']}", json={"nome": "Novo nome"}, headers=h).status_code == 200


def test_matriz_criada_e_segunda_loja(client, farmacia_a, farmacia_b):
    h = farmacia_a["headers"]
    lojas = client.get(f"{API}/lojas", headers=h).json()
    assert len(lojas) == 1
    assert lojas[0]["matriz"] is True
    assert lojas[0]["cnpj"] == "11111111000111"

    filial = client.post(f"{API}/lojas", json=FILIAL, headers=h)
    assert filial.status_code == 201, filial.text
    assert filial.json()["matriz"] is False
    assert filial.json()["uf"] == "SP"
    assert client.post(f"{API}/lojas", json=FILIAL, headers=h).status_code == 409
    assert [l["nome"] for l in client.get(f"{API}/lojas", headers=h).json()] == ["Matriz", "Filial Centro"]
    assert len(client.get(f"{API}/lojas", headers=farmacia_b["headers"]).json()) == 1


def test_editar_matriz_atualiza_nome_da_farmacia(client, farmacia_a):
    h = farmacia_a["headers"]
    matriz = client.get(f"{API}/lojas", headers=h).json()[0]
    resposta = client.patch(
        f"{API}/lojas/{matriz['id']}", json={"nome_fantasia": "Drogaria Nova", "responsavel_tecnico": "Dra. Ana"}, headers=h
    )
    assert resposta.status_code == 200, resposta.text
    assert client.get(f"{API}/painel", headers=h).json()["farmacia"] == "Drogaria Nova"
    assert client.patch(f"{API}/lojas/{matriz['id']}", json={"ativo": False}, headers=h).status_code == 400
    assert client.patch(f"{API}/lojas/{matriz['id']}", json={"nome": None}, headers=h).status_code == 400


def test_so_admin_mexe_nas_lojas_e_configuracoes(client, engine_dono, farmacia_a):
    caixa = _login_caixa(client, engine_dono, farmacia_a)
    assert client.post(f"{API}/lojas", json=FILIAL, headers=caixa).status_code == 403
    assert client.patch(f"{API}/configuracoes", json={"dias_alerta_vencimento": 10}, headers=caixa).status_code == 403
    assert client.get(f"{API}/configuracoes", headers=caixa).status_code == 200


def test_desconto_maximo_configuravel(client, engine_dono, farmacia_a):
    h = farmacia_a["headers"]
    config = client.patch(f"{API}/configuracoes", json={"desconto_maximo_caixa": "25"}, headers=h).json()
    assert config["desconto_maximo_caixa"] == "25.00"
    assert client.patch(f"{API}/configuracoes", json={"desconto_maximo_caixa": "150"}, headers=h).status_code == 422

    produto = _produto_com_estoque(client, farmacia_a, preco="100.00")
    _abrir_caixa(client, farmacia_a)
    # O admin fecha o caixa dele para o operador abrir no mesmo PDV.
    atual = client.get(f"{API}/caixas/atual", headers=h).json()
    client.post(f"{API}/caixas/{atual['caixa']['id']}/fechar", json={"valor_fechamento_informado": "100"}, headers=h)
    caixa = {**_login_caixa(client, engine_dono, farmacia_a), "X-Terminal": h["X-Terminal"]}
    assert client.post(f"{API}/caixas/abrir", json={"valor_abertura": "0"}, headers=caixa).status_code == 201
    vinte = _venda(produto["id"], pagamentos=[{"forma": "pix", "valor": "80"}], desconto="20.00")
    assert client.post(f"{API}/vendas", json=vinte, headers=caixa).status_code == 201
    trinta = _venda(produto["id"], pagamentos=[{"forma": "pix", "valor": "70"}], desconto="30.00")
    assert client.post(f"{API}/vendas", json=trinta, headers=caixa).status_code == 403
