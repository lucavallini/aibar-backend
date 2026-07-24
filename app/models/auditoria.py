from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class AuditoriaOut(BaseModel):
    id: UUID
    usuario_id: UUID
    tipo_accion: str
    entidad: str
    entidad_id: UUID
    detalle: Optional[str] = None
    fecha_hora: datetime