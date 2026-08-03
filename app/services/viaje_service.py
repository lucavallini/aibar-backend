from app.database import supabase
from app.models.viaje import ViajeCreate, ViajeEditar, ViajeCancelar, ViajeFinalizar, ViajeOut, ViajeReanudar
from app.services.auditoria_service import registrar_evento
from app.core.exceptions import NotFoundError, BadRequestError, ConflictError, InternalError
from uuid import UUID
from datetime import datetime, timedelta, timezone
from app.database import supabase, armar_respuesta_paginada
from app.utils.fields import upper_fields

def listar_viajes(chofer_id: str = None, estado: str = None, dias: int = None, patente: str = None, fecha_desde: str = None, fecha_hasta: str = None, empresa_id: str = None, pagina: int = 1, tamano_pagina: int = 20) -> dict:
    query = supabase.table("viajes").select("*", count="exact")

    if chofer_id:
        query = query.eq("chofer_id", chofer_id)

    if estado:
        query = query.eq("estado", estado)

    if dias:
        cutoff = datetime.now(timezone.utc) - timedelta(days=dias)
        query = query.gte("fecha_inicio", cutoff.isoformat())

    if fecha_desde:
        query = query.gte("fecha_inicio", fecha_desde)
    if fecha_hasta:
        query = query.lte("fecha_inicio", fecha_hasta + "T23:59:59")

    if patente:
        camiones_data = supabase.table("camiones").select("id").ilike("patente", f"%{patente}%").execute()
        camion_ids = [c["id"] for c in camiones_data.data]
        if camion_ids:
            ids_str = ",".join(camion_ids)
            query = query.or_(f"camion_id.in.({ids_str}),camion_id_2.in.({ids_str})")
        else:
            query = query.eq("id", "00000000-0000-0000-0000-000000000000")

    if empresa_id:
        choferes_data = supabase.table("choferes").select("id").eq("empresa_id", empresa_id).execute()
        camiones_data = supabase.table("camiones").select("id").eq("empresa_id", empresa_id).execute()
        acoplados_data = supabase.table("acoplados").select("id").eq("empresa_id", empresa_id).execute()
        chofer_ids = [c["id"] for c in choferes_data.data]
        camion_ids = [c["id"] for c in camiones_data.data]
        acoplado_ids = [c["id"] for c in acoplados_data.data]
        or_clauses = []
        if chofer_ids:
            or_clauses.append(f"chofer_id.in.({','.join(chofer_ids)})")
        if camion_ids:
            or_clauses.append(f"camion_id.in.({','.join(camion_ids)})")
        if acoplado_ids:
            ids_str = ",".join(acoplado_ids)
            or_clauses.append(f"camion_id_2.in.({ids_str})")
        if not or_clauses:
            query = query.eq("id", "00000000-0000-0000-0000-000000000000")
        else:
            query = query.or_(",".join(or_clauses))

    query = query.order("fecha_inicio", desc=True)

    result = armar_respuesta_paginada(query, pagina, tamano_pagina)

    ids_vueltas = set()
    ids_a_buscar = set()
    for viaje in result["items"]:
        if viaje.get("viaje_vuelta_id"):
            ids_vueltas.add(viaje["viaje_vuelta_id"])
            ids_a_buscar.add(viaje["viaje_vuelta_id"])

    if ids_a_buscar:
        vueltas = supabase.table("viajes").select("*").in_("id", list(ids_a_buscar)).execute()
        vueltas_map = {v["id"]: v for v in vueltas.data}
        for viaje in result["items"]:
            vid = viaje.get("viaje_vuelta_id")
            if vid and vid in vueltas_map:
                viaje["viaje_vuelta"] = vueltas_map[vid]

    result["items"] = [v for v in result["items"] if v["id"] not in ids_vueltas]
    return result


def _obtener_nombre_chofer(chofer_id: str) -> str:
    r = supabase.table("choferes").select("nombre_completo").eq("id", chofer_id).execute()
    return r.data[0]["nombre_completo"] if r.data else "Desconocido"


def _obtener_nombre_usuario(usuario_id: str) -> str:
    r = supabase.table("usuarios").select("nombre_completo").eq("id", usuario_id).execute()
    return r.data[0]["nombre_completo"] if r.data else "Desconocido"


def _obtener_viaje(viaje_id: str) -> dict:
    resultado = supabase.table("viajes").select("*").eq("id", viaje_id).execute()
    if not resultado.data:
        raise NotFoundError("Viaje no encontrado")
    return resultado.data[0]


