import uuid

from app.services.auditoria_service import registrar_evento


def test_registrar_evento_no_propaga_si_falla_el_insert(query, table):
    query.insert.return_value = query
    query.execute.side_effect = ConnectionError("timeout de red")

    registrar_evento(
        usuario_id=uuid.uuid4(),
        tipo_accion="alta",
        entidad="camion",
        entidad_id=uuid.uuid4(),
        detalle="no debería importar si esto falla",
    )
