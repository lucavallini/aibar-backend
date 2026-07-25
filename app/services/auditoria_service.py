from app.database import supabase
from uuid import UUID
from typing import Optional
from datetime import date, timedelta
from app.database import supabase, armar_respuesta_paginada

def listar_auditoria(usuario_id: str = None, entidad: str = None, dias: int = None, pagina: int = 1, tamano_pagina: int = 20) -> dict:
    query = supabase.table("auditoria").select("*", count="exact")

    if usuario_id:
        query = query.eq("usuario_id", usuario_id)

    if entidad:
        query = query.eq("entidad", entidad)

    if dias:
        desde = (date.today() - timedelta(days=dias)).isoformat()
        query = query.gte("fecha_hora", desde)

    query = query.order("fecha_hora", desc=True)

    return armar_respuesta_paginada(query, pagina, tamano_pagina)


def registrar_evento(
    usuario_id: UUID,
    tipo_accion: str,
    entidad: str,
    entidad_id: UUID,
    detalle: Optional[str] = None,
) -> None:
    evento = {
        "usuario_id": str(usuario_id),
        "tipo_accion": tipo_accion,
        "entidad": entidad,
        "entidad_id": str(entidad_id),
        "detalle": detalle,
    }
    supabase.table("auditoria").insert(evento).execute()

