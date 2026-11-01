"""Assistente de IA: o modelo é trocado por um roteiro, e as ferramentas rodam de verdade no banco."""

import json
from types import SimpleNamespace

import pytest

from app.main import app
from app.modules.assistente.router import get_cliente_ia
from tests.test_promocoes_relatorios import _produto, _promocao

API = "/api/v1"


class ModeloFalso:
    """Faz o papel do Claude: cada passo recebe as mensagens e devolve (stop_reason, blocos)."""

    def __init__(self, *passos):
        self.passos = list(passos)
        self.chamadas: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._criar))

    def _criar(self, **kwargs):
        self.chamadas.append(json.loads(json.dumps(kwargs, default=str)))
        motivo, blocos = self.passos.pop(0)(kwargs["messages"])
        return SimpleNamespace(stop_reason=motivo, content=blocos)


def _ferramenta(nome, entrada, id_="t1"):
    return lambda _m: ("tool_use", [{"type": "tool_use", "id": id_, "name": nome, "input": entrada}])


def _texto(texto):
    return lambda _m: ("end_turn", [{"type": "text", "text": texto}])


def _resultado(mensagens) -> tuple[dict, bool]:
    bloco = mensagens[-1]["content"][0]
    assert bloco["type"] == "tool_result"
    return json.loads(bloco["content"]) if not bloco.get("is_error") else bloco["content"], bool(bloco.get("is_error"))


@pytest.fixture
def modelo():
    falso = {}

    def usar(*passos):
        falso["m"] = ModeloFalso(*passos)
        app.dependency_overrides[get_cliente_ia] = lambda: falso["m"]
        return falso["m"]

    yield usar
    app.dependency_overrides.pop(get_cliente_ia, None)


