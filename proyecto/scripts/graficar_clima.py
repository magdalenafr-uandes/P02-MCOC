"""Muestra la metadata de un snapshot meteorológico y grafica sus series (E11).

Lee exactamente los archivos del snapshot (``metadata.json`` y el JSON de
Open-Meteo), sin pasar por el solver: es la evidencia de qué dato entra a la
condición de borde Robin (ver ``MAPA:temperatura-ambiente``,
``MAPA:viento-conveccion`` y ``MAPA:flujo-solar``).

Uso (desde proyecto/):
    python scripts/graficar_clima.py
    python scripts/graficar_clima.py --snapshot data/weather/2026-10-31T1807_historico
    python scripts/graficar_clima.py --inicio 2026-11-27T04:00 --dias 14
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
SNAPSHOT = RAIZ / "data" / "weather" / "2026-11-07T2001_pronostico"
VARIABLES = (
    ("temperature_2m", "T aire 2 m [°C]", "tab:red"),
    ("wind_speed_10m", "Viento 10 m [m/s]", "tab:blue"),
    ("shortwave_radiation", "Radiación global [W/m²]", "tab:orange"),
)


def leer_snapshot(carpeta: Path) -> tuple[dict, dict, Path]:
    meta = json.loads((carpeta / "metadata.json").read_text(encoding="utf-8"))
    datos = [p for p in sorted(carpeta.glob("*.json")) if p.name != "metadata.json"]
    if len(datos) != 1:
        raise SystemExit(f"Se esperaba un JSON de datos en {carpeta}, hay {len(datos)}.")
    return meta, json.loads(datos[0].read_text(encoding="utf-8")), datos[0]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    p.add_argument("--inicio", type=datetime.fromisoformat, default=datetime(2026, 11, 27, 4),
                   help="Inicio de la obra, para marcar la ventana simulada.")
    p.add_argument("--dias", type=float, default=14.0)
    p.add_argument("--salida", type=Path, default=RAIZ / "results" / "figures" / "e11_clima.png")
    a = p.parse_args()

    carpeta = a.snapshot if a.snapshot.is_absolute() else (Path.cwd() / a.snapshot)
    meta, datos, archivo = leer_snapshot(carpeta.resolve())

    print(f"Snapshot: {carpeta.name}")
    print(f"Archivo de datos: {archivo.name}")
    print("Metadata:")
    for clave, valor in meta.items():
        print(f"  {clave:15s} {valor}")

    horas = datos["hourly"]
    t = [datetime.fromisoformat(s) for s in horas["time"]]
    print(f"Rango: {t[0]:%Y-%m-%d %H:%M} -> {t[-1]:%Y-%m-%d %H:%M} ({len(t)} horas, hora local)")
    for var, nombre, _ in VARIABLES:
        v = [x for x in horas.get(var, []) if x is not None]
        if v:
            print(f"  {nombre:26s} min {min(v):7.1f}  media {sum(v)/len(v):7.1f}  max {max(v):7.1f}")

    fin = a.inicio + timedelta(days=a.dias)
    presentes = [v for v in VARIABLES if v[0] in horas]
    fig, ejes = plt.subplots(len(presentes), 1, figsize=(11, 2.6 * len(presentes)), sharex=True)
    ejes = list(ejes) if len(presentes) > 1 else [ejes]
    for ax, (var, nombre, color) in zip(ejes, presentes):
        ax.plot(t, horas[var], color=color, lw=1.2)
        ax.set_ylabel(nombre)
        ax.grid(alpha=0.3)
        ax.axvspan(a.inicio, fin, color="0.85", zorder=0)
    ejes[0].set_title(
        f"{meta.get('source', '')} · {meta.get('kind', '')} · descargado {meta.get('retrieved_at', '?')}\n"
        f"sitio ({meta.get('latitude')}, {meta.get('longitude')}) · celda del modelo "
        f"({meta.get('latitude_grid', '?')}, {meta.get('longitude_grid', '?')}) · gris = ventana de la obra",
        fontsize=9,
    )
    ejes[-1].set_xlabel("hora local")
    fig.autofmt_xdate()
    fig.tight_layout()
    a.salida.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(a.salida, dpi=150)
    print(f"Figura: {a.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
