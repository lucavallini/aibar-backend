from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import BadRequestError
from app.database import supabase
from app.services import chofer_service


def _viaje(chofer_id: str, kms: float) -> dict:
    return {"chofer_id": chofer_id, "kms_recorridos": kms}


@pytest.fixture
def base_de_datos():
    """supabase.table devuelve datos distintos según la tabla consultada."""
    datos: dict[str, list] = {"choferes": [], "viajes": []}

    def tabla(nombre: str):
        query = MagicMock()
        for metodo in ("select", "eq", "in_", "order", "gte", "lte", "ilike", "range"):
            getattr(query, metodo).return_value = query
        query.execute.return_value = MagicMock(data=datos[nombre], count=len(datos[nombre]))
        return query

    supabase.table = MagicMock(side_effect=tabla)
    return datos


def test_sin_filtros_la_ventana_es_el_mes_en_curso():
    desde, hasta = chofer_service._resolver_ventana()
    assert desde == date.today().replace(day=1)
    assert hasta is None


def test_el_periodo_en_dias_se_cuenta_hacia_atras_desde_hoy():
    desde, _ = chofer_service._resolver_ventana(dias=60)
    assert desde == date.today() - timedelta(days=60)


def test_las_fechas_explicitas_mandan_sobre_el_mes_en_curso():
    desde, hasta = chofer_service._resolver_ventana(fecha_desde="2026-01-10", fecha_hasta="2026-02-20")
    assert (desde, hasta) == (date(2026, 1, 10), date(2026, 2, 20))


def test_periodo_y_rango_se_intersecan_gana_el_mas_restrictivo():
    """Igual que en viajes: si llegan los dos, se aplican ambos."""
    hace_mucho = (date.today() - timedelta(days=365)).isoformat()
    desde, _ = chofer_service._resolver_ventana(dias=15, fecha_desde=hace_mucho)
    assert desde == date.today() - timedelta(days=15)


def test_un_rango_al_reves_se_rechaza():
    with pytest.raises(BadRequestError, match="anterior a la fecha desde"):
        chofer_service._resolver_ventana(fecha_desde="2026-03-10", fecha_hasta="2026-03-01")


def test_las_estadisticas_se_calculan_sobre_la_ventana(base_de_datos):
    base_de_datos["choferes"] = [{"id": "cho-1", "nombre_completo": "JUAN PEREZ"}]
    base_de_datos["viajes"] = [_viaje("cho-1", 100.0), _viaje("cho-1", 250.5), _viaje("cho-2", 80.0)]

    r = chofer_service.listar_choferes(incluir_estadisticas=True, dias=30)

    chofer = r["items"][0]
    assert chofer["kms_periodo"] == 350.5
    assert chofer["viajes_periodo"] == 2
    assert chofer["promedio_kms_viaje"] == 175.25


def test_el_chofer_sin_viajes_aparece_igual_en_cero(base_de_datos):
    """El filtro cambia la columna de kms, no esconde choferes."""
    base_de_datos["choferes"] = [{"id": "cho-9", "nombre_completo": "SIN VIAJES"}]

    chofer = chofer_service.listar_choferes(incluir_estadisticas=True, dias=15)["items"][0]

    assert chofer["kms_periodo"] == 0
    assert chofer["viajes_periodo"] == 0
    assert chofer["promedio_kms_viaje"] == 0


def test_el_total_del_periodo_suma_a_todos_los_alcanzados_no_solo_a_la_pagina(base_de_datos):
    base_de_datos["choferes"] = [{"id": "cho-1", "nombre_completo": "A"}]
    base_de_datos["viajes"] = [_viaje("cho-1", 100.0), _viaje("cho-2", 400.0), _viaje("cho-3", 10.5)]

    periodo = chofer_service.listar_choferes(incluir_estadisticas=True)["periodo"]

    assert periodo["total_kms"] == 510.5
    assert periodo["total_viajes"] == 3
    assert periodo["desde"] == date.today().replace(day=1)


def test_sin_pedir_estadisticas_no_se_agrega_nada(base_de_datos):
    base_de_datos["choferes"] = [{"id": "cho-1", "nombre_completo": "A"}]

    r = chofer_service.listar_choferes()

    assert "periodo" not in r
    assert "kms_periodo" not in r["items"][0]
