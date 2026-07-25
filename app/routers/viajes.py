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
    agregar_vuelta,
    calcular_rendimiento_combustible,
)
from app.dependencies import require_rol
from app.models.common import RespuestaPaginada

router = APIRouter(prefix="/viajes", tags=["viajes"])



@router.get("/", response_model=RespuestaPaginada[ViajeOut])
def obtener_viajes(
    chofer_id: str = None,
    estado: str = None,
    dias: int = None,
    pagina: int = 1,
    tamano_pagina: int = 20,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return listar_viajes(chofer_id, estado, dias, pagina, tamano_pagina)


@router.post("/", response_model=ViajeOut, status_code=201)
def alta_viaje(
    datos: ViajeCreate,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return crear_viaje(datos, asignado_por=usuario_actual.id)


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


@router.post("/{viaje_id}/vuelta", response_model=ViajeOut, status_code=201)
def agregar_vuelta_endpoint(
    viaje_id: str,
    datos: ViajeCreate,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return agregar_vuelta(viaje_id, datos, asignado_por=usuario_actual.id)


@router.get("/rendimiento-combustible/{chofer_id}")
def obtener_rendimiento_combustible(
    chofer_id: str,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return calcular_rendimiento_combustible(chofer_id)