def _tabla_unidad(unidad_id: str) -> str:
    camion = supabase.table("camiones").select("id").eq("id", unidad_id).execute()
    if camion.data:
        return "camiones"
    acoplado = supabase.table("acoplados").select("id").eq("id", unidad_id).execute()
    if acoplado.data:
        return "acoplados"
    return None


def _reservar_unidad(unidad_id, estado_nuevo: str) -> None:
    if not unidad_id:
        return
    unidad_id = str(unidad_id)
    tabla = _tabla_unidad(unidad_id)
    if not tabla:
        raise BadRequestError("La unidad indicada no existe")

    resultado = (
        supabase.table(tabla)
        .update({"estado": estado_nuevo})
        .eq("id", unidad_id)
        .eq("estado", "disponible")
        .execute()
    )
    if not resultado.data:
        nombre = "El chasis" if tabla == "camiones" else "El acoplado"
        raise ConflictError(
            f"{nombre} seleccionado ya no está disponible. Actualizá la pantalla e intentá de nuevo."
        )


def _liberar_unidad(unidad_id, excepto: str = None) -> None:
    if not unidad_id:
        return
    unidad_id = str(unidad_id)
    tabla = _tabla_unidad(unidad_id)
    if not tabla:
        return

    en_uso = (
        supabase.table("viajes")
        .select("id")
        .in_("estado", ["pendiente", "en_curso"])
        .or_(f"camion_id.eq.{unidad_id},camion_id_2.eq.{unidad_id}")
        .execute()
    )
    if excepto:
        en_uso.data = [v for v in en_uso.data if v["id"] != excepto]
    if en_uso.data:
        return

    supabase.table(tabla).update({"estado": "disponible"}).eq("id", unidad_id).in_(
        "estado", ["esperando_iniciar_viaje", "viajando"]
    ).execute()


def _unidad_en_viaje(unidad_id: str) -> bool:
    if not unidad_id:
        return False
    en_uso = (
        supabase.table("viajes")
        .select("id")
        .in_("estado", ["pendiente", "en_curso"])
        .or_(f"camion_id.eq.{unidad_id},camion_id_2.eq.{unidad_id}")
        .execute()
    )
    return bool(en_uso.data)


def crear_viaje(datos: ViajeCreate, asignado_por: UUID) -> dict:
    chofer_id_str = str(datos.chofer_id)

    reserva = (
        supabase.table("choferes")
        .update({"estado": "esperando_iniciar_viaje"})
        .eq("id", chofer_id_str)
        .eq("estado", "disponible")
        .execute()
    )

    if not reserva.data:
        raise ConflictError(
            "El chofer ya no está disponible. Actualizá la pantalla e intentá de nuevo."
        )

    unidades_reservadas = []
    try:
        for campo in ("camion_id", "camion_id_2"):
            valor = getattr(datos, campo, None)
            if valor:
                _reservar_unidad(valor, "esperando_iniciar_viaje")
                unidades_reservadas.append(str(valor))
    except Exception:
        supabase.table("choferes").update({"estado": "disponible"}).eq("id", chofer_id_str).execute()
        for unidad_id in unidades_reservadas:
            _liberar_unidad(unidad_id, excepto=None)
        raise

    nuevo_viaje = datos.model_dump(mode="json", exclude_unset=True)
    upper_fields(nuevo_viaje, "origen", "destino", "cliente", "carga")
    nuevo_viaje["asignado_por"] = str(asignado_por)
    if "camion_id_2" in nuevo_viaje and nuevo_viaje["camion_id_2"] is None:
        nuevo_viaje.pop("camion_id_2")
    if "viaje_vuelta_id" in nuevo_viaje and nuevo_viaje["viaje_vuelta_id"] is None:
        nuevo_viaje.pop("viaje_vuelta_id")

    resultado = supabase.table("viajes").insert(nuevo_viaje).execute()

    if not resultado.data:
        supabase.table("choferes").update({"estado": "disponible"}).eq("id", chofer_id_str).execute()
        for unidad_id in unidades_reservadas:
            _liberar_unidad(unidad_id, excepto=None)
        raise InternalError("No se pudo crear el viaje")

    viaje_creado = resultado.data[0]

    chofer_nombre = _obtener_nombre_chofer(str(datos.chofer_id))
    usuario_nombre = _obtener_nombre_usuario(str(asignado_por))

    registrar_evento(
        usuario_id=asignado_por,
        tipo_accion="alta",
        entidad="viaje",
        entidad_id=viaje_creado["id"],
        detalle=f"Viaje creado: {datos.origen} -> {datos.destino} | Chofer: {chofer_nombre} | Por: {usuario_nombre}",
    )

    return viaje_creado

