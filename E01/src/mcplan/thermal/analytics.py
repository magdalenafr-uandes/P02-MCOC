"""Solución analítica para verificación del solver 1D.

Problema: barra 0 <= x <= L con Dirichlet T(0,t)=T(L,t)=T0 y perfil inicial
T(x,0) = T0 + A·sin(pi·x/L). La solución exacta es

    T(x,t) = T0 + A·sin(pi·x/L)·exp(-alpha·(pi/L)²·t).

Es un caso no trivial: la forma sinusoidal se conserva y la amplitud decae.
"""

from __future__ import annotations

import numpy as np


def solucion_sinusoidal(
    x: np.ndarray,
    t: float,
    alpha: float,
    T0: float,
    A: float,
    L: float,
) -> np.ndarray:
    """Evalúa la solución exacta en la posición ``x`` y el tiempo ``t``."""
    if alpha <= 0.0 or L <= 0.0:
        raise ValueError("alpha y L deben ser positivos.")
    x = np.asarray(x, dtype=float)
    return T0 + A * np.sin(np.pi * x / L) * np.exp(
        -alpha * (np.pi / L) ** 2 * t
    )
