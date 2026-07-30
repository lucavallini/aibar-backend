from fastapi import APIRouter, Depends
from app.models.acoplado import AcopladoCreate, AcopladoOut, AcopladoUpdate
from app.models.usuario import UsuarioOut
from app.services.acoplado_service import (
    crear_acoplado,
    listar_acoplados,
    obtener_acoplado,
    actualizar_acoplado,
    dar_de_baja_acoplado,
)
from app.dependencies import require_rol
from app.models.common import RespuestaPaginada

router = APIRouter(prefix="/acoplados", tags=["acoplados"])


@router.get("/", response_model=RespuestaPaginada[AcopladoOut])
def obtener_acoplados(
    activos_only: bool = True,
    busqueda: str = None,
    pagina: int = 1,
    tamano_pagina: int = 20,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado", "aibar")),

):
    return listar_acoplados(activos_only, busqueda, pagina, tamano_pagina)

@router.post("/", response_model=AcopladoOut, status_code=201)
def alta_acoplado(
    datos: AcopladoCreate,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador")),
):
    return crear_acoplado(datos, usuario_id=usuario_actual.id)


@router.get("/{acoplado_id}", response_model=AcopladoOut)
def obtener_acoplado_por_id(
    acoplado_id: str,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado", "aibar")),

):
    return obtener_acoplado(acoplado_id)

@router.patch("/{acoplado_id}", response_model=AcopladoOut)
def editar_acoplado(
    acoplado_id: str,
    datos: AcopladoUpdate,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador")),
):
    return actualizar_acoplado(acoplado_id, datos, usuario_id=usuario_actual.id)


@router.delete("/{acoplado_id}", response_model=AcopladoOut)
def baja_acoplado(
    acoplado_id: str,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador")),
):
    return dar_de_baja_acoplado(acoplado_id, usuario_id=usuario_actual.id)