def editar_viaje(viaje_id: str, datos: ViajeEditar, usuario_id: UUID) -> dict:
    viaje = _obtener_viaje(viaje_id)

    if viaje["estado"] not in ("pendiente", "en_curso"):
        raise BadRequestError("Solo se pueden editar viajes pendientes o en curso")

    cambios = datos.model_dump(exclude_unset=True, mode="json")
    upper_fields(cambios, "origen", "destino", "cliente", "carga")

    if not cambios:
        raise BadRequestError("No se enviaron campos para actualizar")

    nuevo_camion_id_2 = cambios.get("camion_id_2")
    viejo_camion_id_2 = viaje.get("camion_id_2")
    reservo_nueva = False
    if "camion_id_2" in cambios and nuevo_camion_id_2:
        estado_nuevo = "viajando" if viaje["estado"] == "en_curso" else "esperando_iniciar_viaje"
        _reservar_unidad(nuevo_camion_id_2, estado_nuevo)
        reservo_nueva = True

    resultado = supabase.table("viajes").update(cambios).eq("id", viaje_id).execute()
    viaje_editado = resultado.data[0]

    if reservo_nueva and str(nuevo_camion_id_2) != str(viejo_camion_id_2):
        _liberar_unidad(viejo_camion_id_2, excepto=viaje_id)

    registrar_evento(
        usuario_id=usuario_id,
        tipo_accion="edicion",
        entidad="viaje",
        entidad_id=viaje_id,
        detalle=f"Campos modificados: {', '.join(cambios.keys())}",
    )

    return viaje_editado


def reanudar_viaje(viaje_id: str, datos: ViajeReanudar, usuario_id: UUID) -> dict:
    viaje = _obtener_viaje(viaje_id)

    if viaje["estado"] != "cancelado":
        raise BadRequestError("Solo se pueden reanudar viajes cancelados")

    cambios = {}
    for campo in ("origen", "destino", "cliente", "carga"):
        valor = getattr(datos, campo, None)
        if valor is not None:
            cambios[campo] = valor
    upper_fields(cambios, "origen", "destino", "cliente", "carga")
    for campo in ("camion_id", "camion_id_2"):
        valor = getattr(datos, campo, None)
        if valor is not None:
            cambios[campo] = str(valor)
    for campo in ("tarifa", "fecha_inicio"):
        valor = getattr(datos, campo, None)
        if valor is not None:
            cambios[campo] = valor.isoformat() if campo == "fecha_inicio" else valor

    cambios["estado"] = "pendiente"
    cambios["motivo_cancelacion"] = None

    nuevo_chofer_id = str(datos.chofer_id) if datos.chofer_id else viaje["chofer_id"]
    if nuevo_chofer_id != viaje["chofer_id"]:
        reserva = (
            supabase.table("choferes")
            .update({"estado": "esperando_iniciar_viaje"})
            .eq("id", nuevo_chofer_id)
            .eq("estado", "disponible")
            .execute()
        )
        if not reserva.data:
            raise ConflictError("El chofer seleccionado no está disponible")
        cambios["chofer_id"] = nuevo_chofer_id
    else:
        supabase.table("choferes").update({"estado": "esperando_iniciar_viaje"}).eq("id", viaje["chofer_id"]).execute()

    unidades_nuevas = []
    try:
        for campo in ("camion_id", "camion_id_2"):
            valor = cambios.get(campo)
            if valor:
                _reservar_unidad(valor, "esperando_iniciar_viaje")
                unidades_nuevas.append(str(valor))
    except Exception:
        if nuevo_chofer_id != viaje["chofer_id"]:
            supabase.table("choferes").update({"estado": "disponible"}).eq("id", nuevo_chofer_id).execute()
        else:
            supabase.table("choferes").update({"estado": "disponible"}).eq("id", viaje["chofer_id"]).execute()
        for unidad_id in unidades_nuevas:
            _liberar_unidad(unidad_id, excepto=None)
        raise

    resultado = supabase.table("viajes").update(cambios).eq("id", viaje_id).execute()

    for campo in ("camion_id", "camion_id_2"):
        if campo in cambios and cambios[campo] != viaje.get(campo):
            _liberar_unidad(viaje.get(campo), excepto=viaje_id)

    registrar_evento(
        usuario_id=usuario_id,
        tipo_accion="reanudacion",
        entidad="viaje",
        entidad_id=viaje_id,
        detalle=f"Viaje reanudado. Campos modificados: {', '.join(c for c in cambios if c not in ('estado', 'motivo_cancelacion'))}",
    )

    return resultado.data[0]


