from datetime import date

from app.services.kms_diarios_service import (
    CON_MOVIMIENTO,
    DETENIDO,
    SIN_DATOS,
    clasificar_dia,
    dias_del_rango,
)


def _respuesta(km=0.0, tramos=0, paradas=0, eventos=0) -> dict:
    return {
        "Summary": {"DistanceKm": km},
        "Trips": [{}] * tramos,
        "Stops": [{}] * paradas,
        "Events": [{}] * eventos,
    }


def test_un_dia_con_kilometros_es_movimiento():
    r = clasificar_dia(_respuesta(km=719.84, tramos=3, paradas=3, eventos=40))

    assert r["estado"] == CON_MOVIMIENTO
    assert r["km"] == 719.84


def test_sin_kilometros_pero_con_eventos_el_camion_estuvo_quieto():
    """Caso real de AF356AD el 13/09: 0 km y 58 eventos. El equipo reportó, no se movió."""
    r = clasificar_dia(_respuesta(km=0.0, eventos=58))

    assert r["estado"] == DETENIDO
    assert r["km"] == 0


def test_sin_nada_no_sabemos_y_eso_no_es_cero():
    """Caso real de AA520IE, siete días sin reportar: cero de todo.

    Guardar 0 acá sería afirmar que no anduvo, y hundiría cualquier promedio.
    """
    r = clasificar_dia(_respuesta())

    assert r["estado"] == SIN_DATOS
    assert r["km"] is None


def test_una_parada_sola_tambien_alcanza_como_senal_de_vida():
    r = clasificar_dia(_respuesta(paradas=1))

    assert r["estado"] == DETENIDO
    assert r["km"] == 0


def test_un_tramo_sin_distancia_sigue_siendo_movimiento():
    """Un tramo de 0,1 km redondea a cero pero la unidad se movió."""
    r = clasificar_dia(_respuesta(km=0.0, tramos=1, paradas=1))

    assert r["estado"] == CON_MOVIMIENTO
    assert r["km"] == 0


def test_se_guardan_los_conteos_para_poder_auditar():
    r = clasificar_dia(_respuesta(km=10, tramos=2, paradas=3, eventos=4))

    assert (r["tramos"], r["paradas"], r["eventos"]) == (2, 3, 4)


def test_el_rango_se_recorre_dia_por_dia_e_incluye_los_extremos():
    dias = dias_del_rango(date(2026, 9, 14), date(2026, 9, 17))

    assert dias == [date(2026, 9, 14), date(2026, 9, 15), date(2026, 9, 16), date(2026, 9, 17)]


def test_un_solo_dia_devuelve_ese_dia():
    assert dias_del_rango(date(2026, 9, 17), date(2026, 9, 17)) == [date(2026, 9, 17)]
