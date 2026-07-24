from supabase import create_client, Client
from app.config import settings
import math


def get_supabase()-> Client:
    return create_client(settings.supabase_url, settings.supabase_service_key)

supabase: Client = get_supabase()


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