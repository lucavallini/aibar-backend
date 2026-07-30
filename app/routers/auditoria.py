from fastapi import APIRouter, Depends
from app.models.auditoria import AuditoriaOut
from app.models.usuario import UsuarioOut
from app.services.auditoria_service import listar_auditoria
from app.dependencies import require_rol
from app.models.common import RespuestaPaginada

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


@router.get("/", response_model=RespuestaPaginada[AuditoriaOut])
def obtener_auditoria(
    usuario_id: str = None,
    entidad: str = None,
    dias: int = None,
    pagina: int = 1,
    tamano_pagina: int = 20,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "aibar"))
):
    return listar_auditoria(usuario_id, entidad, dias, pagina, tamano_pagina)
