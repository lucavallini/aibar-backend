import re
import unicodedata
from app.database import supabase, armar_respuesta_paginada
from app.models.usuario import UsuarioCreate, UsuarioUpdate
from app.core.security import hash_password
from app.core.exceptions import NotFoundError, BadRequestError, InternalError
from app.services.auditoria_service import registrar_evento
from uuid import UUID


def _normalizar(texto: str) -> str:
    """
    Normaliza un texto eliminando acentos y caracteres especiales.
    """
    texto = unicodedata.normalize('NFKD', texto)
    texto =texto.encode('ascii', 'ignore').decode('ascii')
    return texto.lower()

def listar_usuarios(pagina: int = 1, tamano_pagina: int = 20) -> dict:
    query = supabase.table("usuarios").select("*", count="exact").order("nombre_completo")
    return armar_respuesta_paginada(query, pagina, tamano_pagina)

def _generar_base_usuario(nombre_completo:str)-> str:
    partes = _normalizar(nombre_completo).split()

    if len(partes)<2:
        base = partes[0] if partes else "usuario"

    else:
        nombre = partes[0]
        apellido = partes[-1]
        base = f"{nombre}{apellido}"
    base = re.sub(r'[^a-z0-9.]', '', base)
    return base



def generar_nombre_usuario(nombre_completo:str, dni:str) -> str:
    base = _generar_base_usuario(nombre_completo)

    existe= supabase.table("usuarios").select("nombre_usuario").eq("nombre_usuario", base).execute()

    if not existe.data:
        return base

    sufijo = dni[-4:]
    return f"{base}.{sufijo}"




def crear_usuario(datos: UsuarioCreate, creado_por: UUID) -> dict:
    dni_existente = supabase.table('usuarios').select('id').eq('dni', datos.dni).execute()

    if dni_existente.data:
        raise BadRequestError("DNI vinculado a otro usuario.")

    nombre_usuario = generar_nombre_usuario(datos.nombre_completo, datos.dni)
    password_hash = hash_password(datos.password)

    nuevo_usuario = {
        "nombre_usuario": nombre_usuario,
        "nombre_completo": datos.nombre_completo,
        "dni": datos.dni,
        "password_hash": password_hash,
        "rol": datos.rol,
    }

    resultado = supabase.table("usuarios").insert(nuevo_usuario).execute()

    if not resultado.data:
        raise InternalError("No se pudo crear el usuario")

    usuario_creado = resultado.data[0]

    registrar_evento(
        usuario_id=creado_por,
        tipo_accion="alta",
        entidad="usuario",
        entidad_id=usuario_creado["id"],
        detalle=f"Usuario creado: {nombre_usuario} ({datos.rol})",
    )

    return usuario_creado

def actualizar_usuario(usuario_id: str, datos: UsuarioUpdate, editado_por: UUID) -> dict:
    resultado_actual = supabase.table("usuarios").select("*").eq("id", usuario_id).execute()
    if not resultado_actual.data:
        raise NotFoundError("Usuario no encontrado")

    cambios = datos.model_dump(exclude_unset=True, mode="json")

    if not cambios:
        raise BadRequestError("No se enviaron campos para actualizar")

    if "dni" in cambios:
        dni_existente = supabase.table("usuarios").select("id").eq("dni", cambios["dni"]).execute()
        if dni_existente.data and dni_existente.data[0]["id"] != usuario_id:
            raise BadRequestError("Ya existe otro usuario con ese DNI")

    resultado = supabase.table("usuarios").update(cambios).eq("id", usuario_id).execute()
    usuario_editado = resultado.data[0]

    registrar_evento(
        usuario_id=editado_por,
        tipo_accion="edicion",
        entidad="usuario",
        entidad_id=usuario_id,
        detalle=f"Campos modificados: {', '.join(cambios.keys())}",
    )

    return usuario_editado


def dar_de_baja_usuario(usuario_id: str, dado_de_baja_por: UUID) -> dict:
    resultado_actual = supabase.table("usuarios").select("*").eq("id", usuario_id).execute()
    if not resultado_actual.data:
        raise NotFoundError("Usuario no encontrado")

    if usuario_id == str(dado_de_baja_por):
        raise BadRequestError("No podés darte de baja a vos mismo")

    resultado = supabase.table("usuarios").update({"activo": False}).eq("id", usuario_id).execute()

    registrar_evento(
        usuario_id=dado_de_baja_por,
        tipo_accion="baja",
        entidad="usuario",
        entidad_id=usuario_id,
    )

    return resultado.data[0]