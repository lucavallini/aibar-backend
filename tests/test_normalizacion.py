"""El catálogo vive en la base, así que estos tests lo reemplazan por uno en memoria."""

import pytest

from app.core.exceptions import BadRequestError
from app.services import normalizacion_service as srv

LUGARES = {
    "l1": "VENADO TUERTO",
    "l2": "RUFINO",
    "l3": "TEODELINA",
    "l4": "BELL VILLE",
    "l5": "BANDERA",
    "l6": "BANDERALO",
}
ALIAS_LUGAR = [
    {"alias": "VT", "canonico_id": "l1"},
    {"alias": "VENADO", "canonico_id": "l1"},
]
CARGAS = {"c1": "CEREAL", "c2": "CONTENEDOR"}
ALIAS_CARGA = [{"alias": "CAREAL", "canonico_id": "c1"}]


class _Consulta:
    def __init__(self, filas):
        self._filas = filas

    def select(self, *_):
        return self

    def eq(self, columna, valor):
        self._campo = valor
        return self

    def execute(self):
        return type("R", (), {"data": self._filas(self._campo)})()


class _Base:
    def table(self, nombre):
        if nombre == "valores_canonicos":
            return _Consulta(
                lambda campo: [
                    {"id": k, "valor": v}
                    for k, v in (LUGARES if campo == "lugar" else CARGAS).items()
                ]
            )
        return _Consulta(lambda campo: ALIAS_LUGAR if campo == "lugar" else ALIAS_CARGA)


@pytest.fixture(autouse=True)
def base(monkeypatch):
    monkeypatch.setattr(srv, "supabase", _Base())
    srv.limpiar_cache()
    yield
    srv.limpiar_cache()


def test_un_alias_conocido_se_sugiere():
    r = srv.sugerir("lugar", "VT")
    assert r["sugerido"] == "VENADO TUERTO"
    assert r["cambios"] == [{"original": "VT", "sugerido": "VENADO TUERTO", "motivo": "conocido"}]


def test_un_valor_ya_correcto_no_sugiere_nada():
    assert srv.sugerir("lugar", "RUFINO")["sugerido"] is None


def test_un_typo_se_detecta_por_parecido():
    r = srv.sugerir("lugar", "TEDODELINA")
    assert r["sugerido"] == "TEODELINA"
    assert r["cambios"][0]["motivo"] == "parecido"


def test_corrige_cada_pueblo_del_itinerario_y_conserva_los_separadores():
    r = srv.sugerir("lugar", "VT, TEDODELINA Y RUFINO")
    assert r["sugerido"] == "VENADO TUERTO, TEODELINA Y RUFINO"
    assert len(r["cambios"]) == 2


def test_respeta_la_barra_como_separador():
    assert srv.sugerir("lugar", "VT/RUFINO")["sugerido"] == "VENADO TUERTO/RUFINO"


def test_la_e_tambien_separa():
    r = srv.sugerir("lugar", "RUFINO E TEDODELINA")
    assert r["sugerido"] == "RUFINO E TEODELINA"


def test_dos_pueblos_parecidos_pero_distintos_no_se_confunden():
    """BANDERA y BANDERALO existen los dos: ninguno es un typo del otro."""
    assert srv.sugerir("lugar", "BANDERALO")["sugerido"] is None
    assert srv.sugerir("lugar", "BANDERA")["sugerido"] is None


def test_un_pueblo_desconocido_no_se_fuerza():
    """Aparecen destinos nuevos: el campo los tiene que aceptar sin sugerir nada."""
    assert srv.sugerir("lugar", "PUEBLO INEXISTENTE DEL SUR")["sugerido"] is None


def test_normaliza_mayusculas_y_espacios_sobrantes():
    r = srv.sugerir("lugar", "  vt   ,  rufino  ")
    assert r["texto"] == "VT , RUFINO"
    assert r["sugerido"] == "VENADO TUERTO , RUFINO"


def test_texto_vacio_no_sugiere_nada():
    for vacio in ("", "   ", None):
        assert srv.sugerir("lugar", vacio)["sugerido"] is None


def test_las_cargas_usan_su_propio_catalogo():
    assert srv.sugerir("carga", "CAREAL")["sugerido"] == "CEREAL"
    # VT es un lugar, no una carga: en este campo no significa nada.
    assert srv.sugerir("carga", "VT")["sugerido"] is None


def test_un_campo_que_no_existe_es_un_error_de_pedido():
    with pytest.raises(BadRequestError):
        srv.sugerir("patente", "AA123BB")


def test_listar_canonicos_devuelve_el_catalogo_ordenado():
    assert srv.listar_canonicos("lugar") == sorted(LUGARES.values())


def test_un_alias_gana_aunque_tambien_figure_como_canonico(monkeypatch):
    """Pasó en el seed: 'VT' tenía 287 usos y entró al catálogo además de como alias."""
    sucio = dict(LUGARES, l9="VT")
    monkeypatch.setattr(
        srv,
        "supabase",
        type(
            "B",
            (),
            {
                "table": lambda self, n: _Consulta(
                    (lambda campo: [{"id": k, "valor": v} for k, v in sucio.items()])
                    if n == "valores_canonicos"
                    else (lambda campo: ALIAS_LUGAR)
                )
            },
        )(),
    )
    srv.limpiar_cache()
    assert srv.sugerir("lugar", "VT")["sugerido"] == "VENADO TUERTO"


def test_un_lugar_ausente_del_catalogo_se_confunde_con_el_parecido(monkeypatch):
    """Por qué el catálogo tiene que incluir todos los lugares que ya se usan.

    BANDERALO existe de verdad, pero si falta del catálogo la comparación por
    parecido lo empareja con BANDERA. El seed cargaba sólo los lugares con tres
    o más usos y por eso los poco frecuentes salían 'corregidos' contra otro
    pueblo. La defensa es de datos, no de código: cargarlos todos.
    """
    incompleto = {k: v for k, v in LUGARES.items() if v != "BANDERALO"}
    monkeypatch.setattr(
        srv,
        "supabase",
        type(
            "B",
            (),
            {
                "table": lambda self, n: _Consulta(
                    (lambda campo: [{"id": k, "valor": v} for k, v in incompleto.items()])
                    if n == "valores_canonicos"
                    else (lambda campo: ALIAS_LUGAR)
                )
            },
        )(),
    )
    srv.limpiar_cache()
    assert srv.sugerir("lugar", "BANDERALO")["sugerido"] == "BANDERA"
