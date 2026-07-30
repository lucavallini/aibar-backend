from fastapi import APIRouter, Depends
from app.models.observacion import ObservacionCreate, ObservacionOut
from app.models.usuario import UsuarioOut
from app.services.observacion_service import listar_observaciones, guardar_observacion
from app.dependencies import require_rol

router = APIRouter(prefix="/observaciones", tags=["observaciones"])


@router.get("/{chofer_id}", response_model=list[ObservacionOut])
def obtener_observaciones(
    chofer_id: str,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado", "aibar"))
):
    return listar_observaciones(chofer_id)


@router.put("/{chofer_id}", response_model=ObservacionOut)
def guardar_observacion_endpoint(
    chofer_id: str,
    datos: ObservacionCreate,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return guardar_observacion(chofer_id, datos, usuario_id=usuario_actual.id)
