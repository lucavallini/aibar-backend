from app.database import supabase
from app.models.chofer import ChoferCreate, ChoferUpdate, ChoferCambiarEstado
from app.core.exceptions import NotFoundError, BadRequestError, ConflictError, InternalError
from uuid import UUID
from datetime import date
import calendar
from app.database import supabase, armar_respuesta_paginada
from app.services.auditoria_service import registrar_evento
from app.utils.fields import upper_fields

def listar_choferes(activos_only: bool = True, busqueda: str = None, pagina: int = 1, tamano_pagina: int = 20, incluir_kms_mes: bool = False, empresa_id: str = None) -> dict:
    query = supabase.table("choferes").select("*", count="exact")

    if activos_only:
        query = query.eq("activo", True)

    if empresa_id:
        query = query.eq("empresa_id", empresa_id)

    if busqueda:
        query = query.ilike("nombre_completo", f"%{busqueda}%")

    query = query.order("nombre_completo")

    resultado = armar_respuesta_paginada(query, pagina, tamano_pagina)

    if incluir_kms_mes:
        _adjuntar_kms_mes_actual(resultado)

    return resultado

def _adjuntar_kms_mes_actual(resultado: dict) -> None:
    items = resultado.get("items", [])
    ids = [chofer["id"] for chofer in items]
    if not ids:
        return

    primer_dia_mes = date.today().replace(day=1).isoformat()
    viajes = (
        supabase.table("viajes")
        .select("chofer_id, kms_recorridos")
        .eq("estado", "finalizado")
        .gte("fecha_inicio", primer_dia_mes)
        .in_("chofer_id", ids)
        .execute()
    )

    kms_por_chofer: dict[str, float] = {}
    for viaje in viajes.data:
        chofer_id = viaje.get("chofer_id")
        kms = viaje.get("kms_recorridos") or 0
        kms_por_chofer[chofer_id] = kms_por_chofer.get(chofer_id, 0) + kms

    for chofer in items:
        chofer["kms_mes_actual"] = kms_por_chofer.get(chofer["id"], 0)

def crear_chofer(datos: ChoferCreate, creado_por: UUID) -> dict:
    nuevo_chofer = datos.model_dump(mode="json")
    upper_fields(nuevo_chofer, "nombre_completo", "dni", "telefono")

    if datos.dni:
        dni_existente = supabase.table("choferes").select("id").eq("dni", nuevo_chofer["dni"]).execute()
        if dni_existente.data:
            raise BadRequestError("Ya existe un chofer con ese DNI")

    if datos.camion_id:
        camion = supabase.table("camiones").select("id").eq("id", str(datos.camion_id)).execute()
        if not camion.data:
            raise NotFoundError("El camión indicado no existe")
    nuevo_chofer["creado_por"] = str(creado_por)

    resultado = supabase.table("choferes").insert(nuevo_chofer).execute()

    if not resultado.data:
        raise InternalError("No se pudo crear el chofer")

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
        raise NotFoundError("Chofer no encontrado")

    return resultado.data[0]


def actualizar_chofer(chofer_id: str, datos: ChoferUpdate, usuario_id: UUID) -> dict:
    obtener_chofer(chofer_id)

    cambios = datos.model_dump(exclude_unset=True, mode="json")
    upper_fields(cambios, "nombre_completo", "dni", "telefono")

    if not cambios:
        raise BadRequestError("No se enviaron campos para actualizar")

    if "camion_id" in cambios and cambios["camion_id"] is not None:
        camion = supabase.table("camiones").select("id").eq("id", cambios["camion_id"]).execute()
        if not camion.data:
            raise NotFoundError("El camión indicado no existe")

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

    en_uso = (
        supabase.table("viajes")
        .select("id")
        .eq("chofer_id", chofer_id)
        .in_("estado", ["pendiente", "en_curso"])
        .execute()
    )
    if en_uso.data:
        raise ConflictError("No se puede cambiar el estado: el chofer tiene un viaje pendiente o en curso")

    cambios = {"estado": datos.estado}

    if datos.estado == "no_disponible":
        motivo = (datos.motivo_no_disponible or "").strip()
        if not motivo:
            raise BadRequestError("Debés indicar el motivo del estado no disponible")
        cambios["motivo_no_disponible"] = motivo
    else:
        cambios["motivo_no_disponible"] = None

    resultado = supabase.table("choferes").update(cambios).eq("id", chofer_id).execute()

    detalle = f"Estado cambiado a: {datos.estado}"
    if "motivo_no_disponible" in cambios and cambios["motivo_no_disponible"]:
        detalle += f" (motivo: {cambios['motivo_no_disponible']})"

    registrar_evento(
        usuario_id=usuario_id,
        tipo_accion="edicion",
        entidad="chofer",
        entidad_id=chofer_id,
        detalle=detalle,
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


def _viajes_finalizados(chofer_id: str) -> list:
    resultado = (
        supabase.table("viajes")
        .select("kms_recorridos, fecha_inicio")
        .eq("chofer_id", chofer_id)
        .eq("estado", "finalizado")
        .execute()
    )
    return resultado.data


def obtener_detalle_chofer(chofer_id: str) -> dict:
    chofer = obtener_chofer(chofer_id)
    viajes = _viajes_finalizados(chofer_id)

    hoy = date.today()
    primer_dia_mes = hoy.replace(day=1).isoformat()
    kms_mes = sum(
        v["kms_recorridos"] or 0
        for v in viajes
        if (v["fecha_inicio"] or "") >= primer_dia_mes
    )

    acumulado = {}
    for viaje in viajes:
        fecha = viaje["fecha_inicio"][:7]  # "2026-07-22..." -> "2026-07"
        acumulado[fecha] = acumulado.get(fecha, 0) + (viaje["kms_recorridos"] or 0)

    historico = [{"mes": mes, "kms": kms} for mes, kms in sorted(acumulado.items(), reverse=True)]

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