"""Solver explícito FTCS para difusión térmica 1D.

Ecuación resuelta (propiedades constantes, fuente volumétrica uniforme):

    rho·cp·dT/dt = k·d²T/dx² + Qdot

Discretización explícita (Forward-Time Centered-Space):

    T_i^{n+1} = T_i^n + r·(T_{i+1}^n - 2T_i^n + T_{i-1}^n)
                + dt·Qdot/(rho·cp)

con r = alpha·dt/dx² y alpha = k/(rho·cp).

Estabilidad de difusión pura: r <= 1/2. Con Robin se agrega la restricción
del balance de medio volumen de control en el borde:

    dt <= rho·cp·dx² / (2k + 2h·dx).

Los extremos con Neumann se tratan como adiabáticos (q'' = 0) usando un nodo
fantasma; los extremos Robin usan el balance sobre medio volumen de control.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .boundaries import CondicionBorde, PropiedadesTermicas


@dataclass
class Resultado1D:
    """Resultado de una simulación 1D."""

    T: np.ndarray
    instantaneas: dict[int, np.ndarray]


def limite_estabilidad(
    propiedades: PropiedadesTermicas,
    dx: float,
    borde_izq: CondicionBorde,
    borde_der: CondicionBorde,
) -> float:
    """Paso temporal máximo admisible para el esquema explícito [s]."""
    if not np.isfinite(dx) or dx <= 0.0:
        raise ValueError("dx debe ser positivo.")
    limite = dx**2 / (2.0 * propiedades.alpha)
    for borde in (borde_izq, borde_der):
        if borde.tipo == "robin":
            limite_robin = (
                propiedades.rho * propiedades.cp * dx**2
                / (2.0 * propiedades.k + 2.0 * borde.h * dx)
            )
            limite = min(limite, limite_robin)
    return limite


def energia_1d(
    T: np.ndarray, propiedades: PropiedadesTermicas, dx: float
) -> float:
    """Energía térmica discreta [J/m²] con pesos de medio volumen en extremos."""
    T = np.asarray(T, dtype=float)
    pesos = np.ones_like(T)
    pesos[0] = 0.5
    pesos[-1] = 0.5
    return propiedades.rho * propiedades.cp * dx * float(np.sum(pesos * T))


def _actualizar_borde(
    T_old: np.ndarray,
    propiedades: PropiedadesTermicas,
    dx: float,
    dt: float,
    r: float,
    borde: CondicionBorde,
    es_izquierdo: bool,
    incremento_fuente: float,
) -> float:
    indice = 0 if es_izquierdo else -1
    vecino = 1 if es_izquierdo else -2

    if borde.tipo == "dirichlet":
        return borde.valor

    conductancia_interna = 2.0 * r
    if borde.tipo == "neumann":
        return (
            T_old[indice]
            + conductancia_interna * (T_old[vecino] - T_old[indice])
            + incremento_fuente
        )

    # Robin: balance de medio volumen de control.
    return (
        T_old[indice]
        + dt
        * (
            2.0 * propiedades.k / (propiedades.rho * propiedades.cp * dx**2)
            * (T_old[vecino] - T_old[indice])
            + 2.0 * borde.h / (propiedades.rho * propiedades.cp * dx)
            * (borde.valor - T_old[indice])
        )
        + incremento_fuente
    )


def resolver_1d(
    T_inicial: np.ndarray,
    propiedades: PropiedadesTermicas,
    dx: float,
    dt: float,
    n_pasos: int,
    borde_izq: CondicionBorde,
    borde_der: CondicionBorde,
    fuente: float = 0.0,
    pasos_guardado: set[int] | None = None,
) -> Resultado1D:
    """Integra la ecuación de difusión 1D con FTCS.

    Parámetros
    ----------
    T_inicial : ndarray, forma (n,)
        Temperatura inicial [°C] en los nodos equiespaciados.
        Los extremos Dirichlet deben coincidir con la temperatura impuesta
        (tolerancia absoluta de 1e-10 °C); si no, se rechaza la entrada.
    propiedades : PropiedadesTermicas
        k [W/(m·K)], rho [kg/m³], cp [J/(kg·K)].
    dx : float
        Espaciamiento uniforme [m].
    dt : float
        Paso temporal [s].
    n_pasos : int
        Número de pasos a integrar.
    borde_izq, borde_der : CondicionBorde
        Condiciones de borde en x=0 y x=L.
    fuente : float
        Fuente volumétrica uniforme Qdot [W/m³]. Cero para difusión pura.
    pasos_guardado : set[int] | None
        Pasos cuyos estados se guardan en ``resultado.instantaneas``.

    Returns
    -------
    Resultado1D
        Temperatura final e instantáneas solicitadas (incluye el paso 0).
    """
    T = np.asarray(T_inicial, dtype=float).copy()
    if T.ndim != 1 or T.size < 3:
        raise ValueError("T_inicial debe ser un arreglo 1D con al menos 3 nodos.")
    if not np.all(np.isfinite(T)):
        raise ValueError("T_inicial contiene valores no finitos.")
    if not np.isfinite(dx) or dx <= 0.0:
        raise ValueError("dx debe ser un número positivo.")
    if not np.isfinite(dt) or dt <= 0.0:
        raise ValueError("dt debe ser un número positivo.")
    if n_pasos < 0:
        raise ValueError("n_pasos no puede ser negativo.")
    if not np.isfinite(fuente):
        raise ValueError("La fuente Qdot debe ser finita.")

    for indice, borde in ((0, borde_izq), (-1, borde_der)):
        if borde.tipo == "dirichlet":
            if not np.isclose(T[indice], borde.valor, rtol=0.0, atol=1e-10):
                raise ValueError("T_inicial es incompatible con el borde Dirichlet.")
            T[indice] = borde.valor

    dt_max = limite_estabilidad(propiedades, dx, borde_izq, borde_der)
    if dt > dt_max * (1.0 + 1e-12):
        raise ValueError(
            "Paso temporal inestable: "
            f"dt={dt:.6e} s supera dt_max={dt_max:.6e} s."
        )

    r = propiedades.alpha * dt / dx**2
    incremento_fuente = dt * fuente / (propiedades.rho * propiedades.cp)

    instantaneas: dict[int, np.ndarray] = {}
    if pasos_guardado is not None:
        pasos_guardado = {int(p) for p in pasos_guardado}
        instantaneas[0] = T.copy()

    for paso in range(1, n_pasos + 1):
        T_old = T.copy()
        T[1:-1] = (
            T_old[1:-1]
            + r * (T_old[2:] - 2.0 * T_old[1:-1] + T_old[:-2])
            + incremento_fuente
        )
        T[0] = _actualizar_borde(
            T_old, propiedades, dx, dt, r, borde_izq, True, incremento_fuente
        )
        T[-1] = _actualizar_borde(
            T_old, propiedades, dx, dt, r, borde_der, False, incremento_fuente
        )
        if pasos_guardado and paso in pasos_guardado:
            instantaneas[paso] = T.copy()

    return Resultado1D(T=T, instantaneas=instantaneas)
