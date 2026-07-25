from fastapi import HTTPException
from app.database import supabase
from app.models.viaje import ViajeCreate, ViajeEditar, ViajeCancelar, ViajeFinalizar, ViajeOut
from app.services.auditoria_service import registrar_evento
from uuid import UUID
from datetime import datetime, timedelta, timezone
from app.database import supabase, armar_respuesta_paginada

def listar_viajes(chofer_id: str = None, estado: str = None, dias: int = None, pagina: int = 1, tamano_pagina: int = 20) -> dict:
    query = supabase.table("viajes").select("*", count="exact")

    if chofer_id:
        query = query.eq("chofer_id", chofer_id)

    if estado:
        query = query.eq("estado", estado)

    if dias:
        cutoff = datetime.now(timezone.utc) - timedelta(days=dias)
        query = query.gte("fecha_inicio", cutoff.isoformat())

    query = query.order("fecha_inicio", desc=True)

    result = armar_respuesta_paginada(query, pagina, tamano_pagina)

    ids_vueltas = set()
    for viaje in result["items"]:
        if viaje.get("viaje_vuelta_id"):
            vuelta_id = viaje["viaje_vuelta_id"]
            ids_vueltas.add(vuelta_id)
            vuelta = supabase.table("viajes").select("*").eq("id", vuelta_id).execute()
            if vuelta.data:
                viaje["viaje_vuelta"] = vuelta.data[0]

    result["items"] = [v for v in result["items"] if v["id"] not in ids_vueltas]
    return result


def _obtener_nombre_chofer(chofer_id: str) -> str:
    r = supabase.table("choferes").select("nombre_completo").eq("id", chofer_id).execute()
    return r.data[0]["nombre_completo"] if r.data else "Desconocido"


def _obtener_nombre_usuario(usuario_id: str) -> str:
    r = supabase.table("usuarios").select("nombre_completo").eq("id", usuario_id).execute()
    return r.data[0]["nombre_completo"] if r.data else "Desconocido"


def _obtener_viaje(viaje_id: str) -> dict:
    resultado = supabase.table("viajes").select("*").eq("id", viaje_id).execute()
    if not resultado.data:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")
    return resultado.data[0]


