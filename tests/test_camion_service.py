import uuid
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import ConflictError
from app.models.camion import CamionCambiarEstado
from app.services.camion_service import cambiar_estado_camion


def test_cambiar_estado_camion_conflicto_si_en_uso(query, table):
    camion_id = str(uuid.uuid4())
    usuario_id = uuid.uuid4()
    camion = {"id": camion_id, "patente": "AB123CD", "estado": "disponible"}

    query.execute.side_effect = [
        MagicMock(data=[camion]),          # obtener_camion
        MagicMock(data=[{"id": "viaje-1"}]),  # en_uso: hay un viaje pendiente/en_curso
    ]

    with pytest.raises(ConflictError):
        cambiar_estado_camion(
            camion_id,
            CamionCambiarEstado(estado="no_disponible", motivo_no_disponible="Service"),
            usuario_id=usuario_id,
        )


def test_cambiar_estado_camion_ok_si_no_esta_en_uso(query, table):
    camion_id = str(uuid.uuid4())
    usuario_id = uuid.uuid4()
    camion = {"id": camion_id, "patente": "AB123CD", "estado": "disponible"}
    camion_actualizado = {**camion, "estado": "no_disponible", "motivo_no_disponible": "Service"}

    query.update.return_value = query
    query.insert.return_value = query
    query.execute.side_effect = [
        MagicMock(data=[camion]),        # obtener_camion
        MagicMock(data=[]),              # en_uso: ningún viaje activo
        MagicMock(data=[camion_actualizado]),  # update
        MagicMock(data=[{"id": "evento-1"}]),  # registrar_evento insert
    ]

    resultado = cambiar_estado_camion(
        camion_id,
        CamionCambiarEstado(estado="no_disponible", motivo_no_disponible="Service"),
        usuario_id=usuario_id,
    )

    assert resultado["estado"] == "no_disponible"
