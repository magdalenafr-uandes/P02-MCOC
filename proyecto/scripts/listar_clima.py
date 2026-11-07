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
from datetime import datetime, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from mcplan.caso.clima import leer_snapshot

RAIZ = Path(__file__).resolve().parents[1]


def cobertura(tiempos, inicio: datetime, fin: datetime) -> float:
    """Horas de [inicio, fin] dentro del rango del snapshot."""
    a, b = max(tiempos[0], inicio), min(tiempos[-1], fin)
    return max(0.0, (b - a).total_seconds() / 3600.0)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--carpeta", type=Path, default=RAIZ / "data" / "weather")
    p.add_argument("--inicio", type=datetime.fromisoformat, default=datetime(2026, 11, 27, 4),
                   help="Inicio de la obra (local).")
    p.add_argument("--dias", type=float, default=14.0)
    a = p.parse_args(argv)
    fin = a.inicio + timedelta(days=a.dias)
    total_h = a.dias * 24.0
    print(f"Ventana de la obra: {a.inicio:%Y-%m-%d %H:%M} -> {fin:%Y-%m-%d %H:%M} ({total_h:.0f} h)\n")
    print(f"{'snapshot':32s} {'tipo':26s} {'descargado':17s} {'datos':33s} {'cubre':>9s} {'anticip.':>9s}  huella")
    for carpeta in sorted(c for c in a.carpeta.iterdir() if (c / "metadata.json").is_file()):
        try:
            s = leer_snapshot(carpeta)
        except (ValueError, FileNotFoundError) as exc:
            print(f"{carpeta.name:32s} INVÁLIDO: {exc}")
            continue
        m = s.metadata
        descargado = datetime.fromisoformat(m["retrieved_at"])
        anticipacion = (a.inicio - descargado.replace(tzinfo=None)).total_seconds() / 86400.0
        h = cobertura(s.tiempos, a.inicio, fin)
        extra = ""
        desfase = a.inicio.year - s.tiempos[0].year
        if h == 0.0 and desfase > 0:  # otro año: sirve como análogo de las mismas fechas
            try:
                h_analogo = cobertura([t.replace(year=t.year + desfase) for t in s.tiempos], a.inicio, fin)
                extra = f"  (análogo con desplazar_anios: {desfase} -> {h_analogo:.0f} h)"
            except ValueError:
                pass
        print(f"{carpeta.name:32s} {m['kind']:26s} {descargado:%Y-%m-%d %H:%M} "
              f"{s.tiempos[0]:%Y-%m-%d %H:%M}..{s.tiempos[-1]:%m-%d %H:%M} "
              f"{h:4.0f}/{total_h:.0f} h {anticipacion:7.1f} d  {s.huella}{extra}")
    print("\nUn pronóstico cubre la ventana recién cuando se descarga a menos de ~16 días de la obra.\n"
          "La cola que falte se completa con 'clima.completar: respaldo' (p. ej. reanálisis de las\n"
          "mismas fechas) y la salida del pipeline declara cuántas horas vienen de cada fuente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
