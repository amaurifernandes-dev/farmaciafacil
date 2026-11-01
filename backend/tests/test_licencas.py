import os
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.licenca.formato import (
    Licenca,
    LicencaInvalida,
    assinar,
    chave_privada,
    chave_publica,
    gerar_par,
    ler,
)
from app.licenca.situacao import situacao

PRIVADA, PUBLICA = gerar_par()
URL_CENTRAL = "postgresql://ff_owner:ff_owner@localhost:5432/farmaciafacil_central_test"
os.environ.setdefault("CENTRAL_DATABASE_URL", URL_CENTRAL)
os.environ.setdefault("CENTRAL_CHAVE_PRIVADA", PRIVADA)
os.environ.setdefault("CENTRAL_JWT_SECRET", "segredo-da-central-de-teste-com-32-bytes")

from app.central.config import get_config
from app.core.config import get_settings
from app.modules.licenca import service

CNPJ_A = "11111111000111"


def _licenca(**campos) -> Licenca:
    hoje = service.hoje()
    dados = {
        "id": "1",
        "cnpj": CNPJ_A,
        "nome": "Farmácia A",
        "tipo": "nuvem",
        "plano": "mensal",
        "inicio": hoje,
        "vence": hoje + timedelta(days=30),
        "emitida_em": datetime.now(UTC),
    }
    return Licenca(**{**dados, **campos})


def _codigo(**campos) -> str:
    return assinar(_licenca(**campos), chave_privada(get_config().chave_privada))


# ---------- formato e regras ----------


def test_codigo_assinado_volta_igual_e_alterado_e_recusado():
    licenca = _licenca(modulos=["faltas"], max_usuarios=3)
    codigo = assinar(licenca, chave_privada(PRIVADA))
    assert codigo.startswith("FF1-")
    assert ler(codigo.lower(), chave_publica(PUBLICA)) == licenca  # aceita colado em minúsculas

    partes = codigo.split("-")
    letra = "A" if partes[1][3] != "A" else "B"
    adulterado = "-".join([partes[0], partes[1][:3] + letra + partes[1][4:], partes[2]])
    with pytest.raises(LicencaInvalida):
        ler(adulterado, chave_publica(PUBLICA))
    with pytest.raises(LicencaInvalida):
        ler(codigo, chave_publica(gerar_par()[1]))  # assinado por outra central
    with pytest.raises(LicencaInvalida):
        ler("ABCDE-FGHIJ", chave_publica(PUBLICA))


def test_aviso_tolerancia_e_encerramento():
    vence = date(2026, 12, 1)
    licenca = _licenca(vence=vence, tolerancia_dias=3)
    assert situacao(licenca, vence - timedelta(days=10)).estado == "normal"
    aviso = situacao(licenca, vence - timedelta(days=2))
    assert (aviso.estado, aviso.bloqueia, aviso.dias) == ("avisando", False, 2)

    # Vencida: 3 dias funcionando normal, com aviso; no 4º dia encerra.
    primeiro = situacao(licenca, vence + timedelta(days=1))
    assert (primeiro.estado, primeiro.bloqueia, primeiro.dias) == ("tolerancia", False, 3)
    ultimo = situacao(licenca, vence + timedelta(days=3))
    assert (ultimo.estado, ultimo.bloqueia, ultimo.dias) == ("tolerancia", False, 1)
    assert situacao(licenca, vence + timedelta(days=4)).estado == "encerrada"
    assert situacao(licenca, vence + timedelta(days=4)).bloqueia


def test_vitalicia_e_servidor_errado():
    assert not situacao(_licenca(plano="vitalicio", vence=None), service.hoje()).bloqueia
    presa = _licenca(maquina="AAAA-BBBB-CCCC-DDDD")
    assert situacao(presa, service.hoje(), "AAAA-BBBB-CCCC-DDDD").estado == "normal"
    assert situacao(presa, service.hoje(), "1111-2222-3333-4444").estado == "outro_servidor"


# ---------- sistema da farmácia ----------


@pytest.fixture
def com_licenca(monkeypatch, engine_dono):
    """Liga a conferência de licença (como numa instalação de verdade)."""
    monkeypatch.setattr(get_settings(), "licenca_chave_publica", PUBLICA)
    service.esquecer_cache()
    yield
    service.esquecer_cache()
    with engine_dono.begin() as conexao:
        conexao.execute(text("TRUNCATE licencas_instaladas, servidor_local"))


def _instalar(client, farmacia, codigo):
    return client.post("/api/v1/licenca", json={"codigo": codigo}, headers=farmacia["headers"])


