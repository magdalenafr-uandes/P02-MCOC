"""Lista los snapshots meteorológicos y qué cubren de la ventana de la obra (G07).

Para cada carpeta de ``data/weather/``: tipo (pronóstico, reanálisis...),
modelo, fecha de descarga, rango de datos, huella SHA-256 y, respecto de la
ventana [inicio, inicio + días]: horas cubiertas y **anticipación** (cuántos
días antes de la obra se descargó). Los snapshots antiguos no se borran: son
la evidencia de qué se sabía en cada momento y permiten medir cómo cambia el
pronóstico con la anticipación.

Uso:
    python scripts/listar_clima.py
    python scripts/listar_clima.py --inicio 2026-11-27T04:00 --dias 14
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from mcplan.caso.clima import resumen_snapshots

RAIZ = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--carpeta", type=Path, default=RAIZ / "data" / "weather")
    p.add_argument("--inicio", type=datetime.fromisoformat, default=datetime(2026, 11, 27, 4),
                   help="Inicio de la obra (local).")
    p.add_argument("--dias", type=float, default=14.0)
    a = p.parse_args(argv)
    total_h = a.dias * 24.0
    print(f"Ventana de la obra: {a.inicio:%Y-%m-%d %H:%M}, {total_h:.0f} h\n")
    print(f"{'snapshot':32s} {'tipo':26s} {'descargado':17s} {'datos':33s} {'cubre':>9s} {'anticip.':>9s}  huella")
    for f in resumen_snapshots(a.carpeta, a.inicio, total_h * 3600.0):
        if "error" in f:
            print(f"{f['carpeta']:32s} INVÁLIDO: {f['error']}")
            continue
        extra = ""
        if f["desplazar_anios_analogo"]:
            extra = f"  (análogo con desplazar_anios: {f['desplazar_anios_analogo']} -> {f['cubre_analogo_h']:.0f} h)"
        print(f"{f['carpeta']:32s} {f['kind']:26s} {f['descargado'].replace('T', ' '):17s} "
              f"{f['desde'].replace('T', ' ')}..{f['hasta'][5:].replace('T', ' ')} "
              f"{f['cubre_h']:4.0f}/{total_h:.0f} h {f['anticipacion_d']:7.1f} d  {f['huella']}{extra}")
    print("\nUn pronóstico cubre la ventana recién cuando se descarga a menos de ~16 días de la obra.\n"
          "La cola que falte se completa con 'clima.completar: respaldo' (p. ej. reanálisis de las\n"
          "mismas fechas) y la salida del pipeline declara cuántas horas vienen de cada fuente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
