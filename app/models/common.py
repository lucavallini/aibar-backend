from pydantic import BaseModel, BeforeValidator
from typing import Annotated, Generic, TypeVar, List

from app.utils.fields import normalizar_patente

T = TypeVar("T")


def _normalizar(valor):
    """Normaliza cada patente conservando la barra que separa a los bitrenes.

    Un acoplado doble se carga con las dos patentes en el mismo campo
    ("AH346HN/AH346HM"), así que no se puede limpiar el texto de una sola pasada:
    hay que normalizar cada lado por separado.
    """
    if not isinstance(valor, str):
        return valor
    partes = [normalizar_patente(parte) for parte in valor.split("/")]
    return "/".join(parte for parte in partes if parte)


Patente = Annotated[str, BeforeValidator(_normalizar)]
"""Patente ya normalizada: mayúsculas, sin espacios ni guiones.

Se aplica al validar el modelo, así toda alta o edición queda guardada en el mismo
formato sin que cada service tenga que acordarse.
"""

class RespuestaPaginada(BaseModel, Generic[T]):
    items: List[T]
    total: int
    pagina: int
    tamano_pagina: int
    total_paginas: int