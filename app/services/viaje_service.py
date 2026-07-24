from fastapi import HTTPException
from app.database import supabase
from app.models.viaje import ViajeCreate, ViajeEditar, ViajeCancelar, ViajeFinalizar
from app.services.auditoria_service import registrar_evento
from uuid import UUID
from app.database import supabase, armar_respuesta_paginada

def listar_viajes(chofer_id: str = None, estado: str = None, pagina: int = 1, tamano_pagina: int = 20) -> dict:
    query = supabase.table("viajes").select("*", count="exact")

    if chofer_id:
        query = query.eq("chofer_id", chofer_id)

    if estado:
        query = query.eq("estado", estado)

    query = query.order("fecha_inicio", desc=True)

    return armar_respuesta_paginada(query, pagina, tamano_pagina)


def _obtener_viaje(viaje_id: str) -> dict:
    resultado = supabase.table("viajes").select("*").eq("id", viaje_id).execute()
    if not resultado.data:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")
    return resultado.data[0]


def crear_viaje(datos: ViajeCreate, asignado_por: UUID) -> dict:
    chofer_id_str = str(datos.chofer_id)

    # Optimistic locking: solo asigna si el chofer está "disponible" en este mismo instante.
    # Si otro empleado lo tomó un segundo antes, este UPDATE afecta 0 filas.
    reserva = (
        supabase.table("choferes")
        .update({"estado": "viajando"})
        .eq("id", chofer_id_str)
        .eq("estado", "disponible")
        .execute()
    )

    if not reserva.data:
        raise HTTPException(
            status_code=409,
            detail="El chofer ya no está disponible. Actualizá la pantalla e intentá de nuevo."
        )

    nuevo_viaje = datos.model_dump(mode="json")
    nuevo_viaje["asignado_por"] = str(asignado_por)

    resultado = supabase.table("viajes").insert(nuevo_viaje).execute()

    if not resultado.data:
        # Si por algún motivo falla el insert del viaje, revertimos el estado del chofer
        supabase.table("choferes").update({"estado": "disponible"}).eq("id", chofer_id_str).execute()
        raise HTTPException(status_code=500, detail="No se pudo crear el viaje")

    viaje_creado = resultado.data[0]

    registrar_evento(
        usuario_id=asignado_por,
        tipo_accion="alta",
        entidad="viaje",
        entidad_id=viaje_creado["id"],
        detalle=f"Viaje creado: {datos.origen} -> {datos.destino}",
    )

    return viaje_creado

def editar_viaje(viaje_id: str, datos: ViajeEditar, usuario_id: UUID) -> dict:
    viaje = _obtener_viaje(viaje_id)

    if viaje["estado"] not in ("pendiente", "en_curso"):
        raise HTTPException(status_code=400, detail="Solo se pueden editar viajes pendientes o en curso")

    cambios = datos.model_dump(exclude_unset=True, mode="json")

    if not cambios:
        raise HTTPException(status_code=400, detail="No se enviaron campos para actualizar")

    resultado = supabase.table("viajes").update(cambios).eq("id", viaje_id).execute()
    viaje_editado = resultado.data[0]

    registrar_evento(
        usuario_id=usuario_id,
        tipo_accion="edicion",
        entidad="viaje",
        entidad_id=viaje_id,
        detalle=f"Campos modificados: {', '.join(cambios.keys())}",
    )

    return viaje_editado


def cancelar_viaje(viaje_id: str, datos: ViajeCancelar, usuario_id: UUID) -> dict:
    viaje = _obtener_viaje(viaje_id)

    if viaje["estado"] in ("finalizado", "cancelado"):
        raise HTTPException(status_code=400, detail="Este viaje ya no se puede cancelar")

    resultado = (
        supabase.table("viajes")
        .update({"estado": "cancelado", "motivo_cancelacion": datos.motivo_cancelacion})
        .eq("id", viaje_id)
        .execute()
    )

    # El chofer vuelve a estar disponible
    supabase.table("choferes").update({"estado": "disponible"}).eq("id", viaje["chofer_id"]).execute()

    registrar_evento(
        usuario_id=usuario_id,
        tipo_accion="cancelacion",
        entidad="viaje",
        entidad_id=viaje_id,
        detalle=f"Motivo: {datos.motivo_cancelacion}",
    )

    return resultado.data[0]


def iniciar_viaje(viaje_id: str, usuario_id: UUID) -> dict:
    viaje = _obtener_viaje(viaje_id)

    if viaje["estado"] != "pendiente":
        raise HTTPException(status_code=400, detail="Solo se pueden iniciar viajes pendientes")

    resultado = supabase.table("viajes").update({"estado": "en_curso"}).eq("id", viaje_id).execute()

    registrar_evento(
        usuario_id=usuario_id,
        tipo_accion="edicion",
        entidad="viaje",
        entidad_id=viaje_id,
        detalle="Viaje pasado a en_curso",
    )

    return resultado.data[0]


def finalizar_viaje(viaje_id: str, datos: ViajeFinalizar, usuario_id: UUID) -> dict:
    viaje = _obtener_viaje(viaje_id)

    if viaje["estado"] != "en_curso":
        raise HTTPException(status_code=400, detail="Solo se pueden finalizar viajes en curso")

    cambios = {
        "estado": "finalizado",
        "fecha_fin": datos.fecha_fin.isoformat(),
        "kms_recorridos": datos.kms_recorridos,
    }

    resultado = supabase.table("viajes").update(cambios).eq("id", viaje_id).execute()

    # El chofer vuelve a estar disponible
    supabase.table("choferes").update({"estado": "disponible"}).eq("id", viaje["chofer_id"]).execute()

    registrar_evento(
        usuario_id=usuario_id,
        tipo_accion="edicion",
        entidad="viaje",
        entidad_id=viaje_id,
        detalle=f"Viaje finalizado, {datos.kms_recorridos} kms",
    )

    return resultado.data[0]


