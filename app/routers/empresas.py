from fastapi import APIRouter, Depends
from app.models.empresa import EmpresaCreate, EmpresaOut
from app.models.usuario import UsuarioOut
from app.services.empresa_service import listar_empresas, crear_empresa
from app.dependencies import require_rol
from app.models.common import RespuestaPaginada

router = APIRouter(prefix="/empresas", tags=["empresas"])


@router.get("/", response_model=RespuestaPaginada[EmpresaOut])
def obtener_empresas(
    busqueda: str = None,
    pagina: int = 1,
    tamano_pagina: int = 20,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado", "aibar")),
):
    return listar_empresas(busqueda, pagina, tamano_pagina)


@router.post("/", response_model=EmpresaOut, status_code=201)
def alta_empresa(
    datos: EmpresaCreate,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador")),
):
    return crear_empresa(datos, usuario_id=usuario_actual.id)
