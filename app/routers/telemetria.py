from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies import require_rol
from app.models.telemetria import FlotaOut, RecorridoOut, ViajeHistorico
from app.models.usuario import UsuarioOut
from app.services.telemetria_service import buscar_viajes, listar_flota, obtener_recorrido_de_viaje

router = APIRouter(prefix="/telemetria", tags=["telemetria"])


@router.get("/flota", response_model=FlotaOut)
def obtener_flota(
    busqueda: Optional[str] = None,
    empresa_id: Optional[UUID] = None,
    solo_en_viaje: bool = False,
    solo_ubicadas: bool = False,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado", "aibar")),
):
    return listar_flota(
        busqueda,
        str(empresa_id) if empresa_id else None,
        solo_en_viaje,
        solo_ubicadas,
    )


@router.get("/viajes/{viaje_id}/recorrido", response_model=RecorridoOut)
def obtener_recorrido(
    viaje_id: UUID,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado", "aibar")),
):
    return obtener_recorrido_de_viaje(str(viaje_id))


@router.get("/viajes", response_model=list[ViajeHistorico])
def obtener_viajes_historicos(
    chofer_id: Optional[UUID] = None,
    patente: Optional[str] = None,
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado", "aibar")),
):
    return buscar_viajes(
        str(chofer_id) if chofer_id else None, patente, fecha_desde, fecha_hasta
    )
