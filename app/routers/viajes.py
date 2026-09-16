from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends
from app.models.viaje import ViajeCreate, ViajeOut, ViajeEditar, ViajeCancelar, ViajeFinalizar, ViajeReanudar, ViajeEliminado
from app.models.usuario import UsuarioOut
from app.services.viaje_service import (
    crear_viaje,
    editar_viaje,
    cancelar_viaje,
    reanudar_viaje,
    iniciar_viaje,
    finalizar_viaje,
    listar_viajes,
    agregar_vuelta,
    calcular_rendimiento_combustible,
    eliminar_viaje,
)
from app.dependencies import require_rol
from app.models.common import RespuestaPaginada

router = APIRouter(prefix="/viajes", tags=["viajes"])



@router.get("/", response_model=RespuestaPaginada[ViajeOut])
def obtener_viajes(
    chofer_id: Optional[UUID] = None,
    estado: str = None,
    dias: int = None,
    patente: str = None,
    fecha_desde: str = None,
    fecha_hasta: str = None,
    empresa_id: Optional[UUID] = None,
    pagina: int = 1,
    tamano_pagina: int = 20,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado", "aibar"))
):
    return listar_viajes(
        str(chofer_id) if chofer_id else None,
        estado,
        dias,
        patente,
        fecha_desde,
        fecha_hasta,
        str(empresa_id) if empresa_id else None,
        pagina,
        tamano_pagina,
    )


@router.post("/", response_model=ViajeOut, status_code=201)
def alta_viaje(
    datos: ViajeCreate,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return crear_viaje(datos, asignado_por=usuario_actual.id)


@router.patch("/{viaje_id}", response_model=ViajeOut)
def editar_viaje_endpoint(
    viaje_id: UUID,
    datos: ViajeEditar,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return editar_viaje(str(viaje_id), datos, usuario_id=usuario_actual.id)


@router.post("/{viaje_id}/cancelar", response_model=ViajeOut)
def cancelar_viaje_endpoint(
    viaje_id: UUID,
    datos: ViajeCancelar,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return cancelar_viaje(str(viaje_id), datos, usuario_id=usuario_actual.id)


@router.post("/{viaje_id}/reanudar", response_model=ViajeOut)
def reanudar_viaje_endpoint(
    viaje_id: UUID,
    datos: ViajeReanudar,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return reanudar_viaje(str(viaje_id), datos, usuario_id=usuario_actual.id)


@router.post("/{viaje_id}/iniciar", response_model=ViajeOut)
def iniciar_viaje_endpoint(
    viaje_id: UUID,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return iniciar_viaje(str(viaje_id), usuario_id=usuario_actual.id)


@router.post("/{viaje_id}/finalizar", response_model=ViajeOut)
def finalizar_viaje_endpoint(
    viaje_id: UUID,
    datos: ViajeFinalizar,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return finalizar_viaje(str(viaje_id), datos, usuario_id=usuario_actual.id)


@router.post("/{viaje_id}/vuelta", response_model=ViajeOut, status_code=201)
def agregar_vuelta_endpoint(
    viaje_id: UUID,
    datos: ViajeCreate,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return agregar_vuelta(str(viaje_id), datos, asignado_por=usuario_actual.id)


@router.get("/rendimiento-combustible/{chofer_id}")
def obtener_rendimiento_combustible(
    chofer_id: UUID,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado", "aibar"))
):
    return calcular_rendimiento_combustible(str(chofer_id))


@router.delete("/{viaje_id}", response_model=ViajeEliminado)
def borrar_viaje(
    viaje_id: UUID,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador"))
):
    """Borrado definitivo. Se lleva el viaje de vuelta y las cargas de combustible."""
    return eliminar_viaje(str(viaje_id), usuario_id=usuario_actual.id)
