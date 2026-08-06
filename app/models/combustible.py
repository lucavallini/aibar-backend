from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date
from uuid import UUID


class CargaCombustibleCreate(BaseModel):
    camion_id: UUID
    viaje_id: Optional[UUID] = None
    litros: float = Field(..., gt=0)
    monto: float = Field(..., gt=0)
    fecha: Optional[date] = None
    km_por_litro: Optional[float] = None


class CargaCombustibleOut(BaseModel):
    id: UUID
    camion_id: UUID
    viaje_id: Optional[UUID] = None
    litros: float
    monto: float
    fecha: date
    km_por_litro: Optional[float] = None
    registrado_por: Optional[UUID] = None
    creado_en: datetime