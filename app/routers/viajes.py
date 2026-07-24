from fastapi import APIRouter, Depends
from app.models.viaje import ViajeCreate, ViajeOut, ViajeEditar, ViajeCancelar, ViajeFinalizar
from app.models.usuario import UsuarioOut
from app.services.viaje_service import (
    crear_viaje,
    editar_viaje,
    cancelar_viaje,
    iniciar_viaje,
    finalizar_viaje,
    listar_viajes,
)
from app.dependencies import require_rol
from app.models.common import RespuestaPaginada

router = APIRouter(prefix="/viajes", tags=["viajes"])



@router.get("/", response_model=RespuestaPaginada[ViajeOut])
def obtener_viajes(
    chofer_id: str = None,
    estado: str = None,
    pagina: int = 1,
    tamano_pagina: int = 20,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return listar_viajes(chofer_id, estado, pagina, tamano_pagina)


@router.post("/", response_model=ViajeOut, status_code=201)
def alta_viaje(
    datos: ViajeCreate,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return crear_viaje(datos, asignado_por=usuario_actual.id)


@router.get("/", response_model=list[ViajeOut])
def obtener_viajes(
    chofer_id: str = None,
    estado: str = None,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return listar_viajes(chofer_id=chofer_id, estado=estado)


@router.patch("/{viaje_id}", response_model=ViajeOut)
def editar_viaje_endpoint(
    viaje_id: str,
    datos: ViajeEditar,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return editar_viaje(viaje_id, datos, usuario_id=usuario_actual.id)


@router.post("/{viaje_id}/cancelar", response_model=ViajeOut)
def cancelar_viaje_endpoint(
    viaje_id: str,
    datos: ViajeCancelar,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return cancelar_viaje(viaje_id, datos, usuario_id=usuario_actual.id)


@router.post("/{viaje_id}/iniciar", response_model=ViajeOut)
def iniciar_viaje_endpoint(
    viaje_id: str,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return iniciar_viaje(viaje_id, usuario_id=usuario_actual.id)


@router.post("/{viaje_id}/finalizar", response_model=ViajeOut)
def finalizar_viaje_endpoint(
    viaje_id: str,
    datos: ViajeFinalizar,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return finalizar_viaje(viaje_id, datos, usuario_id=usuario_actual.id)