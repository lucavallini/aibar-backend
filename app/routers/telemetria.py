from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies import require_rol
from app.models.telemetria import FlotaOut, RecorridoOut
from app.models.usuario import UsuarioOut
from app.services.telemetria_service import listar_flota, obtener_recorrido_de_viaje

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
