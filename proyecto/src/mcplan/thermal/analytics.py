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


def solucion_sinusoidal_nd(
    coords: tuple[np.ndarray, ...],
    t: float,
    alpha: float,
    T0: float,
    A: float,
    L: tuple[float, ...],
) -> np.ndarray:
    """Solución exacta 2D/3D en una caja con Dirichlet ``T0`` en todas las caras.

    T = T0 + A · prod_d sin(pi x_d / L_d) · exp(-alpha · sum_d (pi/L_d)² · t)
    """
    if alpha <= 0.0 or any(Ld <= 0.0 for Ld in L):
        raise ValueError("alpha y L deben ser positivos.")
    if len(coords) != len(L):
        raise ValueError("coords y L deben tener la misma dimensión.")
    forma = np.ones_like(np.asarray(coords[0], dtype=float))
    lam = 0.0
    for x, Ld in zip(coords, L):
        forma = forma * np.sin(np.pi * np.asarray(x, dtype=float) / Ld)
        lam += (np.pi / Ld) ** 2
    return T0 + A * forma * np.exp(-alpha * lam * t)


def _raices_biot(Bi: float, n: int) -> np.ndarray:
    """Primeras ``n`` raíces de zeta·tan(zeta) = Bi (bisección)."""
    raices = []
    for m in range(n):
        a = m * np.pi + 1e-12
        b = m * np.pi + np.pi / 2 - 1e-12
        f = lambda z: z * np.tan(z) - Bi  # noqa: E731
        for _ in range(200):
            c = 0.5 * (a + b)
            if f(a) * f(c) <= 0.0:
                b = c
            else:
                a = c
        raices.append(0.5 * (a + b))
    return np.array(raices)


def solucion_pared_robin(
    x: np.ndarray,
    t: float,
    L: float,
    alpha: float,
    k: float,
    h: float,
    T_i: float,
    T_inf: float,
    n_terminos: int = 60,
) -> np.ndarray:
    """Pared plana de espesor 2L, T inicial uniforme, convección en ambas caras.

    ``x`` se mide desde el plano medio (-L <= x <= L). Serie clásica
    (Incropera, cap. 5):

        theta/theta_i = sum C_n exp(-zeta_n² Fo) cos(zeta_n x / L)
        C_n = 4 sin zeta_n / (2 zeta_n + sin 2 zeta_n),  zeta_n tan zeta_n = Bi

    con Bi = h L / k y Fo = alpha t / L².
    """
    if min(L, alpha, k, h) <= 0.0:
        raise ValueError("L, alpha, k y h deben ser positivos.")
    Bi = h * L / k
    Fo = alpha * t / L**2
    z = _raices_biot(Bi, n_terminos)
    C = 4.0 * np.sin(z) / (2.0 * z + np.sin(2.0 * z))
    x = np.asarray(x, dtype=float)
    theta = np.zeros_like(x)
    for Cn, zn in zip(C, z):
        theta += Cn * np.exp(-(zn**2) * Fo) * np.cos(zn * x / L)
    return T_inf + (T_i - T_inf) * theta
