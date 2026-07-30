from fastapi import APIRouter, Depends
from app.models.usuario import UsuarioCreate, UsuarioOut
from app.services.usuario_service import actualizar_usuario, crear_usuario, dar_de_baja_usuario, listar_usuarios
from app.dependencies import require_rol
from app.models.common import RespuestaPaginada
from app.models.usuario import UsuarioCreate, UsuarioOut, UsuarioUpdate

router = APIRouter(prefix="/usuarios", tags=["usuarios"])

@router.post("/", response_model=UsuarioOut, status_code=201)
def alta_usuario(
    datos: UsuarioCreate,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador"))
):
    return crear_usuario(datos, creado_por=usuario_actual.id)

@router.get("/", response_model=RespuestaPaginada[UsuarioOut])
def obtener_usuarios(
    pagina: int = 1,
    tamano_pagina: int = 20,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado", "aibar"))
):
    return listar_usuarios(pagina, tamano_pagina)

@router.patch("/{usuario_id}", response_model=UsuarioOut)
def editar_usuario(
    usuario_id: str,
    datos: UsuarioUpdate,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador"))
):
    return actualizar_usuario(usuario_id, datos, editado_por=usuario_actual.id)


@router.delete("/{usuario_id}", response_model=UsuarioOut)
def baja_usuario(
    usuario_id: str,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador"))
):
    return dar_de_baja_usuario(usuario_id, dado_de_baja_por=usuario_actual.id)