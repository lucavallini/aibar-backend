from app.database import supabase
from app.models.camion import CamionCreate, CamionUpdate, CamionCambiarEstado
from app.database import supabase, armar_respuesta_paginada
from app.core.exceptions import NotFoundError, BadRequestError, ConflictError, InternalError
from app.services.auditoria_service import registrar_evento
from uuid import UUID
from app.utils.fields import upper_fields

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
        raise NotFoundError("Camión no encontrado")

    return resultado.data[0]

def crear_camion(datos: CamionCreate, usuario_id: UUID) -> dict:
    nuevo_camion = datos.model_dump(mode="json")
    upper_fields(nuevo_camion, "patente", "marca", "modelo", "tipo")

    patente_existente = supabase.table("camiones").select("id").eq("patente", nuevo_camion["patente"]).execute()

    if patente_existente.data:
        raise BadRequestError("Ya existe un camión con esa patente")

    resultado = supabase.table("camiones").insert(nuevo_camion).execute()

    if not resultado.data:
        raise InternalError("No se pudo crear el camión")

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

    cambios = datos.model_dump(exclude_unset=True, mode="json")
    upper_fields(cambios, "marca", "modelo", "tipo")

    if not cambios:
        raise BadRequestError("No se enviaron campos para actualizar")

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


def cambiar_estado_camion(camion_id: str, datos: CamionCambiarEstado, usuario_id: UUID) -> dict:
    obtener_camion(camion_id)

    en_uso = (
        supabase.table("viajes")
        .select("id")
        .in_("estado", ["pendiente", "en_curso"])
        .or_(f"camion_id.eq.{camion_id},camion_id_2.eq.{camion_id}")
        .execute()
    )
    if en_uso.data:
        raise ConflictError("No se puede cambiar el estado: el chasis está asignado a un viaje pendiente o en curso")

    cambios = {"estado": datos.estado}

    if datos.estado == "no_disponible":
        motivo = (datos.motivo_no_disponible or "").strip()
        if not motivo:
            raise BadRequestError("Debés indicar el motivo del estado no disponible")
        cambios["motivo_no_disponible"] = motivo
    else:
        cambios["motivo_no_disponible"] = None

    resultado = supabase.table("camiones").update(cambios).eq("id", camion_id).execute()

    detalle = f"Estado cambiado a: {datos.estado}"
    if cambios["motivo_no_disponible"]:
        detalle += f" (motivo: {cambios['motivo_no_disponible']})"

    registrar_evento(
        usuario_id=usuario_id,
        tipo_accion="edicion",
        entidad="camion",
        entidad_id=camion_id,
        detalle=detalle,
    )

    return resultado.data[0]


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