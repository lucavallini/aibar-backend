from app.database import supabase, armar_respuesta_paginada
from app.models.camion import CamionCreate, CamionUpdate, CamionCambiarEstado, AsignacionCamion
from app.core.exceptions import NotFoundError, BadRequestError, ConflictError, InternalError
from app.services.auditoria_service import registrar_evento
from uuid import UUID
from app.utils.fields import upper_fields

def listar_camiones(activos_only: bool = True, busqueda: str = None, pagina: int = 1, tamano_pagina: int = 20, empresa_id: str = None, chofer_id: str = None, acoplado_id: str = None) -> dict:
    query = supabase.table("camiones").select("*", count="exact")

    if activos_only:
        query = query.eq("activo", True)

    if empresa_id:
        query = query.eq("empresa_id", empresa_id)

    if acoplado_id:
        query = query.eq("acoplado_id", acoplado_id)

    if chofer_id:
        chofer = supabase.table("choferes").select("camion_id").eq("id", chofer_id).execute()
        camion_id = chofer.data[0].get("camion_id") if chofer.data else None
        if not camion_id:
            return {
                "items": [],
                "total": 0,
                "pagina": pagina,
                "tamano_pagina": tamano_pagina,
                "total_paginas": 1,
            }
        query = query.eq("id", camion_id)

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
    upper_fields(nuevo_camion, "marca", "modelo", "tipo")

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


def asignar_unidades(camion_id: str, datos: AsignacionCamion, usuario_id: UUID) -> dict:
    obtener_camion(camion_id)

    cambios = datos.model_dump(exclude_unset=True)
    if not cambios:
        raise BadRequestError("No se enviaron campos para asignar")

    en_uso = (
        supabase.table("viajes")
        .select("id")
        .in_("estado", ["pendiente", "en_curso"])
        .or_(f"camion_id.eq.{camion_id},camion_id_2.eq.{camion_id}")
        .execute()
    )
    if en_uso.data:
        raise ConflictError("No se puede reasignar: el camión tiene un viaje pendiente o en curso")

    detalle_cambios = []

    if "acoplado_id" in cambios:
        acoplado_id = cambios["acoplado_id"]
        if acoplado_id:
            acoplado = supabase.table("acoplados").select("id").eq("id", str(acoplado_id)).execute()
            if not acoplado.data:
                raise NotFoundError("El acoplado indicado no existe")
            supabase.table("camiones").update({"acoplado_id": None}).eq("acoplado_id", str(acoplado_id)).neq("id", camion_id).execute()
        supabase.table("camiones").update({"acoplado_id": acoplado_id}).eq("id", camion_id).execute()
        detalle_cambios.append("acoplado asignado" if acoplado_id else "acoplado desasignado")

    if "chofer_id" in cambios:
        chofer_id = cambios["chofer_id"]
        if chofer_id:
            chofer = supabase.table("choferes").select("id").eq("id", str(chofer_id)).execute()
            if not chofer.data:
                raise NotFoundError("El chofer indicado no existe")
            viaje_chofer = (
                supabase.table("viajes")
                .select("id")
                .eq("chofer_id", str(chofer_id))
                .in_("estado", ["pendiente", "en_curso"])
                .execute()
            )
            if viaje_chofer.data:
                raise ConflictError("El chofer indicado tiene un viaje pendiente o en curso")
            supabase.table("choferes").update({"camion_id": None}).eq("camion_id", camion_id).neq("id", str(chofer_id)).execute()
            supabase.table("choferes").update({"camion_id": camion_id}).eq("id", str(chofer_id)).execute()
            detalle_cambios.append("chofer asignado")
        else:
            supabase.table("choferes").update({"camion_id": None}).eq("camion_id", camion_id).execute()
            detalle_cambios.append("chofer desasignado")

    registrar_evento(
        usuario_id=usuario_id,
        tipo_accion="edicion",
        entidad="camion",
        entidad_id=camion_id,
        detalle=f"Campos asignados: {', '.join(detalle_cambios)}",
    )

    return obtener_camion(camion_id)


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