from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import NotFoundError
from app.database import supabase
from app.services import viaje_service


def _viaje(vid="via-1", estado="finalizado", vuelta=None, chofer="cho-1", camion="cam-1") -> dict:
    return {
        "id": vid,
        "estado": estado,
        "origen": "ROSARIO",
        "destino": "BAHIA BLANCA",
        "fecha_inicio": "2026-08-24T19:00:00-03:00",
        "viaje_vuelta_id": vuelta,
        "chofer_id": chofer,
        "camion_id": camion,
        "camion_id_2": None,
    }


@pytest.fixture
def base():
    """Registra cada operación contra supabase para poder afirmar qué se borró y qué no."""
    estado = {
        "viajes": [],
        "cargas_combustible": [],
        "borrados": {},
        "updates": [],
    }

    def tabla(nombre):
        q = MagicMock()
        q._filtros = {}
        q._accion = "select"
        q._payload = None

        def select(*a, **k):
            q._accion = "select"
            return q

        def delete(*a, **k):
            q._accion = "delete"
            return q

        def update(payload, *a, **k):
            q._accion = "update"
            q._payload = payload
            return q

        def eq(campo, valor):
            q._filtros[campo] = valor
            return q

        def in_(campo, valores):
            q._filtros[campo] = list(valores)
            return q

        def ejecutar():
            if q._accion == "delete":
                estado["borrados"].setdefault(nombre, []).extend(
                    q._filtros.get("id") or q._filtros.get("viaje_id") or []
                )
                filas = estado["cargas_combustible"] if nombre == "cargas_combustible" else estado["viajes"]
                return MagicMock(data=[{"id": f["id"]} for f in filas])
            if q._accion == "update":
                estado["updates"].append((nombre, q._payload, dict(q._filtros)))
                return MagicMock(data=[{}])
            if nombre == "viajes":
                if "viaje_vuelta_id" in q._filtros:
                    return MagicMock(
                        data=[v for v in estado["viajes"] if v.get("viaje_vuelta_id") == q._filtros["viaje_vuelta_id"]]
                    )
                pedido = q._filtros.get("id")
                return MagicMock(data=[v for v in estado["viajes"] if v["id"] == pedido])
            return MagicMock(data=[])

        q.select.side_effect = select
        q.delete.side_effect = delete
        q.update.side_effect = update
        q.eq.side_effect = eq
        q.in_.side_effect = in_
        q.or_.return_value = q
        q.execute.side_effect = ejecutar
        return q

    supabase.table = MagicMock(side_effect=tabla)
    return estado


@pytest.fixture(autouse=True)
def sin_auditoria():
    with patch.object(viaje_service, "registrar_evento"):
        yield


def test_borrar_un_viaje_suelto(base):
    base["viajes"] = [_viaje()]
    base["cargas_combustible"] = [{"id": "carga-1"}]

    with patch.object(viaje_service, "_liberar_unidad") as liberar:
        r = viaje_service.eliminar_viaje("via-1", usuario_id="usr-1")

    assert base["borrados"]["viajes"] == ["via-1"]
    assert r["cargas_combustible_eliminadas"] == 1
    liberar.assert_any_call("cam-1")


def test_se_borra_el_par_ida_y_vuelta(base):
    """Ida y vuelta son un mismo trabajo: pedir una borra las dos."""
    base["viajes"] = [_viaje("via-ida", vuelta="via-vuelta"), _viaje("via-vuelta")]

    with patch.object(viaje_service, "_liberar_unidad"):
        r = viaje_service.eliminar_viaje("via-ida", usuario_id="usr-1")

    assert sorted(base["borrados"]["viajes"]) == ["via-ida", "via-vuelta"]
    assert r["eliminados"] == 2


def test_borrar_la_vuelta_tambien_se_lleva_la_ida(base):
    """Puede llegar el id de cualquiera de los dos."""
    base["viajes"] = [_viaje("via-ida", vuelta="via-vuelta"), _viaje("via-vuelta")]

    with patch.object(viaje_service, "_liberar_unidad"):
        viaje_service.eliminar_viaje("via-vuelta", usuario_id="usr-1")

    assert sorted(base["borrados"]["viajes"]) == ["via-ida", "via-vuelta"]


