from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends
from app.models.common import RespuestaPaginada
from app.models.multa import MultaCreate, MultaOut
from app.models.usuario import UsuarioOut
from app.services.multa_service import crear_multa, listar_multas
from app.dependencies import require_rol

router = APIRouter(prefix="/multas", tags=["multas"])



@router.get("/", response_model=RespuestaPaginada[MultaOut])
def obtener_multas(
    camion_id: Optional[UUID] = None,
    chofer_id: Optional[UUID] = None,
    pagina: int = 1,
    tamano_pagina: int = 20,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado", "aibar"))
):
    return listar_multas(
        str(camion_id) if camion_id else None,
        str(chofer_id) if chofer_id else None,
        pagina,
        tamano_pagina,
    )


@router.post("/", response_model=MultaOut, status_code=201)
def alta_multa(
    datos: MultaCreate,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return crear_multa(datos, registrado_por=usuario_actual.id)