def crear_viaje(datos: ViajeCreate, asignado_por: UUID) -> dict:
    chofer_id_str = str(datos.chofer_id)

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

    nuevo_viaje = datos.model_dump(mode="json", exclude_unset=True)
    nuevo_viaje["asignado_por"] = str(asignado_por)
    if "camion_id_2" in nuevo_viaje and nuevo_viaje["camion_id_2"] is None:
        nuevo_viaje.pop("camion_id_2")
    if "viaje_vuelta_id" in nuevo_viaje and nuevo_viaje["viaje_vuelta_id"] is None:
        nuevo_viaje.pop("viaje_vuelta_id")

    resultado = supabase.table("viajes").insert(nuevo_viaje).execute()

    if not resultado.data:
        supabase.table("choferes").update({"estado": "disponible"}).eq("id", chofer_id_str).execute()
        raise HTTPException(status_code=500, detail="No se pudo crear el viaje")

    viaje_creado = resultado.data[0]

    chofer_nombre = _obtener_nombre_chofer(str(datos.chofer_id))
    usuario_nombre = _obtener_nombre_usuario(str(asignado_por))

    registrar_evento(
        usuario_id=asignado_por,
        tipo_accion="alta",
        entidad="viaje",
        entidad_id=viaje_creado["id"],
        detalle=f"Viaje creado: {datos.origen} -> {datos.destino} | Chofer: {chofer_nombre} | Por: {usuario_nombre}",
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


def agregar_vuelta(viaje_id: str, datos: ViajeCreate, asignado_por: UUID) -> dict:
    viaje_original = _obtener_viaje(viaje_id)

    if viaje_original["viaje_vuelta_id"]:
        raise HTTPException(status_code=400, detail="Este viaje ya tiene una vuelta asignada")

    if viaje_original["estado"] not in ("pendiente", "en_curso", "finalizado"):
        raise HTTPException(status_code=400, detail="No se puede agregar vuelta a un viaje cancelado")

    chofer_id_str = str(datos.chofer_id)

    if viaje_original["chofer_id"] != chofer_id_str:
        reserva = (
            supabase.table("choferes")
            .update({"estado": "viajando"})
            .eq("id", chofer_id_str)
            .eq("estado", "disponible")
            .execute()
        )
        if not reserva.data:
            raise HTTPException(status_code=409, detail="El chofer de la vuelta no está disponible")

    nuevo_viaje = datos.model_dump(mode="json", exclude_unset=True)
    nuevo_viaje["asignado_por"] = str(asignado_por)
    nuevo_viaje.pop("viaje_vuelta_id", None)
    for campo in ("camion_id_2", "viaje_vuelta_id"):
        if campo in nuevo_viaje and nuevo_viaje[campo] is None:
            nuevo_viaje.pop(campo, None)

    resultado = supabase.table("viajes").insert(nuevo_viaje).execute()

    if not resultado.data:
        if viaje_original["chofer_id"] != chofer_id_str:
            supabase.table("choferes").update({"estado": "disponible"}).eq("id", chofer_id_str).execute()
        raise HTTPException(status_code=500, detail="No se pudo crear el viaje de vuelta")

    viaje_vuelta_id = resultado.data[0]["id"]

    supabase.table("viajes").update({"viaje_vuelta_id": viaje_vuelta_id}).eq("id", viaje_id).execute()

    chofer_nombre = _obtener_nombre_chofer(str(datos.chofer_id))
    usuario_nombre = _obtener_nombre_usuario(str(asignado_por))

    registrar_evento(
        usuario_id=asignado_por,
        tipo_accion="edicion",
        entidad="viaje",
        entidad_id=viaje_id,
        detalle=f"Viaje de vuelta agregado: {datos.origen} -> {datos.destino} | Chofer: {chofer_nombre} | Por: {usuario_nombre}",
    )

    return resultado.data[0]


def calcular_rendimiento_combustible(chofer_id: str) -> dict:
    viajes = (
        supabase.table("viajes")
        .select("id, kms_recorridos")
        .eq("chofer_id", chofer_id)
        .eq("estado", "finalizado")
        .execute()
    )

    total_kms = sum(v["kms_recorridos"] or 0 for v in viajes.data)
    viaje_ids = [v["id"] for v in viajes.data]

    total_litros = 0
    if viaje_ids:
        cargas = (
            supabase.table("cargas_combustible")
            .select("litros")
            .in_("viaje_id", viaje_ids)
            .execute()
        )
        total_litros = sum(c["litros"] or 0 for c in cargas.data)

    rendimiento = round(total_kms / total_litros, 2) if total_litros > 0 else None
    litros_cien = round(total_litros / total_kms * 100, 2) if total_kms > 0 else None

    return {
        "chofer_id": chofer_id,
        "total_kms": total_kms,
        "total_litros": total_litros,
        "km_por_litro": rendimiento,
        "litros_100km": litros_cien,
    }


def finalizar_viaje(viaje_id: str, datos: ViajeFinalizar, usuario_id: UUID) -> dict:
    viaje = _obtener_viaje(viaje_id)

    if viaje["estado"] != "en_curso":
        raise HTTPException(status_code=400, detail="Solo se pueden finalizar viajes en curso")

    km_por_litro = None
    if datos.litros_combustible and datos.litros_combustible > 0:
        km_por_litro = round(datos.kms_recorridos / datos.litros_combustible, 2)

    cambios = {
        "estado": "finalizado",
        "fecha_fin": datos.fecha_fin.isoformat(),
        "kms_recorridos": datos.kms_recorridos,
        "litros_combustible": datos.litros_combustible,
        "km_por_litro": km_por_litro,
    }

    resultado = supabase.table("viajes").update(cambios).eq("id", viaje_id).execute()

    supabase.table("choferes").update({"estado": "disponible"}).eq("id", viaje["chofer_id"]).execute()

    detalle = f"Viaje finalizado, {datos.kms_recorridos} kms"
    if datos.litros_combustible:
        detalle += f", {datos.litros_combustible} L"
    if km_por_litro:
        detalle += f", {km_por_litro} km/l"

    registrar_evento(
        usuario_id=usuario_id,
        tipo_accion="edicion",
        entidad="viaje",
        entidad_id=viaje_id,
        detalle=detalle,
    )

    return resultado.data[0]


