"""Figura reproducible: solución numérica vs. solución analítica 1D.

Caso: barra de hormigón de 1 m, perfil inicial sinusoidal, Dirichlet T0 en
ambos extremos. Guarda la figura y reporta el error L_inf.

Uso:
    python scripts/verification_1d.py
    python scripts/verification_1d.py --salida results/figures/otra.png
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from mcplan.thermal import (
    CondicionBorde,
    PropiedadesTermicas,
    resolver_1d,
    solucion_sinusoidal,
)
from mcplan.thermal.solver1d import limite_estabilidad

RAIZ = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compara solver 1D con la solución analítica sinusoidal."
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=RAIZ / "results" / "figures" / "verificacion_1d.png",
        help="Ruta de la figura PNG.",
    )
    args = parser.parse_args()

    L = 1.0
    nx = 81
    T0 = 20.0
    A = 50.0
    propiedades = PropiedadesTermicas(k=2.22, rho=2400.0, cp=970.0)
    alpha = propiedades.alpha

    x = np.linspace(0.0, L, nx)
    dx = x[1] - x[0]

    borde = CondicionBorde("dirichlet", valor=T0)
    dt_objetivo = 0.40 * limite_estabilidad(propiedades, dx, borde, borde)
    t_final = 24.0 * 3600.0
    n_pasos = int(np.ceil(t_final / dt_objetivo))
    dt = t_final / n_pasos
    r = alpha * dt / dx**2

    T_inicial = T0 + A * np.sin(np.pi * x / L)
    T_inicial[0] = T0
    T_inicial[-1] = T0

    pasos = sorted({0, n_pasos // 4, n_pasos // 2, 3 * n_pasos // 4, n_pasos})
    inicio = time.perf_counter()
    resultado = resolver_1d(
        T_inicial,
        propiedades,
        dx,
        dt,
        n_pasos,
        borde,
        borde,
        pasos_guardado=set(pasos),
    )
    duracion = time.perf_counter() - inicio

    exacta_final = solucion_sinusoidal(x, t_final, alpha, T0, A, L)
    error = float(np.max(np.abs(resultado.T - exacta_final)))

    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    colores = plt.cm.viridis(np.linspace(0.05, 0.90, len(pasos)))

    for paso, color in zip(pasos, colores):
        t = paso * dt
        exacta = solucion_sinusoidal(x, t, alpha, T0, A, L)
        ax.plot(x, exacta, color=color, lw=2.0)
        ax.plot(
            x[::5],
            resultado.instantaneas[paso][::5],
            "o",
            color=color,
            ms=4.0,
            mfc="white",
            mew=1.0,
        )
        ax.annotate(
            f"{t / 3600:.0f} h",
            xy=(0.985, exacta[int(0.985 * (nx - 1))]),
            xytext=(5, 0),
            textcoords="offset points",
            fontsize=8,
            color=color,
            va="center",
        )

    ax.set_xlabel("x [m]")
    ax.set_ylabel("T [°C]")
    ax.set_title("Difusión 1D: numérica (marcadores) vs. analítica (líneas)")
    ax.grid(True, alpha=0.35)
    ax.text(
        0.02,
        0.03,
        (
            f"k={propiedades.k:g} W/(m·K), rho={propiedades.rho:g} kg/m³, "
            f"cp={propiedades.cp:g} J/(kg·K)\n"
            f"alpha={alpha:.3e} m²/s, dx={dx:.4f} m, dt={dt:.2f} s, r={r:.3f}\n"
            f"Error L_inf a t={t_final/3600:.0f} h: {error:.3e} °C"
        ),
        transform=ax.transAxes,
        fontsize=8.5,
        va="bottom",
        bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "0.7"},
    )

    args.salida.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(args.salida, dpi=180)
    plt.close(fig)

    print(f"Figura guardada: {args.salida}")
    print(f"nx={nx}, dx={dx:.6e} m, dt={dt:.6e} s, r={r:.5f}, n_pasos={n_pasos}")
    print(f"alpha={alpha:.6e} m²/s")
    print(f"Error L_inf a t={t_final/3600:.1f} h: {error:.6e} °C")
    print(f"Tiempo de cálculo: {duracion:.3f} s")


if __name__ == "__main__":
    main()
