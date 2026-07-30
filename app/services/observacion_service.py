from app.database import supabase
from app.models.observacion import ObservacionCreate
from app.core.exceptions import InternalError
from uuid import UUID
from datetime import date, datetime, timezone
from app.services.auditoria_service import registrar_evento


def listar_observaciones(chofer_id: str) -> list:
    resultado = (
        supabase.table("observaciones")
        .select("*")
        .eq("chofer_id", chofer_id)
        .order("anio", desc=True)
        .order("mes", desc=True)
        .execute()
    )
    return resultado.data


def guardar_observacion(chofer_id: str, datos: ObservacionCreate, usuario_id: UUID) -> dict:
    hoy = date.today()
    mes = hoy.month
    anio = hoy.year

    existente = (
        supabase.table("observaciones")
        .select("*")
        .eq("chofer_id", chofer_id)
        .eq("mes", mes)
        .eq("anio", anio)
        .execute()
    )

    if existente.data:
        resultado = (
            supabase.table("observaciones")
            .update({
                "observacion": datos.observacion,
                "actualizado_en": datetime.now(timezone.utc).isoformat(),
            })
            .eq("chofer_id", chofer_id)
            .eq("mes", mes)
            .eq("anio", anio)
            .execute()
        )

        registrar_evento(
            usuario_id=usuario_id,
            tipo_accion="edicion",
            entidad="observacion",
            entidad_id=resultado.data[0]["id"],
            detalle=f"Observación actualizada para chofer {chofer_id}",
        )

        return resultado.data[0]
    else:
        nueva = {
            "chofer_id": chofer_id,
            "observacion": datos.observacion,
            "mes": mes,
            "anio": anio,
            "creado_por": str(usuario_id),
        }

        resultado = supabase.table("observaciones").insert(nueva).execute()

        if not resultado.data:
            raise InternalError("No se pudo guardar la observación")

        registrar_evento(
            usuario_id=usuario_id,
            tipo_accion="alta",
            entidad="observacion",
            entidad_id=resultado.data[0]["id"],
            detalle=f"Observación creada para chofer {chofer_id}",
        )

        return resultado.data[0]