def test_la_referencia_a_la_vuelta_se_suelta_antes_de_borrar(base):
    """Si no, la clave foránea de la ida impide borrar la vuelta."""
    base["viajes"] = [_viaje("via-ida", vuelta="via-vuelta"), _viaje("via-vuelta")]

    with patch.object(viaje_service, "_liberar_unidad"):
        viaje_service.eliminar_viaje("via-ida", usuario_id="usr-1")

    assert ("viajes", {"viaje_vuelta_id": None}, {"id": ["via-ida", "via-vuelta"]}) in base["updates"]


def test_un_viaje_en_curso_libera_al_chofer_y_al_camion(base):
    """Se permite borrarlo, pero las unidades no pueden quedar reservadas sin viaje."""
    base["viajes"] = [_viaje(estado="en_curso")]

    with patch.object(viaje_service, "_liberar_unidad") as liberar:
        viaje_service.eliminar_viaje("via-1", usuario_id="usr-1")

    liberados = [u for (t, payload, f) in base["updates"] if t == "choferes" for u in [f.get("id")]]
    assert "cho-1" in liberados
    liberar.assert_any_call("cam-1")


def test_las_unidades_se_liberan_despues_de_borrar(base):
    """Al revés, el chequeo de 'tomada por otro viaje activo' vería al que estamos borrando."""
    base["viajes"] = [_viaje(estado="pendiente")]
    orden = []

    def liberar(_):
        orden.append("liberar")

    with patch.object(viaje_service, "_liberar_unidad", side_effect=liberar):
        viaje_service.eliminar_viaje("via-1", usuario_id="usr-1")

    assert base["borrados"]["viajes"] == ["via-1"]
    assert orden == ["liberar", "liberar"]


def test_un_viaje_que_no_existe_no_rompe_nada(base):
    base["viajes"] = []

    with pytest.raises(NotFoundError):
        viaje_service.eliminar_viaje("via-fantasma", usuario_id="usr-1")

    assert "viajes" not in base["borrados"]


def test_la_multa_se_desvincula_pero_no_se_borra(base):
    """Una multa es del camión y del chofer: tiene valor más allá del viaje."""
    base["viajes"] = [_viaje()]

    with patch.object(viaje_service, "_liberar_unidad"):
        r = viaje_service.eliminar_viaje("via-1", usuario_id="usr-1")

    assert ("multas", {"viaje_id": None}, {"viaje_id": ["via-1"]}) in base["updates"]
    assert "multas" not in base["borrados"]
    assert "multas_desvinculadas" in r


def test_la_cadena_de_vueltas_se_borra_entera(base):
    """Una vuelta puede tener su propia vuelta; ninguna puede quedar suelta."""
    base["viajes"] = [
        _viaje("via-1", vuelta="via-2"),
        _viaje("via-2", vuelta="via-3"),
        _viaje("via-3"),
    ]

    with patch.object(viaje_service, "_liberar_unidad"):
        r = viaje_service.eliminar_viaje("via-1", usuario_id="usr-1")

    assert sorted(base["borrados"]["viajes"]) == ["via-1", "via-2", "via-3"]
    assert r["eliminados"] == 3


def test_el_chofer_con_otro_viaje_activo_no_se_libera(base):
    """Liberarlo lo dejaría 'disponible' estando de viaje en otro lado."""
    base["viajes"] = [_viaje()]

    with patch.object(viaje_service, "_liberar_unidad"), patch.object(
        viaje_service, "_liberar_chofer"
    ) as liberar_chofer:
        viaje_service.eliminar_viaje("via-1", usuario_id="usr-1")

    # El servicio delega en _liberar_chofer, que es quien mira si le queda otro viaje.
    liberar_chofer.assert_called_once_with("cho-1")
