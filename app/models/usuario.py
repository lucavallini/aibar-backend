from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

class UsuarioCreate(BaseModel):
    nombre_completo: str = Field(...,min_length= 3, max_length= 100)
    dni : str = Field(..., min_length= 6, max_length= 20)
    password: str = Field(..., min_length= 6)
    rol: str = Field(default="empleado")

class UsuarioOut(BaseModel):
    id: UUID
    nombre_usuario: str
    nombre_completo: str
    dni: str
    rol: str
    activo:bool
    creado_en: datetime

class UsuarioUpdate(BaseModel):
    nombre_completo: Optional[str] = None
    dni: Optional[str] = None
    rol: Optional[str] = None
