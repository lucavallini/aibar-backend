from typing import Optional
from uuid import UUID
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
    empresa_id: Optional[UUID] = None,
    chofer_id: Optional[UUID] = None,
    acoplado_id: Optional[UUID] = None,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado", "aibar"))
):
    return listar_camiones(
        activos_only,
        busqueda,
        pagina,
        tamano_pagina,
        str(empresa_id) if empresa_id else None,
        str(chofer_id) if chofer_id else None,
        str(acoplado_id) if acoplado_id else None,
    )

@router.post("/", response_model=CamionOut, status_code=201)
def alta_camion(
    datos: CamionCreate,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador"))
):
    return crear_camion(datos, usuario_id=usuario_actual.id)

@router.get("/{camion_id}", response_model=CamionOut)
def obtener_camion_por_id(
    camion_id: UUID,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado", "aibar"))
):
    return obtener_camion(str(camion_id))



@router.patch("/{camion_id}/estado", response_model=CamionOut)
def cambiar_estado(
    camion_id: UUID,
    datos: CamionCambiarEstado,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return cambiar_estado_camion(str(camion_id), datos, usuario_id=usuario_actual.id)


@router.patch("/{camion_id}", response_model=CamionOut)
def editar_camion(
    camion_id: UUID,
    datos: CamionUpdate,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador"))
):
    return actualizar_camion(str(camion_id), datos, usuario_id=usuario_actual.id)


@router.patch("/{camion_id}/asignacion", response_model=CamionOut)
def asignar_camion(
    camion_id: UUID,
    datos: AsignacionCamion,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return asignar_unidades(str(camion_id), datos, usuario_id=usuario_actual.id)


@router.delete("/{camion_id}", response_model=CamionOut)
def baja_camion(
    camion_id: UUID,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador"))
):
    return dar_de_baja_camion(str(camion_id), usuario_id=usuario_actual.id)
