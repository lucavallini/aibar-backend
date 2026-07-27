from fastapi import APIRouter, Depends
from app.models.camion import CamionCreate, CamionOut, CamionUpdate
from app.models.usuario import UsuarioOut
from app.services.camion_service import (
    crear_camion,
    listar_camiones,
    obtener_camion,
    actualizar_camion,
    dar_de_baja_camion,
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
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return listar_camiones(activos_only, busqueda, pagina, tamano_pagina)

@router.post("/", response_model=CamionOut, status_code=201)
def alta_camion(
    datos: CamionCreate,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador"))
):
    return crear_camion(datos, usuario_id=usuario_actual.id)

@router.get("/{camion_id}", response_model=CamionOut)
def obtener_camion_por_id(
    camion_id: str,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return obtener_camion(camion_id)



@router.patch("/{camion_id}", response_model=CamionOut)
def editar_camion(
    camion_id: str,
    datos: CamionUpdate,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador"))
):
    return actualizar_camion(camion_id, datos, usuario_id=usuario_actual.id)


@router.delete("/{camion_id}", response_model=CamionOut)
def baja_camion(
    camion_id: str,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador"))
):
    return dar_de_baja_camion(camion_id, usuario_id=usuario_actual.id)