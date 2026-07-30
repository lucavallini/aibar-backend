def upper_fields(data: dict, *campos: str) -> dict:
    for campo in campos:
        if data.get(campo):
            data[campo] = data[campo].upper()
    return data
