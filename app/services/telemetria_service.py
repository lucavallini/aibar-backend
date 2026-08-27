"""Cruce entre el rastreo satelital de la API GC y la flota propia.

El frontend recibe las unidades ya clasificadas, filtradas y con los nombres resueltos:
acá se resuelve todo lo que el mapa necesita mostrar.
"""

from datetime import datetime, timedelta, timezone

from app.core import gc_client
from app.core.exceptions import BadRequestError, NotFoundError
from app.database import supabase
from app.utils.fields import normalizar_patente

ESTADOS_VIAJE_ACTIVO = ["pendiente", "en_curso"]
CATEGORIAS_UBICADAS = ("en_mapa", "dada_de_baja", "no_registrada")


def _indexar_por_patente(registros: list[dict], campo: str) -> dict[str, dict]:
    return {normalizar_patente(r.get(campo)): r for r in registros if normalizar_patente(r.get(campo))}


def _minutos_transcurridos(desde: str | None, hasta: datetime) -> int:
    if not desde:
        return 0
    return max(int((hasta - datetime.fromisoformat(desde)).total_seconds() // 60), 0)


def _armar_posicion(unidad_gps: dict, generado_en: datetime) -> dict:
    posicion = unidad_gps.get("position") or {}
    return {
        "latitud": posicion.get("latitude"),
        "longitud": posicion.get("longitude"),
        "velocidad_kph": posicion.get("speedKph") or 0.0,
        "rumbo_grados": posicion.get("headingDegrees") or 0,
        "reportado_en": posicion.get("timestamp"),
        "minutos_desde_reporte": _minutos_transcurridos(posicion.get("timestamp"), generado_en),
    }


def _armar_telemetria(unidad_gps: dict) -> dict:
    telemetria = unidad_gps.get("telemetry") or {}
    return {
        "contacto_encendido": bool(telemetria.get("ignitionOn")),
        "senal_trabajo": telemetria.get("workSignalOn"),
        "temperatura": telemetria.get("temperatureSensor"),
    }


def _datos_de_rastreo(unidad_gps: dict, generado_en: datetime) -> dict:
    """El odómetro y la distancia a base del proveedor no son confiables, así que no se exponen."""
    conductor = (unidad_gps.get("driver") or {}).get("name")
    return {
        "posicion": _armar_posicion(unidad_gps, generado_en),
        "telemetria": _armar_telemetria(unidad_gps),
        "descripcion_gps": unidad_gps.get("vehicleDescription"),
        "chofer_gps": conductor,
    }


def _viajes_activos_por_camion() -> dict[str, dict]:
    """Un viaje pendiente o en curso indexado por cada camión que tenga asignado."""
    viajes = (
        supabase.table("viajes")
        .select("id,origen,destino,cliente,carga,tarifa,fecha_inicio,estado,chofer_id,camion_id,camion_id_2")
        .in_("estado", ESTADOS_VIAJE_ACTIVO)
        .order("fecha_inicio")
        .execute()
    ).data or []

    nombres = _nombres_de_choferes([v["chofer_id"] for v in viajes if v.get("chofer_id")])

    por_camion: dict[str, dict] = {}
    for viaje in viajes:
        viaje["chofer_nombre"] = nombres.get(str(viaje.get("chofer_id")))
        for campo in ("camion_id", "camion_id_2"):
            if viaje.get(campo):
                por_camion.setdefault(str(viaje[campo]), viaje)
    return por_camion


def _nombres_de_choferes(chofer_ids: list) -> dict[str, str]:
    if not chofer_ids:
        return {}
    choferes = (
        supabase.table("choferes")
        .select("id,nombre_completo")
        .in_("id", [str(c) for c in set(chofer_ids)])
        .execute()
    ).data or []
    return {str(c["id"]): c.get("nombre_completo") for c in choferes}


def _nombres_de_empresas() -> dict[str, str]:
    empresas = (supabase.table("empresas").select("id,nombre").execute()).data or []
    return {str(e["id"]): e.get("nombre") for e in empresas}


def _datos_propios(camion: dict, viajes: dict, empresas: dict) -> dict:
    return {
        "camion_id": camion["id"],
        "patente": camion["patente"],
        "marca": camion.get("marca"),
        "modelo": camion.get("modelo"),
        "tipo": camion.get("tipo"),
        "empresa_id": camion.get("empresa_id"),
        "empresa_nombre": empresas.get(str(camion.get("empresa_id"))),
        "estado": camion.get("estado", "disponible"),
        "viaje": viajes.get(str(camion["id"])),
    }


def _coincide(unidad: dict, busqueda: str | None, empresa_id: str | None, solo_en_viaje: bool) -> bool:
    if busqueda and normalizar_patente(busqueda) not in normalizar_patente(unidad["patente"]):
        return False
    if empresa_id and str(unidad.get("empresa_id")) != empresa_id:
        return False
    if solo_en_viaje and not unidad.get("viaje"):
        return False
    return True


def listar_flota(
    busqueda: str = None,
    empresa_id: str = None,
    solo_en_viaje: bool = False,
    solo_ubicadas: bool = False,
) -> dict:
    snapshot = gc_client.obtener_snapshot() or {}
    generado_en = datetime.fromisoformat(snapshot["generatedAt"])

    gps = _indexar_por_patente(snapshot.get("vehicles") or [], "licensePlate")

    # Se traen también los dados de baja: si el equipo sigue reportando hay que reconocerlos
    # como propios en lugar de tratarlos como una unidad ajena.
    camiones = (supabase.table("camiones").select("*").order("patente").execute()).data or []

    viajes = _viajes_activos_por_camion()
    empresas = _nombres_de_empresas()

    unidades: list[dict] = []
    patentes_propias = set()

    for camion in camiones:
        patente = normalizar_patente(camion.get("patente"))
        patentes_propias.add(patente)
        unidad_gps = gps.get(patente)

        if not camion.get("activo"):
            # Una baja sin rastreo ya no es parte de la flota: no aporta nada al mapa.
            if unidad_gps:
                unidades.append(
                    {
                        **_datos_propios(camion, viajes, empresas),
                        **_datos_de_rastreo(unidad_gps, generado_en),
                        "categoria": "dada_de_baja",
                    }
                )
            continue

        unidad = _datos_propios(camion, viajes, empresas)
        if unidad_gps:
            unidades.append({**unidad, **_datos_de_rastreo(unidad_gps, generado_en), "categoria": "en_mapa"})
        else:
            unidades.append({**unidad, "categoria": "sin_gps"})

    for patente, unidad_gps in gps.items():
        if patente not in patentes_propias:
            unidades.append(
                {
                    "patente": unidad_gps.get("licensePlate"),
                    **_datos_de_rastreo(unidad_gps, generado_en),
                    "categoria": "no_registrada",
                }
            )

    if solo_ubicadas:
        unidades = [u for u in unidades if u["categoria"] in CATEGORIAS_UBICADAS]
    unidades = [u for u in unidades if _coincide(u, busqueda, empresa_id, solo_en_viaje)]

    return {
        "generado_en": generado_en,
        "resumen": {
            "en_mapa": sum(1 for u in unidades if u["categoria"] == "en_mapa"),
            "sin_gps": sum(1 for u in unidades if u["categoria"] == "sin_gps"),
            "dadas_de_baja": sum(1 for u in unidades if u["categoria"] == "dada_de_baja"),
            "no_registradas": sum(1 for u in unidades if u["categoria"] == "no_registrada"),
            "en_viaje": sum(1 for u in unidades if u.get("viaje")),
        },
        "unidades": unidades,
    }


# El proveedor devuelve las fechas del recorrido sin zona horaria; son hora local argentina.
ZONA_ARGENTINA = timezone(timedelta(hours=-3))
FORMATO_FECHA_HORA = "%d/%m/%Y %H:%M:%S"
FORMATO_FECHA = "%d/%m/%Y"
MAX_DIAS_RECORRIDO = 31


def _a_decimal(valor) -> float:
    """El proveedor manda las coordenadas y velocidades como texto, a veces con espacios."""
    try:
        return float(str(valor).strip())
    except (TypeError, ValueError):
        return 0.0


def _a_momento(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        return datetime.strptime(valor.strip(), FORMATO_FECHA_HORA).replace(tzinfo=ZONA_ARGENTINA)
    except ValueError:
        return None


def _punto(posicion: dict) -> dict | None:
    momento = _a_momento(posicion.get("DateAt"))
    if momento is None:
        return None
    limite = int(_a_decimal(posicion.get("SpeedLimit"))) or None
    return {
        "latitud": _a_decimal(posicion.get("Lat")),
        "longitud": _a_decimal(posicion.get("Lon")),
        "velocidad_kph": _a_decimal(posicion.get("Speed")),
        "limite_kph": limite,
        "momento": momento,
    }


def _detencion(parada: dict) -> dict | None:
    inicio = _a_momento(parada.get("StartAt"))
    if inicio is None:
        return None
    return {
        "latitud": _a_decimal(parada.get("Lat")),
        "longitud": _a_decimal(parada.get("Lon")),
        "inicio": inicio,
        "fin": _a_momento(parada.get("EndAt")),
        "duracion": (parada.get("Duration") or "").strip() or None,
    }


def _id_vehiculo(patente: str) -> str:
    """Traduce la patente propia al identificador que usa el proveedor."""
    padron = {
        normalizar_patente(v.get("LicensePlate")): v.get("VehicleId")
        for v in gc_client.obtener_vehiculos() or []
    }
    id_vehiculo = padron.get(normalizar_patente(patente))
    if not id_vehiculo:
        raise NotFoundError("La unidad no está dada de alta en el servicio de rastreo satelital")
    return id_vehiculo


def _camion_del_viaje(viaje: dict) -> dict:
    camion_id = viaje.get("camion_id") or viaje.get("camion_id_2")
    if not camion_id:
        raise BadRequestError("El viaje no tiene ninguna unidad asignada")

    camion = supabase.table("camiones").select("patente").eq("id", str(camion_id)).execute().data
    if not camion:
        raise NotFoundError("El camión del viaje no existe")
    return camion[0]


def _viene_en_camino(patente: str) -> bool:
    """Contacto puesto y en movimiento: el recorrido todavía no terminó."""
    unidad = _indexar_por_patente(
        (gc_client.obtener_snapshot() or {}).get("vehicles") or [], "licensePlate"
    ).get(normalizar_patente(patente))
    if not unidad:
        return False
    telemetria = unidad.get("telemetry") or {}
    posicion = unidad.get("position") or {}
    return bool(telemetria.get("ignitionOn")) and (posicion.get("speedKph") or 0) > 0


def obtener_recorrido_de_viaje(viaje_id: str) -> dict:
    """Traza del viaje, recortada a su ventana real.

    El proveedor solo acepta días completos, así que devuelve también lo que la unidad hizo
    antes de salir y después de llegar: eso se descarta acá.
    """
    viaje = supabase.table("viajes").select("*").eq("id", viaje_id).execute().data
    if not viaje:
        raise NotFoundError("Viaje no encontrado")
    viaje = viaje[0]

    desde = datetime.fromisoformat(viaje["fecha_inicio"])
    hasta = datetime.fromisoformat(viaje["fecha_fin"]) if viaje.get("fecha_fin") else datetime.now(ZONA_ARGENTINA)

    if hasta < desde:
        raise BadRequestError(
            "El viaje tiene la fecha de fin anterior a la de inicio; corregilas para ver el recorrido"
        )

    if (hasta.date() - desde.date()).days > MAX_DIAS_RECORRIDO:
        raise BadRequestError(f"El viaje supera los {MAX_DIAS_RECORRIDO} días; el recorrido es demasiado extenso")

    patente = _camion_del_viaje(viaje)["patente"]
    crudo = gc_client.obtener_recorrido(
        _id_vehiculo(patente),
        desde.strftime(FORMATO_FECHA),
        hasta.strftime(FORMATO_FECHA),
        incluir_posiciones=True,
    ) or {}

    puntos = [p for p in map(_punto, crudo.get("Positions") or []) if p]
    detenciones = [d for d in map(_detencion, crudo.get("Stops") or []) if d]

    en_ventana = [p for p in puntos if desde <= p["momento"] <= hasta]
    resumen = crudo.get("Summary") or {}

    return {
        "viaje_id": viaje_id,
        "patente": patente,
        "distancia_km": _a_decimal(resumen.get("DistanceKm")),
        "velocidad_maxima_kph": int(_a_decimal(resumen.get("MaxSpeedKmh"))),
        "puntos": en_ventana,
        "detenciones": [d for d in detenciones if desde <= d["inicio"] <= hasta],
        "recortado": len(en_ventana) < len(puntos),
        "en_camino": viaje["estado"] in ESTADOS_VIAJE_ACTIVO and _viene_en_camino(patente),
    }
