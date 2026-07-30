from app.database import supabase, armar_respuesta_paginada
from app.models.empresa import EmpresaCreate
from app.core.exceptions import BadRequestError, InternalError
from app.services.auditoria_service import registrar_evento
from app.utils.fields import upper_fields
from uuid import UUID


def listar_empresas(busqueda: str = None, pagina: int = 1, tamano_pagina: int = 20) -> dict:
    query = supabase.table("empresas").select("*", count="exact")
    if busqueda:
        query = query.ilike("nombre", f"%{busqueda}%")
    query = query.order("nombre")
    return armar_respuesta_paginada(query, pagina, tamano_pagina)


def crear_empresa(datos: EmpresaCreate, usuario_id: UUID) -> dict:
    data = datos.model_dump(mode="json")
    upper_fields(data, "nombre")

    existente = supabase.table("empresas").select("id").eq("nombre", data["nombre"]).execute()
    if existente.data:
        raise BadRequestError("Ya existe una empresa con ese nombre")
    resultado = supabase.table("empresas").insert(data).execute()

    if not resultado.data:
        raise InternalError("No se pudo crear la empresa")

    empresa_creada = resultado.data[0]

    registrar_evento(
        usuario_id=usuario_id,
        tipo_accion="alta",
        entidad="empresa",
        entidad_id=empresa_creada["id"],
        detalle=f"Empresa creada: {data['nombre']}",
    )

    return empresa_creada
