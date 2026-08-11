from app.database import supabase, armar_respuesta_paginada
from app.models.combustible import CargaCombustibleCreate
from app.core.exceptions import NotFoundError, InternalError
from uuid import UUID
from datetime import date, timedelta
from app.services.auditoria_service import registrar_evento

def listar_cargas_combustible(
    camion_id: str = None,
    chofer_id: str = None,
    fecha_desde: str = None,
    fecha_hasta: str = None,
    pagina: int = 1,
    tamano_pagina: int = 20,
    solo_ultimos_30_dias: bool = True,
) -> dict:
    query = supabase.table("cargas_combustible").select("*", count="exact")

    if camion_id:
        query = query.eq("camion_id", camion_id)

    if chofer_id:
        chofer = supabase.table("choferes").select("camion_id").eq("id", chofer_id).execute()
        if chofer.data and chofer.data[0].get("camion_id"):
            query = query.eq("camion_id", chofer.data[0]["camion_id"])
        else:
            query = query.eq("id", "00000000-0000-0000-0000-000000000000")

    if fecha_desde:
        query = query.gte("fecha", fecha_desde)
    if fecha_hasta:
        query = query.lte("fecha", fecha_hasta)

    if solo_ultimos_30_dias and not fecha_desde and not fecha_hasta:
        hace_30_dias = (date.today() - timedelta(days=30)).isoformat()
        query = query.gte("fecha", hace_30_dias)

    query = query.order("fecha", desc=True)

    return armar_respuesta_paginada(query, pagina, tamano_pagina)

def crear_carga_combustible(datos: CargaCombustibleCreate, registrado_por: UUID) -> dict:
    camion = supabase.table("camiones").select("id").eq("id", str(datos.camion_id)).execute()
    if not camion.data:
        raise NotFoundError("El camión indicado no existe")

    if datos.viaje_id:
        viaje = supabase.table("viajes").select("id").eq("id", str(datos.viaje_id)).execute()
        if not viaje.data:
            raise NotFoundError("El viaje indicado no existe")

    nueva_carga = datos.model_dump(mode="json", exclude_unset=True)
    nueva_carga["registrado_por"] = str(registrado_por)

    resultado = supabase.table("cargas_combustible").insert(nueva_carga).execute()

    if not resultado.data:
        raise InternalError("No se pudo registrar la carga de combustible")

    carga_creada = resultado.data[0]

    registrar_evento(
        usuario_id=registrado_por,
        tipo_accion="alta",
        entidad="combustible",
        entidad_id=carga_creada["id"],
        detalle=f"{datos.litros} litros, ${datos.monto}",
    )

    return carga_creada




def calcular_gasto_total_camion(camion_id: str) -> dict:
    resultado = (
        supabase.table("cargas_combustible")
        .select("litros, monto")
        .eq("camion_id", camion_id)
        .execute()
    )

    total_litros = sum(c["litros"] for c in resultado.data)
    total_monto = sum(c["monto"] for c in resultado.data)

    return {
        "camion_id": camion_id,
        "total_litros": total_litros,
        "total_monto": total_monto,
        "cantidad_cargas": len(resultado.data),
    }