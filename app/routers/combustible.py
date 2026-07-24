from fastapi import APIRouter, Depends
from app.models.combustible import CargaCombustibleCreate, CargaCombustibleOut
from app.models.usuario import UsuarioOut
from app.services.combustible_service import (
    crear_carga_combustible,
    listar_cargas_combustible,
    calcular_gasto_total_camion,
)
from app.dependencies import require_rol
from app.models.common import RespuestaPaginada

router = APIRouter(prefix="/combustible", tags=["combustible"])



@router.get("/", response_model=RespuestaPaginada[CargaCombustibleOut])
def obtener_cargas_combustible(
    camion_id: str = None,
    pagina: int = 1,
    tamano_pagina: int = 20,
    solo_ultimos_30_dias: bool = True,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return listar_cargas_combustible(camion_id, pagina, tamano_pagina, solo_ultimos_30_dias)


@router.post("/", response_model=CargaCombustibleOut, status_code=201)
def alta_carga_combustible(
    datos: CargaCombustibleCreate,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return crear_carga_combustible(datos, registrado_por=usuario_actual.id)


@router.get("/", response_model=list[CargaCombustibleOut])
def obtener_cargas_combustible(
    camion_id: str = None,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return listar_cargas_combustible(camion_id=camion_id)


@router.get("/{camion_id}/gasto-total")
def obtener_gasto_total(
    camion_id: str,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return calcular_gasto_total_camion(camion_id)