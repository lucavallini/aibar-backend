from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class EmpresaCreate(BaseModel):
    nombre: str


class EmpresaOut(BaseModel):
    id: UUID
    nombre: str
    creado_en: datetime
