from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import BadRequestError, NotFoundError
from app.database import supabase
from app.services import telemetria_service

GENERADO_EN = "2026-08-25T11:00:00-03:00"


def _snapshot(*vehiculos: dict) -> dict:
    return {"generatedAt": GENERADO_EN, "vehicles": list(vehiculos)}


def _vehiculo_gps(patente: str, reportado_en: str = "2026-08-25T10:45:00-03:00", **extra) -> dict:
    return {
        "licensePlate": patente,
        "vehicleDescription": "Unidad de prueba",
        "position": {
            "timestamp": reportado_en,
            "latitude": -33.73,
            "longitude": -61.98,
            "speedKph": 62.5,
            "headingDegrees": 180,
        },
        "driver": {"name": extra.get("chofer_gps")},
        "telemetry": {"ignitionOn": True, "workSignalOn": None, "temperatureSensor": 0.0},
    }


def _camion(patente: str, camion_id: str = "cam-1", **extra) -> dict:
    return {
        "id": camion_id,
        "patente": patente,
        "marca": "SCANIA",
        "modelo": "R450",
        "tipo": "CHASIS",
        "empresa_id": "emp-1",
        "estado": "viajando",
        "activo": True,
        **extra,
    }


def _viaje(camion_id: str = "cam-1", estado: str = "en_curso") -> dict:
    return {
        "id": "via-1",
        "origen": "ROSARIO",
        "destino": "BAHIA BLANCA",
        "cliente": "CARGILL",
        "carga": "SOJA",
        "tarifa": 150000.0,
        "fecha_inicio": "2026-08-25T06:00:00-03:00",
        "estado": estado,
        "chofer_id": "cho-1",
        "camion_id": camion_id,
        "camion_id_2": None,
    }


@pytest.fixture
def base_de_datos():
    """Reemplaza supabase.table por un despachador que devuelve datos por tabla."""
    datos: dict[str, list] = {"camiones": [], "viajes": [], "choferes": [], "empresas": []}

    def tabla(nombre: str):
        query = MagicMock()
        for metodo in ("select", "eq", "in_", "order"):
            getattr(query, metodo).return_value = query
        query.execute.return_value = MagicMock(data=datos[nombre], count=len(datos[nombre]))
        return query

    supabase.table = MagicMock(side_effect=tabla)
    return datos


def _listar(snapshot: dict, **filtros) -> dict:
    with patch.object(telemetria_service.gc_client, "obtener_snapshot", return_value=snapshot):
        return telemetria_service.listar_flota(**filtros)


def test_camion_con_gps_y_viaje_activo_queda_en_el_mapa(base_de_datos):
    base_de_datos["camiones"] = [_camion("AE195MX")]
    base_de_datos["viajes"] = [_viaje()]
    base_de_datos["choferes"] = [{"id": "cho-1", "nombre_completo": "JUAN PEREZ"}]
    base_de_datos["empresas"] = [{"id": "emp-1", "nombre": "AIBAR SRL"}]

    resultado = _listar(_snapshot(_vehiculo_gps("AE195MX")))

    unidad = resultado["unidades"][0]
    assert unidad["categoria"] == "en_mapa"
    assert unidad["empresa_nombre"] == "AIBAR SRL"
    assert unidad["posicion"]["velocidad_kph"] == 62.5
    assert unidad["viaje"]["destino"] == "BAHIA BLANCA"
    assert unidad["viaje"]["chofer_nombre"] == "JUAN PEREZ"
    assert resultado["resumen"] == {
        "en_mapa": 1,
        "sin_gps": 0,
        "dadas_de_baja": 0,
        "no_registradas": 0,
        "en_viaje": 1,
    }


def test_camion_sin_reporte_del_gps_se_informa_como_sin_gps(base_de_datos):
    base_de_datos["camiones"] = [_camion("AB155BS")]

    unidad = _listar(_snapshot())["unidades"][0]

    assert unidad["categoria"] == "sin_gps"
    assert "posicion" not in unidad


