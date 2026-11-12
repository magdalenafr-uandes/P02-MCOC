"""Tuberías de enfriamiento embebidas: Dirichlet en la pared del tubo.

La pared del tubo se mantiene a la temperatura del agua (**Dirichlet**,
``T = T_agua``). Un tubo de ~25 mm es mucho menor que el voxel, así que no se
convierte la celda entera en agua (eso inflaría el diámetro): cada celda que
atraviesa el tubo intercambia calor con su pared por una conductancia de
"pozo en celda" (Peaceman, 1978)::

    G = 2π·k·L / ln(r_eq / r_tubo)          [W/K]
    r_eq = 0,14·√(Δa² + Δb²)                 (Δa, Δb: lados de la sección transversal)
    P = G·(T_celda − T_agua)                 [W]  (positivo = calor que el agua extrae)

``r_eq`` es el radio al que la temperatura del campo continuo alrededor del
tubo iguala a la de la celda. La potencia extraída **varía** con la
temperatura del hormigón: al principio, con el hormigón caliente, extrae más;
cuando el núcleo se enfría, menos. Si el agua está más caliente que el
hormigón, el signo se invierte (no se fuerza una extracción inexistente).

Supuestos: agua a temperatura constante a lo largo del circuito (caudal
suficiente para que no se caliente; ver ``docs/enfriamiento_tuberias.md``
para el modelo con calentamiento del agua) y resistencia de la pared
despreciable frente a la del hormigón.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Tuberia:
    """Un circuito ya trazado sobre la grilla (índices planos de las celdas que cruza)."""

    nombre: str
    vertida_id: int
    idx: np.ndarray  # celdas atravesadas (índices planos)
    G: np.ndarray  # conductancia celda -> pared por celda [W/K]
    T_agua_C: float
    longitud_m: float
    desde_s: float = 0.0  # desde el inicio de la vertida
    hasta_s: float = math.inf
    direccion: str = "x"  # eje de los tubos rectos (para dibujarlos)

    def __post_init__(self) -> None:
        if len(self.idx) == 0:
            raise ValueError(f"Tubería {self.nombre}: no atraviesa ninguna celda de su vertida.")
        if not math.isfinite(self.T_agua_C):
            raise ValueError(f"Tubería {self.nombre}: T del agua finita.")
        if not (0.0 <= self.desde_s < self.hasta_s):
            raise ValueError(f"Tubería {self.nombre}: período [desde, hasta) válido.")

    def activa(self, t_s: float, inicio_vertida_s: float) -> bool:
        return self.desde_s <= t_s - inicio_vertida_s < self.hasta_s


# [MAPA:tuberia-dirichlet] pared del tubo a T_agua: G = 2πkL/ln(r_eq/r), P = G (T_celda − T_agua)
def conductancia_pozo(k: float, largo_m: float, lado_a_m: float, lado_b_m: float, radio_m: float) -> float:
    """Conductancia celda -> pared de un tramo de tubo (Peaceman) [W/K]."""
    r_eq = 0.14 * math.hypot(lado_a_m, lado_b_m)
    if radio_m <= 0.0 or r_eq <= radio_m:
        raise ValueError(
            f"El tubo (r = {radio_m * 1000:.1f} mm) no cabe en la celda (r_eq = {r_eq * 1000:.1f} mm): "
            "agrandar la celda transversal o reducir el diámetro."
        )
    return 2.0 * math.pi * k * largo_m / math.log(r_eq / radio_m)


# [MAPA:tuberia-trazado] líneas paralelas a una cota, con separación y recubrimiento, dentro de la vertida
def trazar_tuberias(
    vertida_id: np.ndarray,
    origen: Sequence[float],
    paso: Sequence[float],
    nombre: str,
    vid: int,
    cota_m: float,
    direccion: str,
    separacion_m: float,
    diametro_m: float,
    T_agua_C: float,
    k_hormigon: float,
    recubrimiento_m: float = 0.5,
    desde_s: float = 0.0,
    hasta_s: float = math.inf,
) -> Tuberia:
    """Tubos rectos paralelos a ``direccion`` ('x' o 'y') en la capa de la cota dada.

    Los ejes se reparten cada ``separacion_m`` dentro de la huella de la
    vertida en esa capa, dejando ``recubrimiento_m`` hasta el borde lateral.
    """
    if direccion not in ("x", "y"):
        raise ValueError(f"{nombre}: direccion 'x' o 'y'.")
    if not separacion_m > 0.0 or not diametro_m > 0.0 or recubrimiento_m < 0.0:
        raise ValueError(f"{nombre}: separación y diámetro positivos, recubrimiento no negativo.")
    eje = 0 if direccion == "x" else 1
    trans = 1 - eje
    nz = vertida_id.shape[2]
    k = int(math.floor((cota_m - origen[2]) / paso[2]))
    if not 0 <= k < nz or not np.any(vertida_id[:, :, k] == vid):
        raise ValueError(f"{nombre}: la cota {cota_m} m no cae dentro de la vertida {vid}.")
    capa = vertida_id[:, :, k] == vid
    centros_trans = origen[trans] + (np.arange(capa.shape[trans]) + 0.5) * paso[trans]
    ocupadas = np.nonzero(capa.any(axis=eje))[0]
    lo = centros_trans[ocupadas[0]] - paso[trans] / 2 + recubrimiento_m
    hi = centros_trans[ocupadas[-1]] + paso[trans] / 2 - recubrimiento_m
    if hi < lo:
        raise ValueError(f"{nombre}: el recubrimiento no deja espacio para tubos en la vertida {vid}.")
    n_lineas = int(math.floor((hi - lo) / separacion_m)) + 1
    centro = 0.5 * (lo + hi)
    posiciones = centro + (np.arange(n_lineas) - (n_lineas - 1) / 2) * separacion_m  # centradas en la huella
    recorte = int(math.ceil(recubrimiento_m / paso[eje]))
    celdas = []
    for pos in posiciones:
        j = int(np.argmin(np.abs(centros_trans - pos)))
        linea = capa[:, j] if eje == 0 else capa[j, :]
        dentro = np.nonzero(linea)[0]
        if dentro.size == 0:
            continue
        # tramos contiguos; se recortan 'recorte' celdas en cada extremo (recubrimiento)
        cortes = np.split(dentro, np.nonzero(np.diff(dentro) > 1)[0] + 1)
        for tramo in cortes:
            tramo = tramo[recorte:len(tramo) - recorte]
            for i in tramo:
                ijk = (i, j, k) if eje == 0 else (j, i, k)
                celdas.append(np.ravel_multi_index(ijk, vertida_id.shape))
    idx = np.array(sorted(set(celdas)), dtype=np.int64)
    G = conductancia_pozo(k_hormigon, paso[eje], paso[trans], paso[2], diametro_m / 2.0)
    return Tuberia(nombre, vid, idx, np.full(idx.shape, G), T_agua_C, len(idx) * paso[eje], desde_s, hasta_s,
                   direccion)


def tramos(tub: Tuberia, forma: Sequence[int], origen: Sequence[float], paso: Sequence[float]) -> list[list[list[float]]]:
    """Tramos rectos [[x, y, z] inicio, [x, y, z] fin] de un circuito, para dibujarlo."""
    eje = 0 if tub.direccion == "x" else 1
    ijk = np.array(np.unravel_index(tub.idx, tuple(forma))).T
    resultado = []
    otros = [a for a in range(3) if a != eje]
    for clave in sorted({tuple(f[otros]) for f in ijk}):
        fila = sorted(int(f[eje]) for f in ijk if tuple(f[otros]) == clave)
        cortes = np.split(np.array(fila), np.nonzero(np.diff(fila) > 1)[0] + 1)
        for run in cortes:
            p0, p1 = [0.0] * 3, [0.0] * 3
            for a, v in zip(otros, clave):
                p0[a] = p1[a] = origen[a] + (v + 0.5) * paso[a]
            p0[eje] = origen[eje] + run[0] * paso[eje]
            p1[eje] = origen[eje] + (run[-1] + 1) * paso[eje]
            resultado.append([p0, p1])
    return resultado
