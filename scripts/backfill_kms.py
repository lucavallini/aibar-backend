"""Trae a la base los kilómetros diarios que el proveedor todavía conserva.

Se corre a mano, una vez, y después se puede repetir sin miedo: lo ya guardado se saltea.
El proveedor conserva alrededor de seis meses, así que lo que no se traiga ahora se pierde
para siempre.

    python scripts/backfill_kms.py --dias 180
    python scripts/backfill_kms.py --dias 7 --patentes AH070HV,AF470HZ --simulacro

Va de a un día por consulta y con una pausa entre cada una: son varios miles de pedidos
contra la producción de un tercero del que no conocemos el límite de uso.
"""

import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import gc_client  # noqa: E402
from app.services.kms_diarios_service import (  # noqa: E402
    DIAS_RETENCION_PROVEEDOR,
    SIN_DATOS,
    dias_del_rango,
    dias_ya_guardados,
    guardar_dia,
    traer_dia,
)

PAUSA_POR_DEFECTO = 0.3


def parsear_argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dias", type=int, default=DIAS_RETENCION_PROVEEDOR,
                   help=f"cuántos días hacia atrás traer (por defecto {DIAS_RETENCION_PROVEEDOR})")
    p.add_argument("--patentes", default="", help="lista separada por comas; vacío es toda la flota")
    p.add_argument("--pausa", type=float, default=PAUSA_POR_DEFECTO,
                   help=f"segundos entre consultas (por defecto {PAUSA_POR_DEFECTO})")
    p.add_argument("--simulacro", action="store_true", help="consulta y muestra, pero no guarda nada")
    p.add_argument("--rehacer", action="store_true", help="vuelve a pedir los días ya guardados")
    return p.parse_args()


def main() -> int:
    args = parsear_argumentos()

    hasta = date.today() - timedelta(days=1)  # hoy todavía está en curso
    desde = hasta - timedelta(days=args.dias - 1)

    try:
        padron = {v["LicensePlate"]: v["VehicleId"] for v in gc_client.obtener_vehiculos()}
    except Exception as exc:
        print(f"No se pudo leer el padrón de unidades: {exc}")
        return 1

    pedidas = [p.strip().upper() for p in args.patentes.split(",") if p.strip()]
    unidades = {p: i for p, i in padron.items() if not pedidas or p in pedidas}

    faltantes = [p for p in pedidas if p not in padron]
    if faltantes:
        print(f"Estas patentes no están en el servicio de rastreo: {', '.join(faltantes)}\n")

    if not unidades:
        print("No hay unidades para procesar.")
        return 1

    dias = dias_del_rango(desde, hasta)
    print(f"Del {desde} al {hasta} ({len(dias)} días) por {len(unidades)} unidades.")
    print(f"{'Simulacro: no se guarda nada.' if args.simulacro else 'Guardando en kms_diarios.'}\n")

    totales = {"guardados": 0, "salteados": 0, "km": 0.0, SIN_DATOS: 0}
    comenzado = time.monotonic()

    for n, (patente, id_vehiculo) in enumerate(sorted(unidades.items()), start=1):
        ya = set() if args.rehacer or args.simulacro else dias_ya_guardados(patente, desde, hasta)
        pendientes = [d for d in dias if d not in ya]
        totales["salteados"] += len(dias) - len(pendientes)

        km_unidad = 0.0
        for dia in pendientes:
            datos = traer_dia(id_vehiculo, dia)
            if not datos:
                continue  # falló la consulta: queda pendiente para la próxima corrida

            if not args.simulacro:
                guardar_dia(patente, dia, datos)

            totales["guardados"] += 1
            if datos["estado"] == SIN_DATOS:
                totales[SIN_DATOS] += 1
            else:
                km_unidad += datos["km"]

            time.sleep(args.pausa)

        totales["km"] += km_unidad
        print(f"  [{n:>2}/{len(unidades)}] {patente:10} {len(pendientes):>4} días nuevos, "
              f"{len(dias) - len(pendientes):>4} ya estaban, {km_unidad:>10,.0f} km")

    minutos = (time.monotonic() - comenzado) / 60
    print(f"\nListo en {minutos:.1f} min.")
    print(f"  días guardados:  {totales['guardados']:,}")
    print(f"  días salteados:  {totales['salteados']:,}")
    print(f"  sin datos:       {totales[SIN_DATOS]:,} (el equipo no reportó: no es cero kilómetros)")
    print(f"  kilómetros:      {totales['km']:,.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
