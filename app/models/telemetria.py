from datetime import datetime
from typing import Annotated, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field


class PosicionOut(BaseModel):
    latitud: float
    longitud: float
    velocidad_kph: float
    rumbo_grados: int
    reportado_en: datetime
    minutos_desde_reporte: int


class TelemetriaOut(BaseModel):
    contacto_encendido: bool
    senal_trabajo: Optional[bool] = None
    temperatura: Optional[float] = None


class ViajeEnCursoOut(BaseModel):
    id: UUID
    origen: str
    destino: str
    cliente: Optional[str] = None
    carga: Optional[str] = None
    tarifa: Optional[float] = None
    fecha_inicio: datetime
    estado: str
    chofer_id: Optional[UUID] = None
    chofer_nombre: Optional[str] = None


class UnidadBase(BaseModel):
    """Lo que toda unidad del mapa tiene, venga de donde venga."""

    patente: str


class UnidadRegistradaBase(UnidadBase):
    """Unidad que existe en la flota propia, con o sin rastreo satelital."""

    camion_id: UUID
    marca: Optional[str] = None
    modelo: Optional[str] = None
    tipo: Optional[str] = None
    empresa_id: Optional[UUID] = None
    empresa_nombre: Optional[str] = None
    estado: str
    viaje: Optional[ViajeEnCursoOut] = None


class UnidadUbicadaBase(UnidadBase):
    """Unidad que el servicio de rastreo está reportando en el mapa."""

    posicion: PosicionOut
    telemetria: TelemetriaOut
    descripcion_gps: Optional[str] = None
    chofer_gps: Optional[str] = None


class UnidadEnMapa(UnidadRegistradaBase, UnidadUbicadaBase):
    """Camión propio con posición: el caso completo."""

    categoria: Literal["en_mapa"] = "en_mapa"


class UnidadSinGps(UnidadRegistradaBase):
    """Camión propio que el servicio de rastreo no reporta."""

    categoria: Literal["sin_gps"] = "sin_gps"
    motivo: str = "GPS no disponible"


class UnidadDadaDeBaja(UnidadRegistradaBase, UnidadUbicadaBase):
    """Camión propio dado de baja al que todavía le quedó el equipo reportando."""

    categoria: Literal["dada_de_baja"] = "dada_de_baja"
    motivo: str = "Dada de baja en el sistema"


class UnidadNoRegistrada(UnidadUbicadaBase):
    """Unidad que el servicio reporta pero que no existe en la flota propia."""

    categoria: Literal["no_registrada"] = "no_registrada"
    motivo: str = "Unidad no registrada en el sistema"


Unidad = Annotated[
    Union[UnidadEnMapa, UnidadSinGps, UnidadDadaDeBaja, UnidadNoRegistrada],
    Field(discriminator="categoria"),
]


class ResumenFlota(BaseModel):
    en_mapa: int
    sin_gps: int
    dadas_de_baja: int
    no_registradas: int
    en_viaje: int


class FlotaOut(BaseModel):
    generado_en: datetime
    resumen: ResumenFlota
    unidades: list[Unidad]


class PuntoRecorrido(BaseModel):
    latitud: float
    longitud: float
    velocidad_kph: float
    limite_kph: Optional[int] = None
    momento: datetime


class DetencionRecorrido(BaseModel):
    latitud: float
    longitud: float
    inicio: datetime
    fin: Optional[datetime] = None
    duracion: Optional[str] = None


class RecorridoOut(BaseModel):
    viaje_id: UUID
    patente: str
    distancia_km: float
    velocidad_maxima_kph: int
    puntos: list[PuntoRecorrido]
    detenciones: list[DetencionRecorrido]
    recortado: bool
    """True cuando el proveedor devolvió días completos y se recortó al rango del viaje."""
    en_camino: bool
    """True si la unidad sigue rodando: el último punto es dónde va, no dónde llegó."""
    sin_datos_por_antiguedad: bool
    """True cuando no hay traza porque el viaje quedó fuera de lo que el proveedor guarda."""


class ViajeHistorico(BaseModel):
    """Viaje del buscador del mapa, listo para listar sin resolver nada más."""

    id: UUID
    origen: str
    destino: str
    estado: str
    fecha_inicio: datetime
    fecha_fin: Optional[datetime] = None
    chofer_nombre: Optional[str] = None
    patente: Optional[str] = None