def test_unidad_reportada_que_no_esta_en_la_flota_propia(base_de_datos):
    unidades = _listar(_snapshot(_vehiculo_gps("AE538LR")))["unidades"]

    assert [u["categoria"] for u in unidades] == ["no_registrada"]
    assert unidades[0]["patente"] == "AE538LR"


def test_la_patente_con_espacios_igual_matchea(base_de_datos):
    """En la base hay patentes cargadas con espacios sobrantes; deben cruzar igual."""
    base_de_datos["camiones"] = [_camion("AG949LF ")]

    unidad = _listar(_snapshot(_vehiculo_gps("AG949LF")))["unidades"][0]

    assert unidad["categoria"] == "en_mapa"


def test_viaje_pendiente_tambien_cuenta_como_activo(base_de_datos):
    """El chofer puede haber salido antes de que el empleado marque el viaje en curso."""
    base_de_datos["camiones"] = [_camion("AE195MX")]
    base_de_datos["viajes"] = [_viaje(estado="pendiente")]

    unidad = _listar(_snapshot(_vehiculo_gps("AE195MX")))["unidades"][0]

    assert unidad["viaje"]["estado"] == "pendiente"


def test_solo_en_viaje_descarta_las_unidades_libres(base_de_datos):
    base_de_datos["camiones"] = [_camion("AE195MX"), _camion("AB155BS", camion_id="cam-2")]
    base_de_datos["viajes"] = [_viaje()]

    resultado = _listar(_snapshot(_vehiculo_gps("AE195MX")), solo_en_viaje=True)

    assert [u["patente"] for u in resultado["unidades"]] == ["AE195MX"]


def test_solo_ubicadas_descarta_las_que_no_tienen_posicion(base_de_datos):
    base_de_datos["camiones"] = [_camion("AE195MX"), _camion("AB155BS", camion_id="cam-2")]

    resultado = _listar(_snapshot(_vehiculo_gps("AE195MX")), solo_ubicadas=True)

    assert [u["categoria"] for u in resultado["unidades"]] == ["en_mapa"]


def test_la_busqueda_por_patente_ignora_el_formato(base_de_datos):
    base_de_datos["camiones"] = [_camion("AE195MX"), _camion("AB155BS", camion_id="cam-2")]

    resultado = _listar(_snapshot(), busqueda="ae195 mx")

    assert [u["patente"] for u in resultado["unidades"]] == ["AE195MX"]


def test_antiguedad_del_reporte_se_calcula_contra_el_snapshot(base_de_datos):
    base_de_datos["camiones"] = [_camion("AE195MX")]

    unidad = _listar(_snapshot(_vehiculo_gps("AE195MX", "2026-08-25T10:45:00-03:00")))["unidades"][0]

    assert unidad["posicion"]["minutos_desde_reporte"] == 15


def test_filtro_por_empresa(base_de_datos):
    base_de_datos["camiones"] = [
        _camion("AE195MX"),
        _camion("AB155BS", camion_id="cam-2", empresa_id="emp-2"),
    ]

    resultado = _listar(_snapshot(), empresa_id="emp-1")

    assert [u["patente"] for u in resultado["unidades"]] == ["AE195MX"]


def test_camion_dado_de_baja_con_gps_no_se_confunde_con_una_unidad_ajena(base_de_datos):
    """El equipo puede seguir reportando después de la baja; sigue siendo un camión propio."""
    base_de_datos["camiones"] = [_camion("AI283WR", activo=False)]

    unidad = _listar(_snapshot(_vehiculo_gps("AI283WR")))["unidades"][0]

    assert unidad["categoria"] == "dada_de_baja"
    assert unidad["camion_id"] == "cam-1"
    assert unidad["posicion"]["latitud"] == -33.73


def test_camion_dado_de_baja_sin_gps_no_aparece(base_de_datos):
    base_de_datos["camiones"] = [_camion("EVJ393", activo=False)]

    assert _listar(_snapshot())["unidades"] == []