def test_sem_licenca_o_sistema_para_e_a_tela_da_licenca_abre(client, farmacia_a, com_licenca):
    resposta = client.get("/api/v1/produtos", headers=farmacia_a["headers"])
    assert resposta.status_code == 402
    estado = client.get("/api/v1/licenca", headers=farmacia_a["headers"]).json()
    assert estado["exigida"] and estado["situacao"]["estado"] == "sem_licenca"

    instalada = _instalar(client, farmacia_a, _codigo())
    assert instalada.status_code == 200, instalada.text
    assert instalada.json()["situacao"]["estado"] == "normal"
    assert instalada.json()["licenca"]["plano"] == "mensal"
    assert client.get("/api/v1/produtos", headers=farmacia_a["headers"]).status_code == 200


def test_sem_chave_publica_nada_e_conferido(client, farmacia_a):
    assert client.get("/api/v1/produtos", headers=farmacia_a["headers"]).status_code == 200
    assert client.get("/api/v1/licenca", headers=farmacia_a["headers"]).json()["exigida"] is False


def test_codigo_de_outro_cnpj_ou_mais_antigo_e_recusado(client, farmacia_a, com_licenca):
    outro = _instalar(client, farmacia_a, _codigo(cnpj="22222222000122"))
    assert outro.status_code == 400 and "22222222000122" in outro.json()["detail"]

    antigo = _codigo(emitida_em=datetime.now(UTC) - timedelta(days=1))
    assert _instalar(client, farmacia_a, _codigo()).status_code == 200
    assert _instalar(client, farmacia_a, antigo).status_code == 400

    alterado = _codigo()[:-3] + "AAA"
    assert _instalar(client, farmacia_a, alterado).status_code == 400


def test_tolerancia_funciona_e_depois_encerra(client, farmacia_a, com_licenca):
    hoje = service.hoje()
    _instalar(client, farmacia_a, _codigo(vence=hoje - timedelta(days=2), tolerancia_dias=5))
    assert client.get("/api/v1/produtos", headers=farmacia_a["headers"]).status_code == 200
    estado = client.get("/api/v1/licenca", headers=farmacia_a["headers"]).json()["situacao"]
    assert estado["estado"] == "tolerancia" and estado["dias"] == 4

    _instalar(client, farmacia_a, _codigo(vence=hoje - timedelta(days=6), tolerancia_dias=5))
    bloqueio = client.get("/api/v1/produtos", headers=farmacia_a["headers"])
    assert bloqueio.status_code == 402 and "tolerância" in bloqueio.json()["detail"]
    # A tela da licença continua abrindo, para colar o código renovado.
    assert _instalar(client, farmacia_a, _codigo(vence=hoje + timedelta(days=30))).status_code == 200
    assert client.get("/api/v1/produtos", headers=farmacia_a["headers"]).status_code == 200


def test_licenca_online_nao_serve_instalada_na_farmacia(client, farmacia_a, com_licenca, monkeypatch):
    _instalar(client, farmacia_a, _codigo())
    monkeypatch.setattr(get_settings(), "instalacao", "farmacia")
    service.esquecer_cache()
    assert client.get("/api/v1/produtos", headers=farmacia_a["headers"]).status_code == 402


def test_na_farmacia_a_licenca_fica_presa_ao_servidor(client, farmacia_a, com_licenca, monkeypatch):
    monkeypatch.setattr(get_settings(), "instalacao", "farmacia")
    # Sem login: é por aqui que se ativa um servidor vencido.
    estado = client.get("/api/v1/licenca").json()
    codigo_servidor = estado["codigo_servidor"]
    assert len(codigo_servidor) == 19

    de_outro = client.post(
        "/api/v1/licenca", json={"codigo": _codigo(tipo="farmacia", maquina="AAAA-BBBB-CCCC-DDDD")}
    )
    assert de_outro.status_code == 200
    assert de_outro.json()["situacao"]["estado"] == "outro_servidor"
    assert client.get("/api/v1/produtos", headers=farmacia_a["headers"]).status_code == 402

    deste = client.post("/api/v1/licenca", json={"codigo": _codigo(tipo="farmacia", maquina=codigo_servidor)})
    assert deste.json()["situacao"]["estado"] == "normal"
    assert client.get("/api/v1/produtos", headers=farmacia_a["headers"]).status_code == 200


def test_relogio_voltado_para_o_sistema(client, farmacia_a, com_licenca, engine_dono):
    _instalar(client, farmacia_a, _codigo())
    with engine_dono.begin() as conexao:
        conexao.execute(
            text("UPDATE servidor_local SET maior_data = :dia"), {"dia": service.hoje() + timedelta(days=10)}
        )
    service.esquecer_cache()
    resposta = client.get("/api/v1/produtos", headers=farmacia_a["headers"])
    assert resposta.status_code == 402 and "data" in resposta.json()["detail"]


