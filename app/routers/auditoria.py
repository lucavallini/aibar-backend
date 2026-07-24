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
    pagina: int = 1,
    tamano_pagina: int = 50,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador"))
):
    return listar_auditoria(usuario_id, entidad, pagina, tamano_pagina)


@router.get("/", response_model=list[AuditoriaOut])
def obtener_auditoria(
    usuario_id: str = None,
    entidad: str = None,
    limite: int = 100,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador"))
):
    return listar_auditoria(usuario_id=usuario_id, entidad=entidad, limite=limite)