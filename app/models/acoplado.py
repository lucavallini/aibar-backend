from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class AcopladoCreate(BaseModel):
    patente: str = Field(..., min_length=6, max_length=20)
    tipo: Optional[str] = None
    empresa_id: Optional[UUID] = None


class AcopladoOut(BaseModel):
    id: UUID
    patente: str
    tipo: Optional[str] = None
    empresa_id: Optional[UUID] = None
    activo: bool
    estado: str = "disponible"
    motivo_no_disponible: Optional[str] = None
    creado_en: datetime


class AcopladoUpdate(BaseModel):
    patente: Optional[str] = Field(None, min_length=6, max_length=20)
    tipo: Optional[str] = None
    empresa_id: Optional[UUID] = None


class AcopladoCambiarEstado(BaseModel):
    estado: str = Field(..., pattern="^(disponible|no_disponible)$")
    motivo_no_disponible: Optional[str] = None