def _perguntar(client, farmacia, mensagem, historico=()):
    resposta = client.post(
        f"{API}/assistente", json={"mensagem": mensagem, "historico": list(historico)}, headers=farmacia["headers"]
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def test_desligado_sem_chave(client, farmacia_a):
    h = farmacia_a["headers"]
    assert client.get(f"{API}/assistente/status", headers=h).json() == {"ligado": False}
    resposta = client.post(f"{API}/assistente", json={"mensagem": "oi"}, headers=h)
    assert resposta.status_code == 503
    assert "ANTHROPIC_API_KEY" in resposta.json()["detail"]
    assert client.post(f"{API}/assistente", json={"mensagem": "oi"}).status_code == 401


def test_procura_protetor_solar_com_melhor_preco_e_promocao(client, farmacia_a, modelo):
    caro = _produto(client, farmacia_a, "Protetor Solar FPS 50 Facial", "89.90")
    barato = _produto(client, farmacia_a, "Protetor solar FPS 30 corpo", "39.90")
    promo = _produto(client, farmacia_a, "Bloqueador Solar Infantil FPS 60", "59.90")
    client.post(f"{API}/produtos", json={"nome": "Protetor Solar Sem Estoque", "preco_venda": "10.00"},
                headers=farmacia_a["headers"])
    _produto(client, farmacia_a, "Dipirona 500mg", "8.90")
    _promocao(client, farmacia_a, [promo], nome="Verão", percentual="50")

    m = modelo(
        _ferramenta("buscar_produtos", {"termos": ["protetor solar", "bloqueador"], "so_promocao": False,
                                        "incluir_sem_estoque": False}),
        _texto("O mais em conta é o Bloqueador Infantil, em promoção."),
    )
    r = _perguntar(client, farmacia_a, "quero ver protetor solar")

    assert r["resposta"] == "O mais em conta é o Bloqueador Infantil, em promoção."
    [cartao] = r["cartoes"]
    assert cartao["tipo"] == "produtos"
    nomes = [i["nome"] for i in cartao["itens"]]
    # Do menor preço final para o maior, sem o que não tem estoque e sem o que não é protetor.
    assert nomes == ["Bloqueador Solar Infantil FPS 60", "Protetor solar FPS 30 corpo", "Protetor Solar FPS 50 Facial"]
    assert cartao["itens"][0]["preco_final"] == "29.95"
    assert cartao["itens"][0]["promocao"] == "50% de desconto"
    assert cartao["itens"][1]["promocao"] is None
    assert {barato["id"], caro["id"]} <= {i["produto_id"] for i in cartao["itens"]}

    # O modelo recebeu o resultado da ferramenta, e o histórico volta completo para a tela.
    resultado, erro = _resultado(m.chamadas[1]["messages"])
    assert not erro and resultado["quantidade"] == 3
    assert [msg["role"] for msg in r["historico"]] == ["user", "assistant", "user", "assistant"]
    assert m.chamadas[0]["tools"][0]["strict"] is True
    assert "Admin" in m.chamadas[0]["system"][1]["text"]

    # Acento não atrapalha e "só promoção" filtra.
    modelo(
        _ferramenta("buscar_produtos", {"termos": ["protetor solar"], "so_promocao": True,
                                        "incluir_sem_estoque": True}),
        _texto("ok"),
    )
    r = _perguntar(client, farmacia_a, "protetor em promoção", r["historico"])
    assert r["cartoes"][0]["itens"] == []


def test_abre_pre_venda_com_os_produtos(client, farmacia_a, modelo):
    produto = _produto(client, farmacia_a, "Vitamina C 1g", "25.00")
    _promocao(client, farmacia_a, [produto], percentual="10")
    ids = {}

    def criar(mensagens):
        resultado, _ = _resultado(mensagens)
        ids["produto"] = resultado["produtos"][0]["produto_id"]
        entrada = {"itens": [{"produto_id": ids["produto"], "quantidade": 2}], "cliente_cpf": None}
        return "tool_use", [{"type": "text", "text": "Abrindo."},
                            {"type": "tool_use", "id": "t2", "name": "criar_pre_venda", "input": entrada}]

    m = modelo(
        _ferramenta("buscar_produtos", {"termos": ["vitamina c"], "so_promocao": False, "incluir_sem_estoque": False}),
        criar,
        _texto("Pré-venda 1 aberta."),
    )
    r = _perguntar(client, farmacia_a, "abre uma pré-venda com duas vitamina C")
    assert ids["produto"] == produto["id"]
    pre = r["cartoes"][1]
    assert (pre["tipo"], pre["numero"], pre["total"], pre["total_com_promocoes"]) == ("pre_venda", 1, "50.00", "45.00")
    resultado, erro = _resultado(m.chamadas[2]["messages"])
    assert not erro and resultado["pre_venda_numero"] == 1
    abertas = client.get(f"{API}/pre-vendas", headers=farmacia_a["headers"]).json()
    assert [p["id"] for p in abertas] == [pre["id"]]


def test_produto_inventado_volta_como_erro(client, farmacia_a, modelo):
    m = modelo(
        _ferramenta("criar_pre_venda", {"itens": [{"produto_id": "nao-e-uuid", "quantidade": 1}], "cliente_cpf": None}),
        _texto("Não achei esse produto."),
    )
    _perguntar(client, farmacia_a, "abre pré-venda")
    conteudo, erro = _resultado(m.chamadas[1]["messages"])
    assert erro and "inválidos" in conteudo
    assert client.get(f"{API}/pre-vendas", headers=farmacia_a["headers"]).json() == []


DADOS_CLIENTE = {
    "nome": "Maria da Silva", "cpf": "52998224725", "telefone": "11987654321", "email": None,
    "data_nascimento": "1985-03-12", "cep": None, "endereco": None, "bairro": None, "cidade": "São Paulo",
    "uf": "SP", "aceita_ofertas": False,
}


def test_cadastra_cliente_falado(client, farmacia_a, modelo):
    modelo(_ferramenta("cadastrar_cliente", DADOS_CLIENTE), _texto("Maria cadastrada."))
    r = _perguntar(client, farmacia_a, "sim, pode cadastrar")
    [cartao] = r["cartoes"]
    assert (cartao["tipo"], cartao["nome"]) == ("cliente", "Maria da Silva")
    salvo = client.get(f"{API}/clientes/{cartao['id']}", headers=farmacia_a["headers"]).json()
    assert (salvo["cpf"], salvo["data_nascimento"], salvo["uf"]) == ("52998224725", "1985-03-12", "SP")

    # De novo com o mesmo CPF: a busca acha, e cadastrar volta erro para o modelo explicar.
    m = modelo(
        _ferramenta("buscar_cliente", {"busca": "52998224725"}),
        _ferramenta("cadastrar_cliente", DADOS_CLIENTE, "t2"),
        _texto("Ela já tem cadastro."),
    )
    _perguntar(client, farmacia_a, "cadastra a Maria")
    achados, _ = _resultado(m.chamadas[1]["messages"])
    assert [c["nome"] for c in achados["clientes"]] == ["Maria da Silva"]
    conteudo, erro = _resultado(m.chamadas[2]["messages"])
    assert erro and "CPF" in conteudo

    m = modelo(_ferramenta("cadastrar_cliente", {**DADOS_CLIENTE, "cpf": "12345678900"}), _texto("CPF errado."))
    _perguntar(client, farmacia_a, "cadastra")
    conteudo, erro = _resultado(m.chamadas[1]["messages"])
    assert erro and "cpf" in conteudo


def test_guia_com_tela_para_comecar(client, farmacia_a, modelo):
    modelo(_ferramenta("mostrar_guia", {"guia_id": "receber_nota"}), _texto("Veja o passo a passo."))
    r = _perguntar(client, farmacia_a, "como faço para incluir produtos recebidos do fornecedor?")
    [cartao] = r["cartoes"]
    assert (cartao["tipo"], cartao["rota"]) == ("guia", "/compras")
    assert len(cartao["passos"]) >= 3


def test_recusa_nao_guarda_a_pergunta(client, farmacia_a, modelo):
    modelo(lambda _m: ("refusal", []))
    r = _perguntar(client, farmacia_a, "algo proibido")
    assert r["historico"] == [] and "Não posso ajudar" in r["resposta"]


def test_para_de_chamar_ferramentas_no_limite(client, farmacia_a, modelo):
    passos = [_ferramenta("mostrar_guia", {"guia_id": "etiquetas"}, f"t{i}") for i in range(7)]
    m = modelo(*passos, _texto("Chega."))
    r = _perguntar(client, farmacia_a, "repete")
    assert r["resposta"] == "Chega."
    assert len(m.chamadas) == 8
    assert m.chamadas[-1]["tool_choice"] == {"type": "none"}
    assert "tool_choice" not in m.chamadas[0]
