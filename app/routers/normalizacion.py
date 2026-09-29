from fastapi import APIRouter, Depends, Query

from app.dependencies import require_rol
from app.models.normalizacion import AliasCreate, AliasOut, SugerenciaOut, SugerenciaPedido
from app.services import normalizacion_service

router = APIRouter(prefix="/normalizacion", tags=["normalizacion"])


@router.post("/sugerir", response_model=SugerenciaOut)
def sugerir(
    pedido: SugerenciaPedido,
    _=Depends(require_rol("administrador", "empleado", "aibar")),
):
    """Qué debería decir el campo según el catálogo. No guarda nada."""
    return normalizacion_service.sugerir(pedido.campo, pedido.texto)


@router.get("/canonicos", response_model=list[str])
def canonicos(
    campo: str = Query(...),
    _=Depends(require_rol("administrador", "empleado", "aibar")),
):
    return normalizacion_service.listar_canonicos(campo)


@router.post("/alias", response_model=AliasOut)
def crear_alias(
    datos: AliasCreate,
    _=Depends(require_rol("administrador")),
):
    """Deja guardada una equivalencia nueva para que se sugiera de acá en adelante."""
    return normalizacion_service.registrar_alias(datos.campo, datos.alias, datos.canonico)
