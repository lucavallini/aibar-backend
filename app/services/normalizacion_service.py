"""Sugerencias de escritura para los campos de texto libre de un viaje.

Los lugares y las cargas se escriben a mano, así que el mismo pueblo entra como
«VT», «VENADO» o «VENADO TUERTO» y la misma mercadería como «CONTEINER» o
«CONTENEDOR». Este módulo compara lo que se tipeó contra un catálogo de valores
canónicos y devuelve la forma correcta, sin imponerla: el campo sigue aceptando
valores nuevos porque siempre aparecen pueblos y cargas que no están cargados.

Un campo de lugar no contiene un lugar sino un itinerario («VT, RUFINO Y ARIAS»),
por eso la comparación se hace pueblo por pueblo y el texto se rearma con los
mismos separadores que escribió el usuario.
"""

import difflib
import re
import time

from app.core.exceptions import BadRequestError
from app.database import supabase

CAMPOS = ("lugar", "carga")

#: Separadores con que se enumeran varios lugares en un mismo campo. Van en un
#: grupo de captura para poder rearmar el texto tal como se escribió.
SEPARADORES = re.compile(r"(\s*[,/]\s*|\s+[YE]\s+)", re.IGNORECASE)

#: Un parecido más bajo empieza a confundir pueblos distintos (BANDERA/BANDERALO).
PARECIDO_MINIMO = 0.86

#: El catálogo cambia muy de a poco y se consulta en cada tecla.
SEGUNDOS_CACHE = 300

_cache: dict[str, tuple[float, dict, list[str]]] = {}


def _catalogo(campo: str) -> tuple[dict[str, str], list[str]]:
    """Alias conocidos y lista de canónicos del campo, con caché en memoria."""
    guardado = _cache.get(campo)
    if guardado and time.monotonic() - guardado[0] < SEGUNDOS_CACHE:
        return guardado[1], guardado[2]

    canonicos = (
        supabase.table("valores_canonicos").select("id, valor").eq("campo", campo).execute()
    ).data or []
    por_id = {c["id"]: c["valor"] for c in canonicos}

    filas = (
        supabase.table("alias_valores").select("alias, canonico_id").eq("campo", campo).execute()
    ).data or []
    alias = {f["alias"]: por_id[f["canonico_id"]] for f in filas if f["canonico_id"] in por_id}

    valores = sorted(por_id.values())
    _cache[campo] = (time.monotonic(), alias, valores)
    return alias, valores


def limpiar_cache() -> None:
    """El catálogo se editó: la próxima consulta lo vuelve a leer."""
    _cache.clear()


def _normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip().upper()


def _corregir(parte: str, alias: dict[str, str], valores: list[str]) -> tuple[str, str] | None:
    """Devuelve (canónico, motivo) si la parte tiene una forma mejor."""
    if not parte:
        return None

    # Los alias se miran antes que el catálogo: si un valor mal escrito llegó a
    # cargarse como canónico, la equivalencia explícita tiene que ganar igual.
    canonico = alias.get(parte)
    if canonico:
        return (canonico, "conocido") if canonico != parte else None

    if parte in valores:
        return None

    parecidos = difflib.get_close_matches(parte, valores, n=1, cutoff=PARECIDO_MINIMO)
    if parecidos and parecidos[0] != parte:
        return parecidos[0], "parecido"
    return None


def sugerir(campo: str, texto: str) -> dict:
    """Qué debería decir el campo, y qué parte de lo escrito lo motiva.

    `sugerido` es None cuando no hay nada que corregir, así el frontend sólo
    tiene que preguntar por ese campo para saber si muestra el aviso.
    """
    if campo not in CAMPOS:
        raise BadRequestError(f"Campo desconocido: se esperaba uno de {', '.join(CAMPOS)}")

    original = _normalizar(texto)
    if not original:
        return {"campo": campo, "texto": original, "sugerido": None, "cambios": []}

    alias, valores = _catalogo(campo)

    piezas = SEPARADORES.split(original)
    cambios = []
    for i in range(0, len(piezas), 2):  # las impares son los separadores
        parte = _normalizar(piezas[i])
        arreglo = _corregir(parte, alias, valores)
        if arreglo:
            piezas[i] = arreglo[0]
            cambios.append({"original": parte, "sugerido": arreglo[0], "motivo": arreglo[1]})

    sugerido = "".join(piezas)
    return {
        "campo": campo,
        "texto": original,
        "sugerido": sugerido if cambios else None,
        "cambios": cambios,
    }


def listar_canonicos(campo: str) -> list[str]:
    """Para que el frontend pueda ofrecer el listado completo al elegir."""
    if campo not in CAMPOS:
        raise BadRequestError(f"Campo desconocido: se esperaba uno de {', '.join(CAMPOS)}")
    return _catalogo(campo)[1]


def registrar_alias(campo: str, alias: str, canonico: str) -> dict:
    """Deja guardada una equivalencia para que la próxima vez se sugiera sola."""
    if campo not in CAMPOS:
        raise BadRequestError(f"Campo desconocido: se esperaba uno de {', '.join(CAMPOS)}")

    alias, canonico = _normalizar(alias), _normalizar(canonico)
    if not alias or not canonico:
        raise BadRequestError("Hacen falta el valor a corregir y el valor correcto")
    if alias == canonico:
        raise BadRequestError("El valor a corregir y el correcto son el mismo")

    fila = (
        supabase.table("valores_canonicos")
        .select("id")
        .eq("campo", campo)
        .eq("valor", canonico)
        .execute()
    ).data
    if not fila:
        fila = (
            supabase.table("valores_canonicos")
            .insert({"campo": campo, "valor": canonico})
            .execute()
        ).data

    (
        supabase.table("alias_valores")
        .upsert(
            {"campo": campo, "alias": alias, "canonico_id": fila[0]["id"]},
            on_conflict="campo,alias",
        )
        .execute()
    )
    limpiar_cache()
    return {"campo": campo, "alias": alias, "canonico": canonico}
