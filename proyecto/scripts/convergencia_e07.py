"""Estudio de convergencia en Δx = Δy (guía G04): ¿cuánto cambian las magnitudes
relevantes al refinar la grilla?

Para cada paso corre el pipeline completo (Δz fijo del YAML) y reporta T_max,
tiempo al pico, ΔT núcleo-superficie máx., e_V total y área corregida. Con
tres pasos en razón 2 estima el orden observado p y el valor extrapolado de
Richardson f* = f_fino + (f_fino − f_medio)/(2^p − 1), cuya distancia a la
malla fina es el error de discretización estimado.

Uso:
    python scripts/convergencia_e07.py
    python scripts/convergencia_e07.py --pasos 0.5 0.25 0.125 --set simulacion.duracion_h=96
"""

from __future__ import annotations

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import argparse
import math
import time
from pathlib import Path

import numpy as np
import yaml

from mcplan.caso import aplicar_sobrescrituras, ejecutar_pipeline, leer_config

RAIZ = Path(__file__).resolve().parents[1]
HORA = 3600.0


def metricas(r) -> dict[str, float]:
    s = r.simulacion
    i = int(np.nanargmax(s.T_max_C))
    dT = s.delta_T_C
    V = sum(f["V_malla_m3"] for f in r.volumetria)
    Vh = sum(f["V_h_m3"] for f in r.volumetria)
    return {
        "T_max_C": float(s.T_max_C[i]),
        "t_pico_h": s.tiempos_s[i] / HORA,
        "dT_max_C": float(np.nanmax(dT)),
        "e_V_pct": 100 * abs(Vh - V) / V,
        "area_m2": r.area_exterior_corregida_m2["total"],
    }


def richardson(f: list[float]) -> tuple[float, float]:
    """(orden observado p, valor extrapolado) con f = [grueso, medio, fino] en razón 2."""
    d1, d2 = f[0] - f[1], f[1] - f[2]
    if d1 == 0.0 or d2 == 0.0 or d1 / d2 <= 0.0:
        return math.nan, math.nan  # no monótono: no hay régimen asintótico
    p = math.log(d1 / d2) / math.log(2.0)
    return p, f[2] - d2 / (2.0**p - 1.0)  # f* = f_fino + (f_fino - f_medio)/(2^p - 1)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, default=RAIZ / "configs" / "e07_caso_base.yaml")
    ap.add_argument("--pasos", type=float, nargs="+", default=[0.5, 0.25, 0.125])
    ap.add_argument("--set", dest="sobrescrituras", action="append", default=["simulacion.duracion_h=96"],
                    metavar="CLAVE=VALOR")
    a = ap.parse_args(argv)
    base = yaml.safe_load(a.config.read_text(encoding="utf-8"))
    filas = []
    for paso in a.pasos:
        t0 = time.time()
        datos = aplicar_sobrescrituras(base, [*a.sobrescrituras, f"malla.paso_m={paso}"])
        r = ejecutar_pipeline(leer_config(datos, base_rutas=a.config.parent))
        filas.append({"paso_m": paso, "voxeles": int(np.prod(r.grilla.forma)), **metricas(r),
                      "segundos": time.time() - t0})
        f = filas[-1]
        print(f"Δx = {paso:<6g} {f['voxeles']:>10,} voxeles  T_max = {f['T_max_C']:.3f} °C "
              f"(t = {f['t_pico_h']:.1f} h)  ΔT = {f['dT_max_C']:.3f} °C  e_V = {f['e_V_pct']:.3f} %  "
              f"A = {f['area_m2']:.1f} m²  [{f['segundos']:.0f} s]", flush=True)
    if len(filas) == 3 and math.isclose(a.pasos[0], 2 * a.pasos[1]) and math.isclose(a.pasos[1], 2 * a.pasos[2]):
        print("\nRichardson (razón 2):")
        for clave in ("T_max_C", "dT_max_C", "area_m2"):
            serie = [f[clave] for f in filas]
            p, extrapolado = richardson(serie)
            if math.isnan(p):
                print(f"  {clave:9s}: no monótona {['%.3f' % x for x in serie]}: diferencias "
                      f"{abs(serie[0] - serie[1]):.3f} y {abs(serie[1] - serie[2]):.3f}")
            else:
                print(f"  {clave:9s}: p = {p:.2f}, extrapolado = {extrapolado:.3f}, "
                      f"error estimado de la malla fina = {abs(serie[2] - extrapolado):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
