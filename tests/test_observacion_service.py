from unittest.mock import MagicMock

from app.services.observacion_service import listar_observaciones_mes_actual


def test_listar_observaciones_mes_actual_filtra_por_mes_y_anio(query, table):
    observaciones = [
        {"id": "obs-1", "chofer_id": "chofer-1", "observacion": "Todo bien"},
        {"id": "obs-2", "chofer_id": "chofer-2", "observacion": "Faltó carnet"},
    ]
    query.execute.return_value = MagicMock(data=observaciones)

    resultado = listar_observaciones_mes_actual()

    assert resultado == observaciones
    assert table.call_args_list[-1].args == ("observaciones",)
    columnas_filtradas = [call.args[0] for call in query.eq.call_args_list]
    assert "mes" in columnas_filtradas
    assert "anio" in columnas_filtradas
