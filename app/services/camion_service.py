from fastapi import HTTPException
from app.database import supabase
from app.models.camion import CamionCreate, CamionUpdate
from app.database import supabase, armar_respuesta_paginada
from app.services.auditoria_service import registrar_evento
from uuid import UUID

def listar_camiones(activos_only: bool = True, busqueda: str = None, pagina: int = 1, tamano_pagina: int = 20) -> dict:
    query = supabase.table("camiones").select("*", count="exact")

    if activos_only:
        query = query.eq("activo", True)

    if busqueda:
        query = query.ilike("patente", f"%{busqueda}%")

    query = query.order("patente")

    return armar_respuesta_paginada(query, pagina, tamano_pagina)

def obtener_camion(camion_id: str) -> dict:
    resultado = supabase.table("camiones").select("*").eq("id", camion_id).execute()

    if not resultado.data:
        raise HTTPException(status_code=404, detail="Camión no encontrado")

    return resultado.data[0]

def crear_camion(datos: CamionCreate, usuario_id: UUID) -> dict:
    patente_existente = supabase.table("camiones").select("id").eq("patente", datos.patente).execute()

    if patente_existente.data:
        raise HTTPException(status_code=400, detail="Ya existe un camión con esa patente")

    nuevo_camion = datos.model_dump()

    resultado = supabase.table("camiones").insert(nuevo_camion).execute()

    if not resultado.data:
        raise HTTPException(status_code=500, detail="No se pudo crear el camión")

    camion_creado = resultado.data[0]

    registrar_evento(
        usuario_id=usuario_id,
        tipo_accion="alta",
        entidad="camion",
        entidad_id=camion_creado["id"],
        detalle=f"Camión creado: {datos.patente}",
    )

    return camion_creado


def actualizar_camion(camion_id: str, datos: CamionUpdate, usuario_id: UUID) -> dict:
    obtener_camion(camion_id)

    cambios = datos.model_dump(exclude_unset=True)

    if not cambios:
        raise HTTPException(status_code=400, detail="No se enviaron campos para actualizar")

    resultado = supabase.table("camiones").update(cambios).eq("id", camion_id).execute()
    camion_editado = resultado.data[0]

    registrar_evento(
        usuario_id=usuario_id,
        tipo_accion="edicion",
        entidad="camion",
        entidad_id=camion_id,
        detalle=f"Campos modificados: {', '.join(cambios.keys())}",
    )

    return camion_editado


def dar_de_baja_camion(camion_id: str, usuario_id: UUID) -> dict:
    obtener_camion(camion_id)

    resultado = supabase.table("camiones").update({"activo": False}).eq("id", camion_id).execute()

    registrar_evento(
        usuario_id=usuario_id,
        tipo_accion="baja",
        entidad="camion",
        entidad_id=camion_id,
    )

    return resultado.data[0]