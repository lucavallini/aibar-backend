from typing import Literal, Optional

from pydantic import BaseModel, Field

Campo = Literal["lugar", "carga"]


class SugerenciaPedido(BaseModel):
    campo: Campo
    texto: str = Field("", max_length=300)


class CambioSugerido(BaseModel):
    original: str
    sugerido: str
    #: "conocido" = equivalencia ya guardada; "parecido" = se deduce por ortografía.
    motivo: Literal["conocido", "parecido"]


class SugerenciaOut(BaseModel):
    campo: Campo
    texto: str
    #: None cuando no hay nada que corregir: el frontend no muestra el aviso.
    sugerido: Optional[str] = None
    cambios: list[CambioSugerido] = []


class AliasCreate(BaseModel):
    campo: Campo
    alias: str = Field(..., min_length=1, max_length=150)
    canonico: str = Field(..., min_length=2, max_length=150)


class AliasOut(BaseModel):
    campo: Campo
    alias: str
    canonico: str
