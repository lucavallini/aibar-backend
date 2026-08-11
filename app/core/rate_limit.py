import threading
import time
from collections import defaultdict

from app.core.exceptions import TooManyRequestsError

MAX_INTENTOS = 5
VENTANA_SEGUNDOS = 60

_lock = threading.Lock()
_intentos: dict[str, list[float]] = defaultdict(list)


def verificar_rate_limit(clave: str, max_intentos: int = MAX_INTENTOS, ventana_segundos: int = VENTANA_SEGUNDOS) -> None:
    """Limitador simple en memoria por clave (ej. IP). No distribuido entre procesos."""
    ahora = time.monotonic()
    with _lock:
        vigentes = [t for t in _intentos[clave] if ahora - t < ventana_segundos]
        if len(vigentes) >= max_intentos:
            _intentos[clave] = vigentes
            raise TooManyRequestsError(
                "Demasiados intentos. Esperá un momento antes de volver a intentar."
            )
        vigentes.append(ahora)
        _intentos[clave] = vigentes
