from fastapi import HTTPException
from app.database import supabase
from app.models.chofer import ChoferCreate, ChoferUpdate, ChoferCambiarEstado
from uuid import UUID
from datetime import date
import calendar
from app.database import supabase, armar_respuesta_paginada
from app.services.auditoria_service import registrar_evento

def listar_choferes(activos_only: bool = True, busqueda: str = None, pagina: int = 1, tamano_pagina: int = 20) -> dict:
    query = supabase.table("choferes").select("*", count="exact")

    if activos_only:
        query = query.eq("activo", True)

    if busqueda:
        query = query.ilike("nombre_completo", f"%{busqueda}%")

    query = query.order("nombre_completo")

    return armar_respuesta_paginada(query, pagina, tamano_pagina)

def crear_chofer(datos: ChoferCreate, creado_por: UUID) -> dict:
    if datos.dni:
        dni_existente = supabase.table("choferes").select("id").eq("dni", datos.dni).execute()
        if dni_existente.data:
            raise HTTPException(status_code=400, detail="Ya existe un chofer con ese DNI")

    if datos.camion_id:
        camion = supabase.table("camiones").select("id").eq("id", str(datos.camion_id)).execute()
        if not camion.data:
            raise HTTPException(status_code=404, detail="El camión indicado no existe")

    nuevo_chofer = datos.model_dump(mode="json")
    nuevo_chofer["creado_por"] = str(creado_por)

    resultado = supabase.table("choferes").insert(nuevo_chofer).execute()

    if not resultado.data:
        raise HTTPException(status_code=500, detail="No se pudo crear el chofer")

    chofer_creado = resultado.data[0]

    registrar_evento(
        usuario_id=creado_por,
        tipo_accion="alta",
        entidad="chofer",
        entidad_id=chofer_creado["id"],
        detalle=f"Chofer creado: {datos.nombre_completo}",
    )

    return chofer_creado




def obtener_chofer(chofer_id: str) -> dict:
    resultado = supabase.table("choferes").select("*").eq("id", chofer_id).execute()

    if not resultado.data:
        raise HTTPException(status_code=404, detail="Chofer no encontrado")

    return resultado.data[0]


def actualizar_chofer(chofer_id: str, datos: ChoferUpdate, usuario_id: UUID) -> dict:
    obtener_chofer(chofer_id)

    cambios = datos.model_dump(exclude_unset=True, mode="json")

    if not cambios:
        raise HTTPException(status_code=400, detail="No se enviaron campos para actualizar")

    if "camion_id" in cambios and cambios["camion_id"] is not None:
        camion = supabase.table("camiones").select("id").eq("id", cambios["camion_id"]).execute()
        if not camion.data:
            raise HTTPException(status_code=404, detail="El camión indicado no existe")

    resultado = supabase.table("choferes").update(cambios).eq("id", chofer_id).execute()
    chofer_editado = resultado.data[0]

    registrar_evento(
        usuario_id=usuario_id,
        tipo_accion="edicion",
        entidad="chofer",
        entidad_id=chofer_id,
        detalle=f"Campos modificados: {', '.join(cambios.keys())}",
    )

    return chofer_editado


def cambiar_estado_chofer(chofer_id: str, datos: ChoferCambiarEstado, usuario_id: UUID) -> dict:
    obtener_chofer(chofer_id)

    resultado = supabase.table("choferes").update({"estado": datos.estado}).eq("id", chofer_id).execute()

    registrar_evento(
        usuario_id=usuario_id,
        tipo_accion="edicion",
        entidad="chofer",
        entidad_id=chofer_id,
        detalle=f"Estado cambiado a: {datos.estado}",
    )

    return resultado.data[0]



def dar_de_baja_chofer(chofer_id: str, usuario_id: UUID) -> dict:
    obtener_chofer(chofer_id)

    resultado = supabase.table("choferes").update({"activo": False}).eq("id", chofer_id).execute()

    registrar_evento(
        usuario_id=usuario_id,
        tipo_accion="baja",
        entidad="chofer",
        entidad_id=chofer_id,
    )

    return resultado.data[0]


def calcular_kms_mes_actual(chofer_id: str) -> float:
    hoy = date.today()
    primer_dia_mes = hoy.replace(day=1).isoformat()

    resultado = (
        supabase.table("viajes")
        .select("kms_recorridos")
        .eq("chofer_id", chofer_id)
        .eq("estado", "finalizado")
        .gte("fecha_inicio", primer_dia_mes)
        .execute()
    )

    total = sum(v["kms_recorridos"] or 0 for v in resultado.data)
    return total


def obtener_detalle_chofer(chofer_id: str) -> dict:
    chofer = obtener_chofer(chofer_id)
    kms_mes = calcular_kms_mes_actual(chofer_id)
    historico = calcular_kms_historico(chofer_id)
    return {
        **chofer,
        "kms_mes_actual": kms_mes,
        "historico": historico,
    }


def calcular_kms_historico(chofer_id: str) -> list:
    resultado = (
        supabase.table("viajes")
        .select("kms_recorridos, fecha_inicio")
        .eq("chofer_id", chofer_id)
        .eq("estado", "finalizado")
        .execute()
    )

    acumulado = {}
    for viaje in resultado.data:
        fecha = viaje["fecha_inicio"][:7]  # "2026-07-22..." -> "2026-07"
        acumulado[fecha] = acumulado.get(fecha, 0) + (viaje["kms_recorridos"] or 0)

    historico = [{"mes": mes, "kms": kms} for mes, kms in sorted(acumulado.items(), reverse=True)]
    return historico