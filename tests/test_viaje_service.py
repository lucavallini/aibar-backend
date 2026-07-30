from unittest.mock import MagicMock
from app.services.viaje_service import listar_viajes


def test_listar_viajes_vuelta_n_plus_one(query, table):
    viaje_ida = {
        "id": "ida-1",
        "viaje_vuelta_id": "vuelta-1",
        "origen": "Bs As",
        "destino": "Cba",
    }
    viaje_vuelta = {
        "id": "vuelta-1",
        "origen": "Cba",
        "destino": "Bs As",
    }

    query.execute.return_value = MagicMock(
        data=[viaje_ida, viaje_vuelta],
        count=2,
    )

    def in_side_effect(column, values):
        if column == "id":
            query.execute.return_value = MagicMock(data=[viaje_vuelta], count=1)
        return query

    query.in_ = MagicMock(side_effect=in_side_effect)

    result = listar_viajes()

    assert len(result["items"]) == 1
    assert result["items"][0]["id"] == "ida-1"
    assert result["items"][0]["viaje_vuelta"]["id"] == "vuelta-1"

    table.assert_called_with("viajes")
    query.in_.assert_called_once_with("id", ["vuelta-1"])
    assert query.execute.call_count == 2


def test_listar_viajes_sin_vueltas(query, table):
    viajes = [
        {"id": "v-1", "viaje_vuelta_id": None, "origen": "A", "destino": "B"},
        {"id": "v-2", "viaje_vuelta_id": None, "origen": "C", "destino": "D"},
    ]
    query.execute.return_value = MagicMock(data=viajes, count=2)

    result = listar_viajes()

    assert len(result["items"]) == 2
    query.in_.assert_not_called()
