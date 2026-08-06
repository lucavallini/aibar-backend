from supabase import create_client, Client
from app.config import settings
import math
import threading
import time
import httpx
import httpcore
import postgrest._sync.request_builder as _rb

_ERROES_TRANSIENTES = (
    httpx.RemoteProtocolError,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    httpcore.RemoteProtocolError,
)

_execute_original = _rb.SyncQueryRequestBuilder.execute


def _execute_con_reintentos(self, *args, **kwargs):
    for intento in range(3):
        try:
            return _execute_original(self, *args, **kwargs)
        except _ERROES_TRANSIENTES:
            if intento == 2:
                raise
            time.sleep(0.25 * (intento + 1))


_rb.SyncQueryRequestBuilder.execute = _execute_con_reintentos

_local = threading.local()


def get_supabase() -> Client:
    cliente = getattr(_local, "cliente", None)
    if cliente is None:
        cliente = create_client(settings.supabase_url, settings.supabase_service_key)
        _local.cliente = cliente
    return cliente


class _ProxySupabase:
    def __getattr__(self, nombre):
        return getattr(get_supabase(), nombre)

    def __setattr__(self, nombre, valor):
        setattr(get_supabase(), nombre, valor)


supabase: Client = _ProxySupabase()


def armar_respuesta_paginada(query, pagina: int, tamano_pagina: int) -> dict:
    desde = (pagina - 1) * tamano_pagina
    hasta = desde + tamano_pagina - 1

    resultado = query.range(desde, hasta).execute()
    total = resultado.count or 0
    total_paginas = math.ceil(total / tamano_pagina) if total > 0 else 1

    return {
        "items": resultado.data,
        "total": total,
        "pagina": pagina,
        "tamano_pagina": tamano_pagina,
        "total_paginas": total_paginas,
    }
