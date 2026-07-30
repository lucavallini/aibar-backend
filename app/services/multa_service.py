from app.database import supabase
from app.models.multa import MultaCreate
from app.core.exceptions import NotFoundError, InternalError
from uuid import UUID
from app.database import supabase, armar_respuesta_paginada
from app.services.auditoria_service import registrar_evento
from app.utils.fields import upper_fields

def listar_multas(camion_id: str = None, chofer_id: str = None, pagina: int = 1, tamano_pagina: int = 20) -> dict:
    query = supabase.table("multas").select("*", count="exact")

    if camion_id:
        query = query.eq("camion_id", camion_id)

    if chofer_id:
        query = query.eq("chofer_id", chofer_id)

    query = query.order("fecha", desc=True)

    return armar_respuesta_paginada(query, pagina, tamano_pagina)


def crear_multa(datos: MultaCreate, registrado_por: UUID) -> dict:
    camion = supabase.table("camiones").select("id").eq("id", str(datos.camion_id)).execute()
    if not camion.data:
        raise NotFoundError("El camión indicado no existe")

    if datos.chofer_id:
        chofer = supabase.table("choferes").select("id").eq("id", str(datos.chofer_id)).execute()
        if not chofer.data:
            raise NotFoundError("El chofer indicado no existe")

    if datos.viaje_id:
        viaje = supabase.table("viajes").select("id").eq("id", str(datos.viaje_id)).execute()
        if not viaje.data:
            raise NotFoundError("El viaje indicado no existe")

    nueva_multa = datos.model_dump(mode="json", exclude_unset=True)
    upper_fields(nueva_multa, "motivo")
    nueva_multa["registrado_por"] = str(registrado_por)

    resultado = supabase.table("multas").insert(nueva_multa).execute()

    if not resultado.data:
        raise InternalError("No se pudo registrar la multa")

    multa_creada = resultado.data[0]

    registrar_evento(
        usuario_id=registrado_por,
        tipo_accion="alta",
        entidad="multa",
        entidad_id=multa_creada["id"],
        detalle=f"Multa registrada: {datos.motivo}",
    )

    return multa_creada

