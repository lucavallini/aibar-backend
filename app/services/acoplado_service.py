from app.database import supabase, armar_respuesta_paginada
from app.models.acoplado import AcopladoCreate, AcopladoUpdate, AcopladoCambiarEstado
from app.core.exceptions import NotFoundError, BadRequestError, ConflictError, InternalError
from app.services.auditoria_service import registrar_evento
from uuid import UUID
from app.utils.fields import upper_fields


def listar_acoplados(activos_only: bool = True, busqueda: str = None, pagina: int = 1, tamano_pagina: int = 20, empresa_id: str = None) -> dict:
    query = supabase.table("acoplados").select("*", count="exact")

    if activos_only:
        query = query.eq("activo", True)

    if empresa_id:
        query = query.eq("empresa_id", empresa_id)

    if busqueda:
        query = query.ilike("patente", f"%{busqueda}%")

    query = query.order("patente")

    return armar_respuesta_paginada(query, pagina, tamano_pagina)


def obtener_acoplado(acoplado_id: str) -> dict:
    resultado = supabase.table("acoplados").select("*").eq("id", acoplado_id).execute()

    if not resultado.data:
        raise NotFoundError("Acoplado no encontrado")

    return resultado.data[0]


def crear_acoplado(datos: AcopladoCreate, usuario_id: UUID) -> dict:
    nuevo_acoplado = datos.model_dump(mode="json")
    upper_fields(nuevo_acoplado, "patente", "tipo")

    patente_existente = supabase.table("acoplados").select("id").eq("patente", nuevo_acoplado["patente"]).execute()

    if patente_existente.data:
        raise BadRequestError("Ya existe un acoplado con esa patente")

    resultado = supabase.table("acoplados").insert(nuevo_acoplado).execute()

    if not resultado.data:
        raise InternalError("No se pudo crear el acoplado")

    acoplado_creado = resultado.data[0]

    registrar_evento(
        usuario_id=usuario_id,
        tipo_accion="alta",
        entidad="acoplado",
        entidad_id=acoplado_creado["id"],
        detalle=f"Acoplado creado: {datos.patente}",
    )

    return acoplado_creado


def actualizar_acoplado(acoplado_id: str, datos: AcopladoUpdate, usuario_id: UUID) -> dict:
    obtener_acoplado(acoplado_id)

    cambios = datos.model_dump(exclude_unset=True, mode="json")
    upper_fields(cambios, "patente", "tipo")

    if "patente" in cambios:
        patente_existente = supabase.table("acoplados").select("id").eq("patente", cambios["patente"]).neq("id", acoplado_id).execute()
        if patente_existente.data:
            raise BadRequestError("Ya existe otro acoplado con esa patente")

    if not cambios:
        raise BadRequestError("No se enviaron campos para actualizar")

    resultado = supabase.table("acoplados").update(cambios).eq("id", acoplado_id).execute()
    acoplado_editado = resultado.data[0]

    registrar_evento(
        usuario_id=usuario_id,
        tipo_accion="edicion",
        entidad="acoplado",
        entidad_id=acoplado_id,
        detalle=f"Campos modificados: {', '.join(cambios.keys())}",
    )

    return acoplado_editado


def cambiar_estado_acoplado(acoplado_id: str, datos: AcopladoCambiarEstado, usuario_id: UUID) -> dict:
    obtener_acoplado(acoplado_id)

    en_uso = (
        supabase.table("viajes")
        .select("id")
        .in_("estado", ["pendiente", "en_curso"])
        .or_(f"camion_id.eq.{acoplado_id},camion_id_2.eq.{acoplado_id}")
        .execute()
    )
    if en_uso.data:
        raise ConflictError("No se puede cambiar el estado: el acoplado está asignado a un viaje pendiente o en curso")

    cambios = {"estado": datos.estado}

    if datos.estado == "no_disponible":
        motivo = (datos.motivo_no_disponible or "").strip()
        if not motivo:
            raise BadRequestError("Debés indicar el motivo del estado no disponible")
        cambios["motivo_no_disponible"] = motivo
    else:
        cambios["motivo_no_disponible"] = None

    resultado = supabase.table("acoplados").update(cambios).eq("id", acoplado_id).execute()

    detalle = f"Estado cambiado a: {datos.estado}"
    if cambios["motivo_no_disponible"]:
        detalle += f" (motivo: {cambios['motivo_no_disponible']})"

    registrar_evento(
        usuario_id=usuario_id,
        tipo_accion="edicion",
        entidad="acoplado",
        entidad_id=acoplado_id,
        detalle=detalle,
    )

    return resultado.data[0]


def dar_de_baja_acoplado(acoplado_id: str, usuario_id: UUID) -> dict:
    obtener_acoplado(acoplado_id)

    resultado = supabase.table("acoplados").update({"activo": False}).eq("id", acoplado_id).execute()

    registrar_evento(
        usuario_id=usuario_id,
        tipo_accion="baja",
        entidad="acoplado",
        entidad_id=acoplado_id,
    )

    return resultado.data[0]
