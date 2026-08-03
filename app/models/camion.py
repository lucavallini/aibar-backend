from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class CamionCreate(BaseModel):
    patente: str = Field(..., min_length=6, max_length=10)
    marca: Optional[str] = None
    modelo: Optional[str] = None
    anio: Optional[int] = None
    tipo: Optional[str] = None  # acoplado, doble acoplado, chasis, furgón, batea, etc
    empresa_id: Optional[UUID] = None


class CamionOut(BaseModel):
    id: UUID
    patente: str
    marca: Optional[str] = None
    modelo: Optional[str] = None
    anio: Optional[int] = None
    tipo: Optional[str] = None
    empresa_id: Optional[UUID] = None
    activo: bool
    estado: str = "disponible"
    motivo_no_disponible: Optional[str] = None
    creado_en: datetime


class CamionUpdate(BaseModel):
    marca: Optional[str] = None
    modelo: Optional[str] = None
    anio: Optional[int] = None
    tipo: Optional[str] = None
    empresa_id: Optional[UUID] = None


class CamionCambiarEstado(BaseModel):
    estado: str = Field(..., pattern="^(disponible|no_disponible)$")
    motivo_no_disponible: Optional[str] = None