def test_modulos_fora_da_licenca(client, farmacia_a, com_licenca):
    _instalar(client, farmacia_a, _codigo(modulos=["devolucoes", "pedidos"]))
    configuracoes = client.get("/api/v1/configuracoes", headers=farmacia_a["headers"]).json()
    assert "faltas" in configuracoes["modulos_fora_da_licenca"]
    assert "pedidos" not in configuracoes["modulos_fora_da_licenca"]
    faltas = client.get("/api/v1/faltas", headers=farmacia_a["headers"])
    assert faltas.status_code == 403 and "licença" in faltas.json()["detail"]
    assert client.get("/api/v1/pedidos", headers=farmacia_a["headers"]).status_code == 200


def test_limite_de_usuarios_e_caixas(client, farmacia_a, com_licenca):
    _instalar(client, farmacia_a, _codigo(max_usuarios=2, max_caixas=1))
    h = farmacia_a["headers"]
    novo = {"nome": "Júlia", "email": "julia@a.com", "papel": "caixa", "senha": "senha-forte"}
    assert client.post("/api/v1/usuarios", json=novo, headers=h).status_code == 201
    demais = client.post("/api/v1/usuarios", json={**novo, "email": "x@a.com"}, headers=h)
    assert demais.status_code == 403 and "até 2 usuários" in demais.json()["detail"]

    loja = client.get("/api/v1/lojas", headers=h).json()[0]["id"]
    assert client.post("/api/v1/terminais", json={"loja_id": loja, "nome": "Caixa 1"}, headers=h).status_code == 201
    segundo = client.post("/api/v1/terminais", json={"loja_id": loja, "nome": "Caixa 2"}, headers=h)
    assert segundo.status_code == 403


# ---------- central de licenças ----------


