"""Cliente HTTP de la API GC (TCSA).

Único punto del sistema que conoce las credenciales, el formato de autenticación y los
códigos de error del proveedor. Los services consumen las funciones públicas de acá y
nunca arman requests por su cuenta.
"""

import base64
import json
import threading
import time

import httpx

from app.config import settings
from app.core.exceptions import BadRequestError, ForbiddenError, InternalError
from app.core.logging import logger

TIMEOUT_SEGUNDOS = 30.0
MARGEN_RENOVACION_SEGUNDOS = 60
TTL_SNAPSHOT_SEGUNDOS = 25
TTL_VEHICULOS_SEGUNDOS = 3600

_lock = threading.Lock()
_token: str | None = None
_token_expira_en: float = 0.0
_cache: dict[str, tuple[float, object]] = {}


def _pedir_token() -> tuple[str, int]:
    try:
        respuesta = httpx.post(
            f"{settings.gc_base_url.rstrip('/')}/api/ApiClientAuth/Token",
            json={
                "client_id": settings.gc_client_id,
                "client_secret": settings.gc_client_secret,
            },
            timeout=TIMEOUT_SEGUNDOS,
        )
    except httpx.HTTPError as exc:
        raise InternalError("No se pudo contactar al servicio de rastreo satelital") from exc

    if respuesta.status_code != 200:
        logger.error("Fallo la autenticación contra la API GC: %s", respuesta.status_code)
        raise InternalError("No se pudo autenticar contra el servicio de rastreo satelital")

    datos = respuesta.json()
    return datos["access_token"], int(datos.get("expires_in", 3600))


def _obtener_token() -> str:
    """Devuelve un token vigente, renovándolo antes de que venza."""
    global _token, _token_expira_en

    with _lock:
        if _token and time.monotonic() < _token_expira_en:
            return _token

        _token, expires_in = _pedir_token()
        _token_expira_en = time.monotonic() + max(expires_in - MARGEN_RENOVACION_SEGUNDOS, 0)
        return _token


def _consultar(path: str, params: dict | None = None) -> object:
    """GET autenticado contra la API GC, con los errores traducidos al dominio."""
    try:
        respuesta = httpx.get(
            f"{settings.gc_base_url.rstrip('/')}{path}",
            headers={"Authorization": f"Bearer {_obtener_token()}", "Accept": "application/json"},
            params=params,
            timeout=TIMEOUT_SEGUNDOS,
        )
    except httpx.HTTPError as exc:
        raise InternalError("No se pudo contactar al servicio de rastreo satelital") from exc

    if respuesta.status_code == 200:
        return respuesta.json()

    # El 401 del proveedor significa "esta unidad no es tuya", no "tu sesión venció".
    # Traducirlo a 401 nuestro desloguearía al usuario, así que se mapea a 403.
    if respuesta.status_code in (401, 403):
        raise ForbiddenError("La unidad consultada no está habilitada en el servicio de rastreo")

    if respuesta.status_code == 400:
        raise BadRequestError("Parámetros inválidos para el servicio de rastreo satelital")

    logger.error("Error %s de la API GC en %s", respuesta.status_code, path)
    raise InternalError("El servicio de rastreo satelital respondió con un error")


def _cachear(clave: str, ttl: int, obtener):
    ahora = time.monotonic()
    with _lock:
        vencimiento, valor = _cache.get(clave, (0.0, None))
        if ahora < vencimiento:
            return valor

    valor = obtener()
    with _lock:
        _cache[clave] = (time.monotonic() + ttl, valor)
    return valor


def obtener_snapshot() -> dict:
    """Última posición conocida de todas las unidades habilitadas para el cliente."""
    return _cachear(
        "snapshot",
        TTL_SNAPSHOT_SEGUNDOS,
        lambda: _consultar("/api/VehicleReport/GetFleetSnapshot"),
    )


def _id_cliente() -> str:
    """El identificador de flota que pide GetVehicles viaja dentro del propio token.

    Sin él el endpoint devuelve una lista vacía, y con un valor no numérico responde 500.
    """
    payload = _obtener_token().split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))["IdCustomer"]


def obtener_vehiculos() -> list[dict]:
    """Padrón de unidades con su VehicleId, que es lo que pide la consulta de recorridos."""
    return _cachear(
        "vehiculos",
        TTL_VEHICULOS_SEGUNDOS,
        lambda: _consultar("/api/VehicleMaster/GetVehicles", {"idFleet": _id_cliente()}),
    )


def obtener_recorrido(
    id_vehiculo: str,
    fecha_desde: str,
    fecha_hasta: str,
    minutos_detencion: int = 10,
    incluir_posiciones: bool = False,
) -> dict:
    """Recorrido histórico de una unidad. Las fechas van en formato dd/MM/yyyy."""
    return _consultar(
        "/api/Vehicle/GetVehicleTripFull",
        {
            "idVehicle": id_vehiculo,
            "dateFrom": fecha_desde,
            "dateTo": fecha_hasta,
            "stopMinutes": minutos_detencion,
            "includePositions": str(incluir_posiciones).lower(),
        },
    )


def limpiar_cache() -> None:
    """Usado por los tests y por el arranque; no forma parte del flujo normal."""
    global _token, _token_expira_en
    with _lock:
        _cache.clear()
        _token = None
        _token_expira_en = 0.0
