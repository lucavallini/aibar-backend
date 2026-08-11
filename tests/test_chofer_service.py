import uuid
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import ConflictError
from app.models.chofer import ChoferCambiarEstado
from app.services.chofer_service import (
    obtener_detalle_chofer,
    calcular_kms_historico,
    cambiar_estado_chofer,
)


def test_obtener_detalle_chofer_agrupa_kms_por_mes(query, table):
    chofer_data = {"id": "chofer-1", "nombre_completo": "Juan Perez", "estado": "disponible"}
    viajes_data = [
        {"kms_recorridos": 100, "fecha_inicio": "2026-08-05T10:00:00"},
        {"kms_recorridos": 50, "fecha_inicio": "2026-08-01T10:00:00"},
        {"kms_recorridos": 200, "fecha_inicio": "2026-07-15T10:00:00"},
        {"kms_recorridos": 30, "fecha_inicio": "2026-07-01T10:00:00"},
    ]
    query.execute.side_effect = [
        MagicMock(data=[chofer_data]),
        MagicMock(data=viajes_data),
    ]

    with patch("app.services.chofer_service.date") as mock_date:
        mock_date.today.return_value = date(2026, 8, 10)
        resultado = obtener_detalle_chofer("chofer-1")

    assert resultado["id"] == "chofer-1"
    assert resultado["kms_mes_actual"] == 150
    assert resultado["historico"] == [
        {"mes": "2026-08", "kms": 150},
        {"mes": "2026-07", "kms": 230},
    ]


def test_calcular_kms_historico_agrupa_por_mes_desc(query, table):
    viajes_data = [
        {"kms_recorridos": 100, "fecha_inicio": "2026-08-05T10:00:00"},
        {"kms_recorridos": 200, "fecha_inicio": "2026-06-15T10:00:00"},
        {"kms_recorridos": 30, "fecha_inicio": "2026-06-01T10:00:00"},
    ]
    query.execute.return_value = MagicMock(data=viajes_data)

    resultado = calcular_kms_historico("chofer-1")

    assert resultado == [
        {"mes": "2026-08", "kms": 100},
        {"mes": "2026-06", "kms": 230},
    ]


def test_cambiar_estado_chofer_conflicto_si_en_uso(query, table):
    chofer_id = str(uuid.uuid4())
    usuario_id = uuid.uuid4()
    chofer = {"id": chofer_id, "nombre_completo": "Juan Perez", "estado": "disponible"}

    query.execute.side_effect = [
        MagicMock(data=[chofer]),             # obtener_chofer
        MagicMock(data=[{"id": "viaje-1"}]),  # en_uso: hay un viaje pendiente/en_curso
    ]

    with pytest.raises(ConflictError):
        cambiar_estado_chofer(
            chofer_id,
            ChoferCambiarEstado(estado="no_disponible", motivo_no_disponible="Licencia"),
            usuario_id=usuario_id,
        )


def test_cambiar_estado_chofer_ok_si_no_esta_en_uso(query, table):
    chofer_id = str(uuid.uuid4())
    usuario_id = uuid.uuid4()
    chofer = {"id": chofer_id, "nombre_completo": "Juan Perez", "estado": "disponible"}
    chofer_actualizado = {**chofer, "estado": "no_disponible", "motivo_no_disponible": "Licencia"}

    query.update.return_value = query
    query.insert.return_value = query
    query.execute.side_effect = [
        MagicMock(data=[chofer]),               # obtener_chofer
        MagicMock(data=[]),                     # en_uso: ningún viaje activo
        MagicMock(data=[chofer_actualizado]),   # update
        MagicMock(data=[{"id": "evento-1"}]),   # registrar_evento insert
    ]

    resultado = cambiar_estado_chofer(
        chofer_id,
        ChoferCambiarEstado(estado="no_disponible", motivo_no_disponible="Licencia"),
        usuario_id=usuario_id,
    )

    assert resultado["estado"] == "no_disponible"
