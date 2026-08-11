from typing import Optional
from uuid import UUID
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
    busqueda: str = None,
    pagina: int = 1,
    tamano_pagina: int = 20,
    incluir_kms_mes: bool = False,
    empresa_id: Optional[UUID] = None,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado", "aibar"))
):
    return listar_choferes(
        activos_only,
        busqueda,
        pagina,
        tamano_pagina,
        incluir_kms_mes,
        str(empresa_id) if empresa_id else None,
    )


@router.post("/", response_model=ChoferOut, status_code=201)
def alta_chofer(
    datos: ChoferCreate,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador"))
):
    return crear_chofer(datos, creado_por=usuario_actual.id)


@router.get("/{chofer_id}", response_model=ChoferOut)
def obtener_chofer_por_id(
    chofer_id: UUID,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado", "aibar"))
):
    return obtener_chofer(str(chofer_id))


@router.patch("/{chofer_id}", response_model=ChoferOut)
def editar_chofer(
    chofer_id: UUID,
    datos: ChoferUpdate,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return actualizar_chofer(str(chofer_id), datos, usuario_id=usuario_actual.id)


@router.patch("/{chofer_id}/estado", response_model=ChoferOut)
def cambiar_estado(
    chofer_id: UUID,
    datos: ChoferCambiarEstado,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado"))
):
    return cambiar_estado_chofer(str(chofer_id), datos, usuario_id=usuario_actual.id)


@router.delete("/{chofer_id}", response_model=ChoferOut)
def baja_chofer(
    chofer_id: UUID,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador"))
):
    return dar_de_baja_chofer(str(chofer_id), usuario_id=usuario_actual.id)

@router.get("/{chofer_id}/detalle", response_model=ChoferDetalle)
def obtener_chofer_detalle(
    chofer_id: UUID,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado", "aibar"))
):
    return obtener_detalle_chofer(str(chofer_id))


@router.get("/{chofer_id}/kms-mes-actual")
def obtener_kms_mes_actual(
    chofer_id: UUID,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado", "aibar"))
):
    return {"chofer_id": chofer_id, "kms_mes_actual": calcular_kms_mes_actual(str(chofer_id))}


@router.get("/{chofer_id}/kms-historico")
def obtener_kms_historico(
    chofer_id: UUID,
    usuario_actual: UsuarioOut = Depends(require_rol("administrador", "empleado", "aibar"))
):
    return {"chofer_id": chofer_id, "historico": calcular_kms_historico(str(chofer_id))}
