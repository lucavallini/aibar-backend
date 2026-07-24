from pydantic import BaseModel
from typing import Generic, TypeVar, List

T = TypeVar("T")


class RespuestaPaginada(BaseModel, Generic[T]):
    items: List[T]
    total: int
    pagina: int
    tamano_pagina: int
    total_paginas: int