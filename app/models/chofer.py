from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class ChoferCreate(BaseModel):
    nombre_completo: str = Field(..., min_length=3, max_length=100)
    dni: Optional[str] = Field(None, min_length=6, max_length=20)
    telefono: Optional[str] = None
    camion_id: Optional[UUID] = None


class ChoferOut(BaseModel):
    id: UUID
    nombre_completo: str
    dni: Optional[str] = None
    telefono: Optional[str] = None
    estado: str
    camion_id: Optional[UUID] = None
    activo: bool
    creado_en: datetime
    creado_por: Optional[UUID] = None


class ChoferUpdate(BaseModel):
    nombre_completo: Optional[str] = None
    dni: Optional[str] = None
    telefono: Optional[str] = None
    camion_id: Optional[UUID] = None


class ChoferCambiarEstado(BaseModel):
    estado: str = Field(..., pattern="^(disponible|viajando|inactivo|licencia)$")


class KmsPorMes(BaseModel):
    mes: str
    kms: float


class ChoferDetalle(BaseModel):
    id: UUID
    nombre_completo: str
    dni: Optional[str] = None
    telefono: Optional[str] = None
    estado: str
    activo: bool
    kms_mes_actual: float
    historico: list[KmsPorMes]