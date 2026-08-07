from fastapi import APIRouter, Depends
from app.models.camion import CamionCreate, CamionOut, CamionUpdate, CamionCambiarEstado, AsignacionCamion
from app.models.usuario import UsuarioOut
from app.services.camion_service import (
    crear_camion,
    listar_camiones,
    obtener_camion,
    actualizar_camion,
    cambiar_estado_camion,
    dar_de_baja_camion,
    asignar_unidades,
)
from app.dependencies import require_rol
from app.models.common import RespuestaPaginada

router = APIRouter(prefix="/camiones", tags=["camiones"])



@router.get("/", response_model=RespuestaPaginada[CamionOut])
def obtener_camiones(
    activos_only: bool = True,
    busqueda: str = None,
    pagina: int = 1,
    tamano_pagina: int = 20,
    empresa_id: str = None,
    chofer_id: str = None,
    acoplado_id: str = None,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado", "aibar"))
):
    return listar_camiones(activos_only, busqueda, pagina, tamano_pagina, empresa_id, chofer_id, acoplado_id)

@router.post("/", response_model=CamionOut, status_code=201)
def alta_camion(
    datos: CamionCreate,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador"))
):
    return crear_camion(datos, usuario_id=usuario_actual.id)

@router.get("/{camion_id}", response_model=CamionOut)
def obtener_camion_por_id(
    camion_id: str,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado", "aibar"))
):
    return obtener_camion(camion_id)



@router.patch("/{camion_id}/estado", response_model=CamionOut)
def cambiar_estado(
    camion_id: str,
    datos: CamionCambiarEstado,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return cambiar_estado_camion(camion_id, datos, usuario_id=usuario_actual.id)


@router.patch("/{camion_id}", response_model=CamionOut)
def editar_camion(
    camion_id: str,
    datos: CamionUpdate,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador"))
):
    return actualizar_camion(camion_id, datos, usuario_id=usuario_actual.id)


@router.patch("/{camion_id}/asignacion", response_model=CamionOut)
def asignar_camion(
    camion_id: str,
    datos: AsignacionCamion,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return asignar_unidades(camion_id, datos, usuario_id=usuario_actual.id)


@router.delete("/{camion_id}", response_model=CamionOut)
def baja_camion(
    camion_id: str,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador"))
):
    return dar_de_baja_camion(camion_id, usuario_id=usuario_actual.id)