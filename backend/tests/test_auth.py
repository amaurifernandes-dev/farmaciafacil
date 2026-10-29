def test_login_com_senha_errada(client, farmacia_a):
    resposta = client.post("/api/v1/auth/login", json={"email": "a@farmacia.com", "senha": "errada"})
    assert resposta.status_code == 401


def test_login_email_inexistente(client):
    resposta = client.post("/api/v1/auth/login", json={"email": "ninguem@x.com", "senha": "x"})
    assert resposta.status_code == 401


def test_login_ignora_maiusculas_no_email(client, farmacia_a):
    resposta = client.post("/api/v1/auth/login", json={"email": "A@Farmacia.com", "senha": "senha-forte"})
    assert resposta.status_code == 200


def test_rota_protegida_sem_token(client):
    assert client.get("/api/v1/produtos").status_code == 401


def test_token_invalido(client):
    resposta = client.get("/api/v1/produtos", headers={"Authorization": "Bearer abc"})
    assert resposta.status_code == 401


def test_eu_devolve_farmacia_do_token(client, farmacia_a):
    resposta = client.get("/api/v1/auth/eu", headers=farmacia_a["headers"])
    assert resposta.json()["farmacia_id"] == str(farmacia_a["id"])