def cancelar_viaje(viaje_id: str, datos: ViajeCancelar, usuario_id: UUID) -> dict:
    viaje = _obtener_viaje(viaje_id)

    if viaje["estado"] in ("finalizado", "cancelado"):
        raise BadRequestError("Este viaje ya no se puede cancelar")

    resultado = (
        supabase.table("viajes")
        .update({"estado": "cancelado", "motivo_cancelacion": datos.motivo_cancelacion.upper() if datos.motivo_cancelacion else datos.motivo_cancelacion})
        .eq("id", viaje_id)
        .execute()
    )

    # El chofer y las unidades vuelven a estar disponibles
    supabase.table("choferes").update({"estado": "disponible"}).eq("id", viaje["chofer_id"]).execute()
    _liberar_unidad(viaje.get("camion_id"), excepto=viaje_id)
    _liberar_unidad(viaje.get("camion_id_2"), excepto=viaje_id)

    registrar_evento(
        usuario_id=usuario_id,
        tipo_accion="cancelacion",
        entidad="viaje",
        entidad_id=viaje_id,
        detalle=f"Motivo: {datos.motivo_cancelacion}",
    )

    return resultado.data[0]


def iniciar_viaje(viaje_id: str, usuario_id: UUID) -> dict:
    viaje = _obtener_viaje(viaje_id)

    if viaje["estado"] != "pendiente":
        raise BadRequestError("Solo se pueden iniciar viajes pendientes")

    resultado = supabase.table("viajes").update({"estado": "en_curso"}).eq("id", viaje_id).execute()

    supabase.table("choferes").update({"estado": "viajando"}).eq("id", viaje["chofer_id"]).execute()

    for campo in ("camion_id", "camion_id_2"):
        unidad_id = viaje.get(campo)
        if not unidad_id:
            continue
        tabla = _tabla_unidad(str(unidad_id))
        if tabla:
            supabase.table(tabla).update({"estado": "viajando"}).eq("id", str(unidad_id)).in_(
                "estado", ["disponible", "esperando_iniciar_viaje"]
            ).execute()

    registrar_evento(
        usuario_id=usuario_id,
        tipo_accion="edicion",
        entidad="viaje",
        entidad_id=viaje_id,
        detalle="Viaje pasado a en_curso",
    )

    return resultado.data[0]


def agregar_vuelta(viaje_id: str, datos: ViajeCreate, asignado_por: UUID) -> dict:
    viaje_original = _obtener_viaje(viaje_id)

    if viaje_original.get("solo_ida"):
        raise BadRequestError("Este viaje es solo de ida, no se puede agregar vuelta")

    if viaje_original["viaje_vuelta_id"]:
        raise BadRequestError("Este viaje ya tiene una vuelta asignada")

    if viaje_original["estado"] not in ("pendiente", "en_curso", "finalizado"):
        raise BadRequestError("No se puede agregar vuelta a un viaje cancelado")

    chofer_id_str = str(datos.chofer_id)

    if viaje_original["chofer_id"] != chofer_id_str:
        reserva = (
            supabase.table("choferes")
            .update({"estado": "esperando_iniciar_viaje"})
            .eq("id", chofer_id_str)
            .eq("estado", "disponible")
            .execute()
        )
        if not reserva.data:
            raise ConflictError("El chofer de la vuelta no está disponible")

    unidades_reservadas = []
    try:
        for campo in ("camion_id", "camion_id_2"):
            valor = getattr(datos, campo, None)
            if not valor:
                continue
            valor_str = str(valor)
            if viaje_original["estado"] != "finalizado" and valor_str in (
                str(viaje_original.get("camion_id")),
                str(viaje_original.get("camion_id_2")),
            ):
                continue
            _reservar_unidad(valor_str, "esperando_iniciar_viaje")
            unidades_reservadas.append(valor_str)
    except Exception:
        if viaje_original["chofer_id"] != chofer_id_str:
            supabase.table("choferes").update({"estado": "disponible"}).eq("id", chofer_id_str).execute()
        for unidad_id in unidades_reservadas:
            _liberar_unidad(unidad_id, excepto=None)
        raise

    nuevo_viaje = datos.model_dump(mode="json", exclude_unset=True)
    upper_fields(nuevo_viaje, "origen", "destino", "cliente", "carga")
    nuevo_viaje["asignado_por"] = str(asignado_por)
    nuevo_viaje.pop("viaje_vuelta_id", None)
    for campo in ("camion_id_2", "viaje_vuelta_id"):
        if campo in nuevo_viaje and nuevo_viaje[campo] is None:
            nuevo_viaje.pop(campo, None)

    resultado = supabase.table("viajes").insert(nuevo_viaje).execute()

    if not resultado.data:
        if viaje_original["chofer_id"] != chofer_id_str:
            supabase.table("choferes").update({"estado": "disponible"}).eq("id", chofer_id_str).execute()
        for unidad_id in unidades_reservadas:
            _liberar_unidad(unidad_id, excepto=None)
        raise InternalError("No se pudo crear el viaje de vuelta")

    viaje_vuelta_id = resultado.data[0]["id"]

    supabase.table("viajes").update({"viaje_vuelta_id": viaje_vuelta_id}).eq("id", viaje_id).execute()

    chofer_nombre = _obtener_nombre_chofer(str(datos.chofer_id))
    usuario_nombre = _obtener_nombre_usuario(str(asignado_por))

    registrar_evento(
        usuario_id=asignado_por,
        tipo_accion="edicion",
        entidad="viaje",
        entidad_id=viaje_id,
        detalle=f"Viaje de vuelta agregado: {datos.origen} -> {datos.destino} | Chofer: {chofer_nombre} | Por: {usuario_nombre}",
    )

    return resultado.data[0]


