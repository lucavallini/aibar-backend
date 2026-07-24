from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date
from uuid import UUID


class MultaCreate(BaseModel):
    camion_id: UUID
    chofer_id: Optional[UUID] = None
    viaje_id: Optional[UUID] = None
    motivo: str = Field(..., min_length=3, max_length=255)
    monto: Optional[float] = None
    fecha: Optional[date] = None  # si no se manda, usa la fecha actual (default de la tabla)


class MultaOut(BaseModel):
    id: UUID
    camion_id: UUID
    chofer_id: Optional[UUID] = None
    viaje_id: Optional[UUID] = None
    motivo: str
    monto: Optional[float] = None
    fecha: date
    registrado_por: Optional[UUID] = None
    creado_en: datetime