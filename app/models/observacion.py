from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class ObservacionCreate(BaseModel):
    observacion: str = Field(..., min_length=1, max_length=2000)


class ObservacionOut(BaseModel):
    id: UUID
    chofer_id: UUID
    observacion: str
    mes: int
    anio: int
    creado_en: datetime
    creado_por: Optional[UUID] = None
    actualizado_en: Optional[datetime] = None
