import pytest

from app.core.exceptions import TooManyRequestsError
from app.core.rate_limit import verificar_rate_limit


def test_permite_intentos_dentro_del_limite():
    clave = "ip-dentro-del-limite"
    for _ in range(5):
        verificar_rate_limit(clave, max_intentos=5, ventana_segundos=60)


def test_bloquea_al_superar_el_limite():
    clave = "ip-supera-el-limite"
    for _ in range(5):
        verificar_rate_limit(clave, max_intentos=5, ventana_segundos=60)

    with pytest.raises(TooManyRequestsError):
        verificar_rate_limit(clave, max_intentos=5, ventana_segundos=60)


def test_intentos_no_se_mezclan_entre_claves_distintas():
    for _ in range(5):
        verificar_rate_limit("ip-a", max_intentos=5, ventana_segundos=60)

    # otra clave (otra IP) no se ve afectada por los intentos de "ip-a"
    verificar_rate_limit("ip-b", max_intentos=5, ventana_segundos=60)
