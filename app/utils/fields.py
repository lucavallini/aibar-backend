def upper_fields(data: dict, *campos: str) -> dict:
    for campo in campos:
        if data.get(campo):
            data[campo] = data[campo].upper()
    return data


def normalizar_patente(patente: str | None) -> str:
    """Deja la patente comparable entre sistemas: sin espacios, guiones ni minúsculas."""
    if not patente:
        return ""
    return "".join(c for c in patente if c.isalnum()).upper()
