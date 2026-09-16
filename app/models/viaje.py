from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class ViajeCreate(BaseModel):
    chofer_id: UUID
    camion_id: Optional[UUID] = None
    camion_id_2: Optional[UUID] = None
    viaje_vuelta_id: Optional[UUID] = None
    cliente: Optional[str] = None
    origen: str = Field(..., min_length=2, max_length=150)
    destino: str = Field(..., min_length=2, max_length=150)
    carga: Optional[str] = None
    tarifa: Optional[float] = None
    fecha_inicio: datetime


class ViajeOut(BaseModel):
    id: UUID
    chofer_id: UUID
    camion_id: Optional[UUID] = None
    camion_id_2: Optional[UUID] = None
    viaje_vuelta_id: Optional[UUID] = None
    cliente: Optional[str] = None
    origen: str
    destino: str
    carga: Optional[str] = None
    tarifa: Optional[float] = None
    kms_recorridos: Optional[float] = None
    kms_descargado: Optional[float] = None
    fecha_inicio: datetime
    fecha_fin: Optional[datetime] = None
    estado: str
    motivo_cancelacion: Optional[str] = None
    solo_ida: bool = False
    asignado_por: UUID
    autorizado_por: Optional[UUID] = None
    creado_en: datetime
    viaje_vuelta: Optional["ViajeOut"] = None
    litros_combustible: Optional[float] = None
    km_por_litro: Optional[float] = None


class ViajeEditar(BaseModel):
    cliente: Optional[str] = None
    origen: Optional[str] = None
    destino: Optional[str] = None
    carga: Optional[str] = None
    tarifa: Optional[float] = None
    fecha_inicio: Optional[datetime] = None
    camion_id_2: Optional[UUID] = None

class ViajeReanudar(BaseModel):
    chofer_id: Optional[UUID] = None
    camion_id: Optional[UUID] = None
    camion_id_2: Optional[UUID] = None
    cliente: Optional[str] = None
    origen: Optional[str] = None
    destino: Optional[str] = None
    carga: Optional[str] = None
    tarifa: Optional[float] = None
    fecha_inicio: Optional[datetime] = None


class ViajeCancelar(BaseModel):
    motivo_cancelacion: str = Field(..., min_length=5, max_length=500)


class ViajeFinalizar(BaseModel):
    fecha_fin: datetime
    kms_recorridos: float = Field(..., gt=0)
    kms_descargado: Optional[float] = None
    litros_combustible: Optional[float] = None
    solo_ida: bool = False

class ViajeEliminado(BaseModel):
    """Resultado del borrado definitivo: cuántos registros dejaron de existir."""

    eliminados: int
    cargas_combustible_eliminadas: int
    multas_desvinculadas: int
