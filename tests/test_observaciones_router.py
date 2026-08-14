import uuid
from datetime import datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_current_user
from app.models.usuario import UsuarioOut


def _override_usuario():
    return UsuarioOut(
        id=uuid.uuid4(),
        nombre_usuario="qa",
        nombre_completo="QA",
        dni="1",
        rol="administrador",
        activo=True,
        creado_en=datetime.now(),
    )


def test_mes_actual_no_colisiona_con_ruta_de_chofer_id(query, table):
    app.dependency_overrides[get_current_user] = _override_usuario
    query.execute.return_value = MagicMock(data=[])

    client = TestClient(app)
    try:
        respuesta = client.get("/observaciones/mes-actual")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert respuesta.status_code == 200
    assert respuesta.json() == []