@pytest.fixture(scope="module")
def central_banco():
    servidor = create_engine(URL_CENTRAL.rsplit("/", 1)[0] + "/postgres", isolation_level="AUTOCOMMIT")
    with servidor.connect() as conexao:
        if not conexao.scalar(text("SELECT 1 FROM pg_database WHERE datname = 'farmaciafacil_central_test'")):
            conexao.execute(text("CREATE DATABASE farmaciafacil_central_test"))
    servidor.dispose()

    from alembic import command
    from alembic.config import Config

    engine = create_engine(get_config().database_url)
    with engine.begin() as conexao:
        conexao.execute(text("DROP SCHEMA public CASCADE"))
        conexao.execute(text("CREATE SCHEMA public"))
    pasta = os.path.dirname(os.path.dirname(__file__))
    config = Config(os.path.join(pasta, "alembic_central.ini"))
    config.set_main_option("script_location", os.path.join(pasta, "migrations_central"))
    command.upgrade(config, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def central(central_banco):
    from app.central.main import app as app_central
    from app.central.models import UsuarioCentral
    from app.core.security import gerar_hash_senha

    with central_banco.begin() as conexao:
        conexao.execute(text("TRUNCATE usuarios_central, licencas, historico_licencas RESTART IDENTITY CASCADE"))
    with Session(central_banco) as db:
        db.add(UsuarioCentral(nome="Amauri", email="amauri@central.com", senha_hash=gerar_hash_senha("senha-forte")))
        db.commit()
    cliente = TestClient(app_central)
    token = cliente.post("/api/entrar", json={"email": "amauri@central.com", "senha": "senha-forte"}).json()
    cliente.headers["Authorization"] = f"Bearer {token['access_token']}"
    return cliente


def _cadastrar(central, **campos):
    dados = {"cnpj": "11.222.333/0001-81", "nome": "Farmácia A", "tipo": "farmacia", "plano": "mensal", **campos}
    resposta = central.post("/api/licencas", json=dados)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def test_central_exige_login(central_banco):
    from app.central.main import app as app_central

    cliente = TestClient(app_central)
    assert cliente.get("/api/licencas").status_code == 401
    assert cliente.post("/api/entrar", json={"email": "x@x.com", "senha": "errada"}).status_code == 401
    assert "Central de licenças" in cliente.get("/").text


def test_central_cadastra_renova_e_conta_os_dias(central):
    inicio = "2026-11-01"
    lic = _cadastrar(central, inicio=inicio, tolerancia_dias=10, max_caixas=2, modulos=["faltas"])
    assert lic["cnpj"] == "11222333000181"
    assert lic["vence"] == "2026-12-01"  # 31 dias contando o dia do cadastro
    assert len(lic["chave_ativacao"]) == 29

    renovada = central.post(f"/api/licencas/{lic['id']}/renovar").json()
    assert renovada["vence"] == "2027-01-01"
    anual = _cadastrar(central, plano="anual", inicio=inicio)
    assert anual["vence"] == "2027-10-31"
    vitalicia = _cadastrar(central, plano="vitalicio")
    assert vitalicia["vence"] is None
    assert central.post(f"/api/licencas/{vitalicia['id']}/renovar").status_code == 400

    mudada = central.patch(f"/api/licencas/{lic['id']}", json={"tolerancia_dias": 30}).json()
    assert mudada["tolerancia_dias"] == 30
    eventos = central.get(f"/api/licencas/{lic['id']}/historico").json()
    assert [e["o_que"] for e in eventos][-1].startswith("Cadastrou")
    assert len(central.get("/api/licencas", params={"busca": "112223"}).json()) == 3


def test_central_prende_ao_servidor_e_libera_troca(central):
    lic = _cadastrar(central)
    chave = lic["chave_ativacao"]
    primeira = central.post("/api/ativar", json={"chave_ativacao": chave.lower(), "maquina": "AAAABBBBCCCCDDDD"})
    assert primeira.status_code == 200, primeira.text
    codigo = ler(primeira.json()["codigo"], chave_publica(PUBLICA))
    assert codigo.maquina == "AAAA-BBBB-CCCC-DDDD" and codigo.cnpj == "11222333000181"

    outro = central.post("/api/ativar", json={"chave_ativacao": chave, "maquina": "1111-2222-3333-4444"})
    assert outro.status_code == 409
    central.post(f"/api/licencas/{lic['id']}/liberar-troca")
    assert central.post("/api/ativar", json={"chave_ativacao": chave, "maquina": "1111-2222-3333-4444"}).status_code == 200

    central.post(f"/api/licencas/{lic['id']}/suspender")
    assert central.post("/api/ativar", json={"chave_ativacao": chave, "maquina": "1111-2222-3333-4444"}).status_code == 403
    assert central.post("/api/ativar", json={"chave_ativacao": "XXXXX-XXXXX", "maquina": None}).status_code == 404


def test_central_gera_codigo_para_servidor_sem_internet(central):
    lic = _cadastrar(central)
    sem_maquina = central.post(f"/api/licencas/{lic['id']}/codigo", json={})
    assert sem_maquina.status_code == 400
    resposta = central.post(f"/api/licencas/{lic['id']}/codigo", json={"maquina": "aaaa-bbbb-cccc-dddd"})
    assert resposta.status_code == 200
    assert ler(resposta.json()["codigo"], chave_publica(PUBLICA)).maquina == "AAAA-BBBB-CCCC-DDDD"


def test_servidor_ativa_e_renova_sozinho_pela_central(client, farmacia_a, com_licenca, central, monkeypatch):
    monkeypatch.setattr(get_settings(), "instalacao", "farmacia")
    monkeypatch.setattr(get_settings(), "licencas_url", "https://central.exemplo")

    def post(url, json, timeout):
        assert url == "https://central.exemplo/api/ativar"
        return central.post("/api/ativar", json=json)

    monkeypatch.setattr(service.httpx, "post", post)
    monkeypatch.setattr("app.central.schemas.cnpj_valido", lambda _: True)  # o CNPJ de teste da farmácia A
    lic = _cadastrar(central, cnpj=CNPJ_A, max_usuarios=5)

    errada = client.post("/api/v1/licenca", json={"chave_ativacao": "ZZZZZ-ZZZZZ-ZZZZZ-ZZZZZ-ZZZZZ"})
    assert errada.status_code == 400 and "não encontrada" in errada.json()["detail"]

    ativada = client.post("/api/v1/licenca", json={"chave_ativacao": lic["chave_ativacao"]})
    assert ativada.status_code == 200, ativada.text
    assert ativada.json()["renova_sozinha"] and ativada.json()["situacao"]["estado"] == "normal"
    assert client.get("/api/v1/produtos", headers=farmacia_a["headers"]).status_code == 200
    servidor = ativada.json()["codigo_servidor"]
    assert central.get("/api/licencas").json()[0]["maquina"] == servidor

    # Você renova na central; o servidor busca sozinho o código novo.
    central.post(f"/api/licencas/{lic['id']}/renovar")
    renovada = client.post("/api/v1/licenca/renovar").json()
    assert renovada["licenca"]["vence"] == central.get("/api/licencas").json()[0]["vence"]
