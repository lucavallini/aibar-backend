"""El estado de una unidad se deriva de sus viajes, nunca se escribe a mano.

Estos tests cubren los caminos por los que una unidad quedaba reservada sin viaje o
libre teniendo uno, que es lo que hacía desaparecer camiones del desplegable.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.database import supabase
from app.models.viaje import ViajeCancelar, ViajeEditar, ViajeFinalizar, ViajeReanudar
from app.services import viaje_service


CAM1 = "00000000-0000-0000-0000-0000000000c1"
CAM2 = "00000000-0000-0000-0000-0000000000c2"
ACO1 = "00000000-0000-0000-0000-0000000000a1"
ACO2 = "00000000-0000-0000-0000-0000000000a2"
CHO1 = "00000000-0000-0000-0000-0000000000f1"
CHO2 = "00000000-0000-0000-0000-0000000000f2"


@pytest.fixture
def base():
    """Base en memoria: guarda los estados escritos para poder afirmar sobre ellos."""
    datos = {
        "viajes": [],
        "camiones": [{"id": CAM1, "estado": "disponible"}, {"id": CAM2, "estado": "disponible"}],
        "acoplados": [{"id": ACO1, "estado": "disponible"}, {"id": ACO2, "estado": "disponible"}],
        "choferes": [{"id": CHO1, "estado": "disponible"}, {"id": CHO2, "estado": "disponible"}],
        "cargas_combustible": [],
        "multas": [],
    }

    def tabla(nombre):
        q = MagicMock()
        q._f, q._accion, q._payload = {}, "select", None

        def guardar_filtro(campo, valor):
            q._f[campo] = valor
            return q

        def coincide(fila):
            for campo, valor in q._f.items():
                actual = fila.get(campo)
                if isinstance(valor, list):
                    if actual not in valor:
                        return False
                elif str(actual) != str(valor):
                    return False
            return True

        def ejecutar():
            filas = datos.get(nombre, [])
            elegidas = [f for f in filas if coincide(f)]
            if q._accion == "update":
                for f in elegidas:
                    f.update(q._payload)
                return MagicMock(data=list(elegidas), count=len(elegidas))
            if q._accion == "delete":
                datos[nombre] = [f for f in filas if f not in elegidas]
                return MagicMock(data=list(elegidas), count=len(elegidas))
            if q._accion == "insert":
                fila = {"id": f"{nombre[:3]}-nuevo", **q._payload}
                filas.append(fila)
                return MagicMock(data=[fila], count=1)
            return MagicMock(data=list(elegidas), count=len(elegidas))

        q.select.side_effect = lambda *a, **k: q
        q.order.side_effect = lambda *a, **k: q
        q.neq.side_effect = lambda *a, **k: q
        q.or_.side_effect = lambda *a, **k: q
        q.eq.side_effect = guardar_filtro
        q.in_.side_effect = guardar_filtro
        q.update.side_effect = lambda p, *a, **k: (setattr(q, "_accion", "update"), setattr(q, "_payload", p), q)[-1]
        q.delete.side_effect = lambda *a, **k: (setattr(q, "_accion", "delete"), q)[-1]
        q.insert.side_effect = lambda p, *a, **k: (setattr(q, "_accion", "insert"), setattr(q, "_payload", p), q)[-1]
        q.execute.side_effect = ejecutar
        return q

    supabase.table = MagicMock(side_effect=tabla)
    return datos


@pytest.fixture(autouse=True)
def sin_ruido():
    with patch.object(viaje_service, "registrar_evento"), \
         patch.object(viaje_service, "_obtener_nombre_chofer", return_value="JUAN"), \
         patch.object(viaje_service, "_obtener_nombre_usuario", return_value="ADMIN"):
        yield


def _viaje(base, estado="pendiente", camion=CAM1, acoplado=ACO1, chofer=CHO1):
    v = {
        "id": "via-1", "estado": estado, "origen": "ROSARIO", "destino": "SALTA",
        "fecha_inicio": "2026-09-01T10:00:00-03:00", "fecha_fin": None,
        "camion_id": camion, "camion_id_2": acoplado, "chofer_id": chofer,
        "viaje_vuelta_id": None, "solo_ida": False,
    }
    base["viajes"].append(v)
    ocupado = "viajando" if estado == "en_curso" else "esperando_iniciar_viaje"
    for tabla, uid in (("camiones", camion), ("acoplados", acoplado), ("choferes", chofer)):
        if uid:
            next(f for f in base[tabla] if f["id"] == uid)["estado"] = ocupado
    return v


def _estado(base, tabla, uid):
    return next(f for f in base[tabla] if f["id"] == uid)["estado"]


def test_quitarle_el_acoplado_al_viaje_lo_libera(base):
    """El agujero que dejó AG376XA reservado sin ningún viaje."""
    _viaje(base)

    viaje_service.editar_viaje("via-1", ViajeEditar(camion_id_2=None), usuario_id="u1")

    assert _estado(base, "acoplados", ACO1) == "disponible"


def test_cambiar_el_acoplado_libera_el_anterior_y_reserva_el_nuevo(base):
    _viaje(base)

    viaje_service.editar_viaje("via-1", ViajeEditar(camion_id_2=ACO2), usuario_id="u1")

    assert _estado(base, "acoplados", ACO1) == "disponible"
    assert _estado(base, "acoplados", ACO2) == "esperando_iniciar_viaje"


def test_finalizar_libera_las_tres_unidades(base):
    _viaje(base, estado="en_curso")

    viaje_service.finalizar_viaje(
        "via-1", ViajeFinalizar(fecha_fin="2026-09-02T10:00:00-03:00", kms_recorridos=500), usuario_id="u1")

    assert _estado(base, "camiones", CAM1) == "disponible"
    assert _estado(base, "acoplados", ACO1) == "disponible"
    assert _estado(base, "choferes", CHO1) == "disponible"


def test_cancelar_libera_las_tres_unidades(base):
    _viaje(base, estado="en_curso")

    viaje_service.cancelar_viaje("via-1", ViajeCancelar(motivo_cancelacion="LLUVIA"), usuario_id="u1")

    assert _estado(base, "camiones", CAM1) == "disponible"
    assert _estado(base, "choferes", CHO1) == "disponible"


def test_reanudar_sin_cambiar_unidades_las_vuelve_a_reservar(base):
    """Si no se reservan, el viaje queda pendiente con el camión ofrecido a otro."""
    _viaje(base, estado="cancelado")
    for tabla, uid in (("camiones", CAM1), ("acoplados", ACO1), ("choferes", CHO1)):
        next(f for f in base[tabla] if f["id"] == uid)["estado"] = "disponible"

    viaje_service.reanudar_viaje("via-1", ViajeReanudar(), usuario_id="u1")

    assert _estado(base, "camiones", CAM1) == "esperando_iniciar_viaje"
    assert _estado(base, "acoplados", ACO1) == "esperando_iniciar_viaje"
    assert _estado(base, "choferes", CHO1) == "esperando_iniciar_viaje"


def test_el_chofer_con_otro_viaje_en_curso_no_se_libera(base):
    """Finalizar un viaje no puede dejar disponible a un chofer que sigue en la ruta."""
    _viaje(base, estado="en_curso")
    base["viajes"].append({
        "id": "via-2", "estado": "en_curso", "origen": "A", "destino": "B",
        "fecha_inicio": "2026-09-01T10:00:00-03:00", "fecha_fin": None,
        "camion_id": CAM2, "camion_id_2": None, "chofer_id": CHO1, "viaje_vuelta_id": None,
    })

    viaje_service.finalizar_viaje(
        "via-1", ViajeFinalizar(fecha_fin="2026-09-02T10:00:00-03:00", kms_recorridos=500), usuario_id="u1")

    assert _estado(base, "choferes", CHO1) == "viajando"


def test_iniciar_pone_las_unidades_en_viajando(base):
    _viaje(base)

    viaje_service.iniciar_viaje("via-1", usuario_id="u1")

    assert _estado(base, "camiones", CAM1) == "viajando"
    assert _estado(base, "acoplados", ACO1) == "viajando"
    assert _estado(base, "choferes", CHO1) == "viajando"


def test_una_unidad_en_taller_no_se_toca(base):
    """no_disponible es una decisión de una persona, no una consecuencia de los viajes."""
    next(f for f in base["camiones"] if f["id"] == CAM2)["estado"] = "no_disponible"

    viaje_service.sincronizar_unidades(CAM2)

    assert _estado(base, "camiones", CAM2) == "no_disponible"
