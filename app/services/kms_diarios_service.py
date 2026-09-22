"""Kilometraje diario por unidad, tomado del servicio de rastreo satelital.

El proveedor guarda alrededor de seis meses de recorridos y su odómetro es un parcial que
se reinicia cada medianoche local, así que el kilometraje acumulado hay que construirlo
del lado nuestro. Este módulo trae un día de una unidad, lo clasifica y lo persiste.
"""

from datetime import date, timedelta

from app.core import gc_client
from app.core.logging import logger
from app.database import supabase

FORMATO_FECHA = "%d/%m/%Y"

#: Lo que el proveedor conserva hacia atrás, medido contra su API.
DIAS_RETENCION_PROVEEDOR = 180

CON_MOVIMIENTO = "con_movimiento"
DETENIDO = "detenido"
SIN_DATOS = "sin_datos"


def clasificar_dia(crudo: dict) -> dict:
    """Traduce la respuesta de un día a kilómetros y a un estado.

    Un día sin kilómetros puede ser el camión quieto o el equipo apagado, y en la
    respuesta los dos llegan con distancia cero y sin tramos. Lo que los separa son los
    eventos y las detenciones: si el equipo estuvo vivo, algo reporta aunque no se mueva.
    Sin nada de eso no sabemos qué pasó, y eso no es lo mismo que cero kilómetros.
    """
    km = float((crudo.get("Summary") or {}).get("DistanceKm") or 0)
    tramos = len(crudo.get("Trips") or [])
    paradas = len(crudo.get("Stops") or [])
    eventos = len(crudo.get("Events") or [])

    if km > 0 or tramos:
        estado = CON_MOVIMIENTO
    elif paradas or eventos:
        estado = DETENIDO
    else:
        estado = SIN_DATOS

    return {
        "km": None if estado == SIN_DATOS else round(km, 2),
        "estado": estado,
        "tramos": tramos,
        "paradas": paradas,
        "eventos": eventos,
    }


def dias_del_rango(desde: date, hasta: date) -> list[date]:
    """Un día por consulta.

    Pedir un rango largo de una sola vez devuelve el total del período, no el desglose, y
    los tramos que cruzan la medianoche quedarían atribuidos a un día solo. Día por día el
    corte lo hace el proveedor con el mismo criterio con el que reinicia su odómetro.
    """
    return [desde + timedelta(days=n) for n in range((hasta - desde).days + 1)]


def dias_ya_guardados(patente: str, desde: date, hasta: date) -> set[date]:
    """Para poder reanudar el backfill donde se cortó sin volver a pedir lo mismo."""
    filas = (
        supabase.table("kms_diarios")
        .select("fecha")
        .eq("patente", patente)
        .gte("fecha", desde.isoformat())
        .lte("fecha", hasta.isoformat())
        .execute()
    ).data or []
    return {date.fromisoformat(f["fecha"]) for f in filas}


def guardar_dia(patente: str, dia: date, datos: dict) -> None:
    """Alta o actualización: la clave (patente, fecha) hace la operación repetible."""
    supabase.table("kms_diarios").upsert(
        {"patente": patente, "fecha": dia.isoformat(), **datos},
        on_conflict="patente,fecha",
    ).execute()


def traer_dia(id_vehiculo: str, dia: date) -> dict:
    """Un día de una unidad, ya clasificado. Las fallas de red no cortan el backfill."""
    texto = dia.strftime(FORMATO_FECHA)
    try:
        crudo = gc_client.obtener_recorrido(id_vehiculo, texto, texto) or {}
    except Exception:
        logger.warning("No se pudo traer %s del %s", id_vehiculo, texto, exc_info=True)
        return {}
    return clasificar_dia(crudo)
