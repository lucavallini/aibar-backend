from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends
from app.models.auditoria import AuditoriaOut
from app.models.usuario import UsuarioOut
from app.services.auditoria_service import listar_auditoria
from app.dependencies import require_rol
from app.models.common import RespuestaPaginada

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


@router.get("/", response_model=RespuestaPaginada[AuditoriaOut])
def obtener_auditoria(
    usuario_id: Optional[UUID] = None,
    entidad: str = None,
    dias: int = None,
    pagina: int = 1,
    tamano_pagina: int = 20,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "aibar"))
):
    return listar_auditoria(str(usuario_id) if usuario_id else None, entidad, dias, pagina, tamano_pagina)
