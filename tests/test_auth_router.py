from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_login_devuelve_429_al_superar_el_limite_de_intentos():
    for _ in range(5):
        respuesta = client.post("/auth/login", data={"username": "nadie", "password": "x"})
        assert respuesta.status_code == 401

    respuesta = client.post("/auth/login", data={"username": "nadie", "password": "x"})
    assert respuesta.status_code == 429