def calcular_rendimiento_combustible(chofer_id: str) -> dict:
    viajes = (
        supabase.table("viajes")
        .select("id, kms_recorridos")
        .eq("chofer_id", chofer_id)
        .eq("estado", "finalizado")
        .execute()
    )

    total_kms = sum(v["kms_recorridos"] or 0 for v in viajes.data)
    viaje_ids = [v["id"] for v in viajes.data]

    total_litros = 0
    if viaje_ids:
        cargas = (
            supabase.table("cargas_combustible")
            .select("litros")
            .in_("viaje_id", viaje_ids)
            .execute()
        )
        total_litros = sum(c["litros"] or 0 for c in cargas.data)

    rendimiento = round(total_kms / total_litros, 2) if total_litros > 0 else None
    litros_cien = round(total_litros / total_kms * 100, 2) if total_kms > 0 else None

    return {
        "chofer_id": chofer_id,
        "total_kms": total_kms,
        "total_litros": total_litros,
        "km_por_litro": rendimiento,
        "litros_100km": litros_cien,
    }


def finalizar_viaje(viaje_id: str, datos: ViajeFinalizar, usuario_id: UUID) -> dict:
    viaje = _obtener_viaje(viaje_id)

    if viaje["estado"] != "en_curso":
        raise BadRequestError("Solo se pueden finalizar viajes en curso")

    total_kms = datos.kms_recorridos + (datos.kms_descargado or 0)

    km_por_litro = None
    if datos.litros_combustible and datos.litros_combustible > 0:
        km_por_litro = round(total_kms / datos.litros_combustible, 2)

    cambios = {
        "estado": "finalizado",
        "fecha_fin": datos.fecha_fin.isoformat(),
        "kms_recorridos": total_kms,
        "kms_descargado": datos.kms_descargado,
        "litros_combustible": datos.litros_combustible,
        "km_por_litro": km_por_litro,
        "solo_ida": datos.solo_ida,
    }

    resultado = supabase.table("viajes").update(cambios).eq("id", viaje_id).execute()

    supabase.table("choferes").update({"estado": "disponible"}).eq("id", viaje["chofer_id"]).execute()
    _liberar_unidad(viaje.get("camion_id"), excepto=viaje_id)
    _liberar_unidad(viaje.get("camion_id_2"), excepto=viaje_id)

    detalle = f"Viaje finalizado, {datos.kms_recorridos} kms cargados"
    if datos.kms_descargado:
        detalle += f", {datos.kms_descargado} kms descargados"
    if datos.litros_combustible:
        detalle += f", {datos.litros_combustible} L"
    if km_por_litro:
        detalle += f", {km_por_litro} km/l"

    registrar_evento(
        usuario_id=usuario_id,
        tipo_accion="edicion",
        entidad="viaje",
        entidad_id=viaje_id,
        detalle=detalle,
    )

    return resultado.data[0]


