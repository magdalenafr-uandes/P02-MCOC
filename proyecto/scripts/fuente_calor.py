"""Muestra la fuente de calor medida Q(t) y su curva adiabática θ(t) (MAPA:fuente-medida).

Lee ``data/hidratacion/source_terms.txt`` (datos del profesor, 8 probetas),
imprime por probeta el pico de Q, el calor total y la elevación adiabática
θ = ∫Q dt/(ρ cp), y guarda una figura que compara con la curva pedagógica
anterior (θ∞ = 45 K, τ = 30 h).

Uso (desde proyecto/):
    python scripts/fuente_calor.py
    python scripts/fuente_calor.py --rho 2400 --cp 970
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from mcplan.caso.fuente_calor import MEDIA, elevacion_adiabatica, leer_fuente

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--archivo", type=Path, default=RAIZ / "data" / "hidratacion" / "source_terms.txt")
    p.add_argument("--rho", type=float, default=2400.0, help="densidad del hormigón [kg/m³]")
    p.add_argument("--cp", type=float, default=970.0, help="calor específico [J/(kg K)]")
    p.add_argument("--salida", type=Path, default=RAIZ / "results" / "figures" / "fuente_calor_medida.png")
    a = p.parse_args()

    serie = leer_fuente(a.archivo)
    rho_cp = a.rho * a.cp
    print(f"Archivo: {a.archivo.name}  SHA-256 {serie.sha256}")
    print(f"ρ·cp = {rho_cp:.3e} J/(m³ K);  θ = ∫Q dt / (ρ·cp)")
    print(f"{'curva':8s} {'Q pico':>8s} {'a las':>6s} {'E total':>9s} {'θ 24 h':>7s} {'θ 72 h':>7s} {'θ total':>8s}")
    print(f"{'':8s} {'[W/m³]':>8s} {'[h]':>6s} {'[MJ/m³]':>9s} {'[K]':>7s} {'[K]':>7s} {'[K]':>8s}")
    curvas = {}
    for n in (*serie.nombres, MEDIA):
        Q = serie.curva(n)
        t, th = elevacion_adiabatica(serie.t_h, Q, rho_cp)
        curvas[n] = (Q, np.array(t), np.array(th))
        j = int(np.argmax(Q))
        print(f"{n:8s} {Q[j]:8.0f} {serie.t_h[j]:6.1f} {th[-1] * rho_cp / 1e6:9.1f} "
              f"{np.interp(24, t, th):7.1f} {np.interp(72, t, th):7.1f} {th[-1]:8.1f}")
    print("Curva pedagógica anterior: θ∞ = 45 K, τ = 30 h (θ 72 h = 40,9 K).")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.6))
    for n, (Q, t, th) in curvas.items():
        estilo = dict(color="k", lw=2.2, zorder=3) if n == MEDIA else dict(lw=0.9, alpha=0.75)
        ax1.plot(serie.t_h, Q, label=n, **estilo)
        ax2.plot(t, th, label=n, **estilo)
    tt = np.linspace(0, serie.t_h[-1], 400)
    ax2.plot(tt, 45.0 * -np.expm1(-tt / 30.0), "r--", lw=1.6, label="pedagógica 45 K")
    ax1.set(xlabel="t [h]", ylabel="Q [W/m³]", title="Fuente medida Q(t) (8 probetas)")
    ax2.set(xlabel="t [h]", ylabel="θ [K]", title=f"Elevación adiabática θ = ∫Q dt/(ρ cp), ρcp = {rho_cp:.2e}")
    for ax in (ax1, ax2):
        ax.grid(alpha=0.3)
    ax2.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    a.salida.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(a.salida, dpi=150)
    print(f"Figura: {a.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
