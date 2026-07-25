from fastapi import APIRouter, Depends
from app.models.chofer import ChoferCreate, ChoferOut, ChoferUpdate, ChoferCambiarEstado, ChoferDetalle
from app.models.usuario import UsuarioOut
from app.services.chofer_service import (
    crear_chofer,
    listar_choferes,
    obtener_chofer,
    obtener_detalle_chofer,
    actualizar_chofer,
    cambiar_estado_chofer,
    dar_de_baja_chofer,
    calcular_kms_mes_actual,
    calcular_kms_historico,
)
from app.dependencies import require_rol
from app.models.common import RespuestaPaginada

router = APIRouter(prefix="/choferes", tags=["choferes"])


@router.get("/", response_model=RespuestaPaginada[ChoferOut])
def obtener_choferes(
    activos_only: bool = True,
    pagina: int = 1,
    tamano_pagina: int = 20,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return listar_choferes(activos_only, pagina, tamano_pagina)


@router.post("/", response_model=ChoferOut, status_code=201)
def alta_chofer(
    datos: ChoferCreate,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador"))
):
    return crear_chofer(datos, creado_por=usuario_actual.id)


@router.get("/{chofer_id}", response_model=ChoferOut)
def obtener_chofer_por_id(
    chofer_id: str,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return obtener_chofer(chofer_id)


@router.patch("/{chofer_id}", response_model=ChoferOut)
def editar_chofer(
    chofer_id: str,
    datos: ChoferUpdate,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return actualizar_chofer(chofer_id, datos, usuario_id=usuario_actual.id)


@router.patch("/{chofer_id}/estado", response_model=ChoferOut)
def cambiar_estado(
    chofer_id: str,
    datos: ChoferCambiarEstado,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return cambiar_estado_chofer(chofer_id, datos, usuario_id=usuario_actual.id)


@router.delete("/{chofer_id}", response_model=ChoferOut)
def baja_chofer(
    chofer_id: str,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador"))
):
    return dar_de_baja_chofer(chofer_id, usuario_id=usuario_actual.id)

@router.get("/{chofer_id}/detalle", response_model=ChoferDetalle)
def obtener_chofer_detalle(
    chofer_id: str,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return obtener_detalle_chofer(chofer_id)


@router.get("/{chofer_id}/kms-mes-actual")
def obtener_kms_mes_actual(
    chofer_id: str,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return {"chofer_id": chofer_id, "kms_mes_actual": calcular_kms_mes_actual(chofer_id)}


@router.get("/{chofer_id}/kms-historico")
def obtener_kms_historico(
    chofer_id: str,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return {"chofer_id": chofer_id, "historico": calcular_kms_historico(chofer_id)}