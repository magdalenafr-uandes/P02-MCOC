"""Figura reproducible: solución numérica vs. solución analítica 1D.

Caso: barra de hormigón de 1 m, perfil inicial sinusoidal, Dirichlet T0 en
ambos extremos, difusión pura (Qdot = 0). Guarda la figura y reporta el
error L_inf junto con los valores efectivos de dx, dt y r.

Estabilidad (ver docs/guia_estudio.md):

- Difusión pura / Dirichlet: r = alpha*dt/dx² <= 1/2, es decir
  dt <= dt_max = dx²/(2*alpha).
- Robin (si existiera ese borde): dt <= rho*cp*dx²/(2k + 2h*dx), restricción
  más estricta que incluye conducción y convección en el medio volumen de
  borde. El caso de verificación no usa Robin.

`--dt-scale` es el factor de seguridad aplicado a dt_max (defecto 0.40).
Con valores mayores que 1 el paso supera dt_max: el solver lanza ValueError
y el script termina con código de salida 3 tras reportar el rechazo (el
esquema explícito no integra ese caso; no hay gráfica de inestabilidad).

Uso:
    python scripts/verification_1d.py
    python scripts/verification_1d.py --nx 161 --dt-scale 0.8
    python scripts/verification_1d.py --salida results/figures/otra.png
"""

from __future__ import annotations

import argparse
import sys
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compara solver 1D con la solución analítica sinusoidal."
    )
    parser.add_argument(
        "--nx",
        type=int,
        default=81,
        help="Número de nodos de la malla (defecto 81; mínimo 3).",
    )
    parser.add_argument(
        "--dt-scale",
        type=float,
        default=0.40,
        help=(
            "Factor de seguridad sobre dt_max (defecto 0.40). "
            "Valores > 1 superan dt_max y el solver rechaza el paso."
        ),
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=RAIZ / "results" / "figures" / "verificacion_1d.png",
        help="Ruta de la figura PNG.",
    )
    args = parser.parse_args()

    if args.nx < 3:
        parser.error("--nx debe ser al menos 3.")
    if args.dt_scale <= 0.0 or not np.isfinite(args.dt_scale):
        parser.error("--dt-scale debe ser un número positivo finito.")

    L = 1.0
    T0 = 20.0
    A = 50.0
    propiedades = PropiedadesTermicas(k=2.22, rho=2400.0, cp=970.0)
    alpha = propiedades.alpha

    x = np.linspace(0.0, L, args.nx)
    dx = x[1] - x[0]

    borde = CondicionBorde("dirichlet", valor=T0)
    dt_max = limite_estabilidad(propiedades, dx, borde, borde)
    dt_objetivo = args.dt_scale * dt_max
    t_final = 24.0 * 3600.0
    n_pasos = int(np.ceil(t_final / dt_objetivo))
    dt = t_final / n_pasos
    r = alpha * dt / dx**2

    print(f"nx={args.nx}, dx={dx:.6e} m, dt_max={dt_max:.6e} s")
    print(
        f"dt_scale={args.dt_scale:g} -> dt_objetivo={dt_objetivo:.6e} s, "
        f"n_pasos={n_pasos}, dt efectivo={dt:.6e} s, r={r:.5f}"
    )

    T_inicial = T0 + A * np.sin(np.pi * x / L)
    T_inicial[0] = T0
    T_inicial[-1] = T0

    pasos = sorted({0, n_pasos // 4, n_pasos // 2, 3 * n_pasos // 4, n_pasos})
    inicio = time.perf_counter()
    try:
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
    except ValueError as error:
        print(f"RECHAZADO: {error}")
        print(
            f"El paso dt={dt:.6e} s supera dt_max={dt_max:.6e} s "
            f"(r={r:.3f} > 0.5): el esquema explícito no integra este caso."
        )
        return 3
    duracion = time.perf_counter() - inicio

    exacta_final = solucion_sinusoidal(x, t_final, alpha, T0, A, L)
    error = float(np.max(np.abs(resultado.T - exacta_final)))

    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    colores = plt.cm.viridis(np.linspace(0.05, 0.90, len(pasos)))

    for paso, color in zip(pasos, colores):
        t = paso * dt
        exacta = solucion_sinusoidal(x, t, alpha, T0, A, L)
        ax.plot(x, exacta, color=color, lw=2.0, label=f"{t / 3600:.0f} h")
        ax.plot(
            x[::5],
            resultado.instantaneas[paso][::5],
            "o",
            color=color,
            ms=4.0,
            mfc="white",
            mew=1.0,
        )

    ax.set_xlabel("x [m]")
    ax.set_ylabel("T [°C]")
    ax.set_title("Difusión 1D: numérica (marcadores) vs. analítica (líneas)")
    ax.grid(True, alpha=0.35)
    ax.legend(title="Tiempo", loc="upper right")
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
    print(f"alpha={alpha:.6e} m²/s")
    print(f"Error L_inf a t={t_final/3600:.1f} h: {error:.6e} °C")
    print(f"Tiempo de cálculo: {duracion:.3f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