def _viaje_fila(**extra) -> dict:
    return {
        "id": "via-1",
        "estado": "finalizado",
        "camion_id": "cam-1",
        "camion_id_2": None,
        "fecha_inicio": "2026-08-24T19:00:00-03:00",
        "fecha_fin": "2026-08-25T14:00:00-03:00",
        **extra,
    }


def _recorrido_crudo() -> dict:
    return {
        "Summary": {"DistanceKm": 615.111, "MaxSpeedKmh": 88},
        "Positions": [
            {"DateAt": "24/08/2026 18:00:00", "Lat": "-33.1 ", "Lon": "-59.3", "Speed": "0", "SpeedLimit": "80"},
            {"DateAt": "24/08/2026 20:30:00", "Lat": "-33.14817", "Lon": "-59.3039", "Speed": "62", "SpeedLimit": "80"},
            {"DateAt": "25/08/2026 23:00:00", "Lat": "-33.0", "Lon": "-58.5", "Speed": "10", "SpeedLimit": "80"},
        ],
        "Stops": [
            {"StartAt": "24/08/2026 21:00:00", "EndAt": "24/08/2026 21:30:00",
             "Lat": "-33.14 ", "Lon": "-59.30 ", "Duration": "00:30:00 hs"}
        ],
    }


def test_el_recorrido_se_recorta_a_la_ventana_del_viaje(base_de_datos):
    """El proveedor solo acepta días completos: lo de antes de salir y después de llegar sobra."""
    base_de_datos["viajes"] = [_viaje_fila()]
    base_de_datos["camiones"] = [_camion("AE729EO")]

    with patch.object(telemetria_service.gc_client, "obtener_vehiculos",
                      return_value=[{"LicensePlate": "AE729EO", "VehicleId": "_07558"}]), \
         patch.object(telemetria_service.gc_client, "obtener_recorrido",
                      return_value=_recorrido_crudo()):
        r = telemetria_service.obtener_recorrido_de_viaje("via-1")

    assert [p["velocidad_kph"] for p in r["puntos"]] == [62.0]
    assert r["puntos"][0]["latitud"] == -33.14817
    assert r["recortado"] is True
    assert r["en_camino"] is False
    assert r["distancia_km"] == 615.111
    assert len(r["detenciones"]) == 1


def test_un_viaje_en_curso_con_la_unidad_rodando_marca_en_camino(base_de_datos):
    """El último punto es dónde va, no dónde llegó."""
    base_de_datos["viajes"] = [_viaje_fila(estado="en_curso", fecha_fin=None)]
    base_de_datos["camiones"] = [_camion("AE729EO")]
    rodando = _vehiculo_gps("AE729EO")
    rodando["position"]["speedKph"] = 72.0

    with patch.object(telemetria_service.gc_client, "obtener_vehiculos",
                      return_value=[{"LicensePlate": "AE729EO", "VehicleId": "_07558"}]), \
         patch.object(telemetria_service.gc_client, "obtener_recorrido",
                      return_value=_recorrido_crudo()), \
         patch.object(telemetria_service.gc_client, "obtener_snapshot",
                      return_value=_snapshot(rodando)):
        r = telemetria_service.obtener_recorrido_de_viaje("via-1")

    assert r["en_camino"] is True


def test_un_viaje_con_fechas_al_reves_avisa_en_vez_de_fallar_contra_el_proveedor(base_de_datos):
    """Hay viajes cargados con la fecha de fin anterior al inicio; el proveedor devuelve 400."""
    base_de_datos["viajes"] = [_viaje_fila(fecha_fin="2026-08-03T19:46:00-03:00")]

    with pytest.raises(BadRequestError, match="anterior a la de inicio"):
        telemetria_service.obtener_recorrido_de_viaje("via-1")


def test_una_unidad_que_el_proveedor_no_conoce_da_not_found(base_de_datos):
    base_de_datos["viajes"] = [_viaje_fila()]
    base_de_datos["camiones"] = [_camion("EVJ393")]

    with patch.object(telemetria_service.gc_client, "obtener_vehiculos", return_value=[]):
        with pytest.raises(NotFoundError):
            telemetria_service.obtener_recorrido_de_viaje("via-1")
