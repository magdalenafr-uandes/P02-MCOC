"""Voxelización de mallas IFC en una grilla cartesiana (guía G04).

Criterio de pertenencia: un voxel pertenece al sólido si su **centro** está
dentro de la malla cerrada. Se decide por paridad de cruces de un rayo
vertical por cada columna (x, y): la malla se cruza un número par de veces y
los tramos (z_entrada, z_salida] quedan dentro.

Desempates (las mallas traen ruido de redondeo, p. ej. 0.5499999 vs 0.5500001):

- En z, un centro que cae en la cara común de dos vertidas apiladas pertenece
  a la de **abajo**: los cruces se comparan desplazados ``_TOL_Z·Δx`` hacia
  arriba, mucho más que el ruido y mucho menos que Δx. Así ninguna columna
  queda en dos vertidas.
- En (x, y), los rayos se desplazan una fracción ínfima de Δx
  (``_DESPLAZAMIENTO``) para no pasar exactamente por aristas o vértices,
  donde un cruce se contaría dos veces.

Resultado (``GrillaBIM``): por voxel, ``vertida_id`` (0 = sin hormigón) y
``es_suelo``; el volumen estimado ``V_h = N·Δx³`` frente al de la malla; y las
caras expuestas (sólido contra vacío) que recibirán convección.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np

from .mallas_ifc import SolidoVertida

DIRECCIONES = ("x-", "x+", "y-", "y+", "z-", "z+")
_DESPLAZAMIENTO = (1.0e-7 * math.pi, 1.0e-7 * math.e)  # fracción de Δx, Δy en (x, y)
_TOL_Z = 1.0e-6  # fracción de Δz: desempate de centros en una interfaz horizontal

Paso = float | Sequence[float]


def pasos(paso: Paso) -> tuple[float, float, float]:
    """(Δx, Δy, Δz) desde un escalar (voxel cúbico) o una terna."""
    if isinstance(paso, (int, float)):
        terna = (float(paso),) * 3
    else:
        terna = tuple(float(p) for p in paso)
    if len(terna) != 3 or any(not math.isfinite(p) or p <= 0.0 for p in terna):
        raise ValueError("El paso de malla debe ser positivo y finito (escalar o (Δx, Δy, Δz)).")
    return terna  # type: ignore[return-value]


def area_cara(paso: Paso, eje: int) -> float:
    """Área de la cara de un voxel normal al eje [m²]."""
    d = pasos(paso)
    return d[(eje + 1) % 3] * d[(eje + 2) % 3]


@dataclass(frozen=True)
class DefinicionGrilla:
    """Caja de cálculo: origen (esquina mínima), pasos (Δx, Δy, Δz) y número de celdas."""

    origen: tuple[float, float, float]
    paso: tuple[float, float, float]
    forma: tuple[int, int, int]
    n_suelo: int = 0  # capas de suelo bajo la base del hormigón

    def centros(self, eje: int) -> np.ndarray:
        return self.origen[eje] + (np.arange(self.forma[eje]) + 0.5) * self.paso[eje]


@dataclass
class GrillaBIM:
    """Grilla voxelizada lista para el solver."""

    definicion: DefinicionGrilla
    vertida_id: np.ndarray  # (nx, ny, nz) int16, 0 = sin hormigón
    es_suelo: np.ndarray  # (nx, ny, nz) bool
    voxeles_solapados: int = 0

    @property
    def paso(self) -> tuple[float, float, float]:
        return self.definicion.paso

    @property
    def forma(self) -> tuple[int, int, int]:
        return self.definicion.forma

    @property
    def volumen_voxel(self) -> float:
        return float(np.prod(self.paso))

    def ids(self) -> list[int]:
        return sorted(int(v) for v in np.unique(self.vertida_id) if v != 0)

    def volumen(self, vid: int) -> float:
        """V_h = N_activo · ΔxΔyΔz de una vertida [m³]."""
        return float(np.count_nonzero(self.vertida_id == vid)) * self.volumen_voxel


def definir_grilla(
    solidos: Sequence[SolidoVertida],
    paso: Paso,
    margen_lateral: float,
    margen_superior: float,
    espesor_suelo: float = 0.0,
) -> DefinicionGrilla:
    """Caja que contiene los sólidos con márgenes; la base cae en una cara de voxel.

    ``paso`` puede ser un escalar (voxel cúbico) o (Δx, Δy, Δz). Un Δz que
    divide los espesores de las vertidas hace exactas sus interfaces horizontales.
    """
    d = pasos(paso)
    if min(margen_lateral, margen_superior, espesor_suelo) < 0.0:
        raise ValueError("Márgenes y espesor de suelo no pueden ser negativos.")
    if margen_lateral < max(d[0], d[1]) or margen_superior < d[2]:
        raise ValueError("Los márgenes deben ser >= paso: el hormigón no puede tocar la caja.")
    lo = np.min([s.limites[0] for s in solidos], axis=0)
    hi = np.max([s.limites[1] for s in solidos], axis=0)
    forma: list[int] = []
    origen: list[float] = []
    for eje in (0, 1):
        n = int(math.ceil((hi[eje] - lo[eje] + 2.0 * margen_lateral) / d[eje]))
        forma.append(n)
        origen.append(0.5 * (lo[eje] + hi[eje]) - 0.5 * n * d[eje])
    n_suelo = int(round(espesor_suelo / d[2]))
    if espesor_suelo > 0.0 and n_suelo == 0:
        raise ValueError("espesor de suelo menor que media celda: aumentarlo o refinar.")
    n_sobre = int(math.ceil((hi[2] - lo[2] + margen_superior) / d[2]))
    forma.append(n_suelo + n_sobre)
    origen.append(float(lo[2]) - n_suelo * d[2])
    return DefinicionGrilla((origen[0], origen[1], origen[2]), d, tuple(forma), n_suelo)


def _cruces_rayo_z(
    triangulos: np.ndarray, xs: np.ndarray, ys: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Cruces de los rayos verticales (xs[i], ys[j]) con los triángulos."""
    ix_l: list[np.ndarray] = []
    iy_l: list[np.ndarray] = []
    z_l: list[np.ndarray] = []
    escala = float(np.ptp(triangulos.reshape(-1, 3)[:, :2])) or 1.0
    for (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) in triangulos:
        det = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(det) <= 1e-14 * escala**2:
            continue  # triángulo vertical: un rayo vertical no lo cruza
        i0, i1 = np.searchsorted(xs, [min(x0, x1, x2), max(x0, x1, x2)], side="left")
        j0, j1 = np.searchsorted(ys, [min(y0, y1, y2), max(y0, y1, y2)], side="left")
        if i0 >= i1 or j0 >= j1:
            continue
        X, Y = np.meshgrid(xs[i0:i1], ys[j0:j1], indexing="ij")
        w0 = ((y1 - y2) * (X - x2) + (x2 - x1) * (Y - y2)) / det
        w1 = ((y2 - y0) * (X - x2) + (x0 - x2) * (Y - y2)) / det
        w2 = 1.0 - w0 - w1
        dentro = (w0 >= 0.0) & (w1 >= 0.0) & (w2 >= 0.0)
        if not dentro.any():
            continue
        ii, jj = np.nonzero(dentro)
        ix_l.append(ii + i0)
        iy_l.append(jj + j0)
        z_l.append((w0 * z0 + w1 * z1 + w2 * z2)[dentro])
    if not ix_l:
        vacio = np.zeros(0, dtype=int)
        return vacio, vacio, np.zeros(0)
    return np.concatenate(ix_l), np.concatenate(iy_l), np.concatenate(z_l)


def ocupacion(solido: SolidoVertida, grilla: DefinicionGrilla) -> np.ndarray:
    """Máscara booleana de voxeles cuyo centro está dentro de la malla."""
    dx, dy, dz = grilla.paso
    xs = grilla.centros(0) + _DESPLAZAMIENTO[0] * dx
    ys = grilla.centros(1) + _DESPLAZAMIENTO[1] * dy
    zc = grilla.centros(2)
    nx, ny, nz = grilla.forma
    ix, iy, z = _cruces_rayo_z(solido.triangulos, xs, ys)
    if z.size == 0:
        return np.zeros(grilla.forma, dtype=bool)

    orden = np.lexsort((z, iy, ix))
    ix, iy, z = ix[orden], iy[orden], z[orden]
    columna = ix * ny + iy
    _, inicio, cuenta = np.unique(columna, return_index=True, return_counts=True)
    if np.any(cuenta % 2):
        raise ValueError(
            f"Vertida {solido.vertida_id}: la malla no es cerrada "
            "(un rayo la cruza un número impar de veces)."
        )
    posicion = np.arange(z.size) - np.repeat(inicio, cuenta)
    entra = posicion % 2 == 0
    z = z + _TOL_Z * dz
    k0 = np.searchsorted(zc, z[entra], side="left")
    k1 = np.searchsorted(zc, z[~entra], side="left")
    marcas = np.zeros((nx, ny, nz + 1), dtype=np.int32)
    np.add.at(marcas, (ix[entra], iy[entra], k0), 1)
    np.add.at(marcas, (ix[entra], iy[entra], k1), -1)
    return np.cumsum(marcas, axis=2)[:, :, :nz] > 0


def voxelizar_solidos(
    solidos: Sequence[SolidoVertida], grilla: DefinicionGrilla
) -> GrillaBIM:
    """Asigna ``vertida_id`` a cada voxel; marca el suelo bajo la base."""
    ids = np.zeros(grilla.forma, dtype=np.int16)
    es_suelo = np.zeros(grilla.forma, dtype=bool)
    es_suelo[:, :, : grilla.n_suelo] = True
    solapados = 0
    for s in sorted(solidos, key=lambda s: s.vertida_id):
        dentro = ocupacion(s, grilla)
        solapados += int(np.count_nonzero(dentro & ((ids != 0) | es_suelo)))
        ids[dentro & (ids == 0) & ~es_suelo] = s.vertida_id
    return GrillaBIM(grilla, ids, es_suelo, solapados)


def caras_expuestas(solido: np.ndarray) -> dict[str, np.ndarray]:
    """Caras de voxeles sólidos que dan a un voxel vacío, por dirección.

    Solo caras interiores a la caja: las de la caja se tratan aparte.
    ``resultado["z+"][i, j, k]`` es True si la cara superior de (i, j, k) está
    expuesta.
    """
    solido = np.asarray(solido, dtype=bool)
    expuestas = {}
    for eje in range(3):
        n = solido.shape[eje]
        menos = [slice(None)] * 3
        mas = [slice(None)] * 3
        menos[eje], mas[eje] = slice(0, n - 1), slice(1, n)
        cara_mas = np.zeros_like(solido)
        cara_menos = np.zeros_like(solido)
        cara_mas[tuple(menos)] = solido[tuple(menos)] & ~solido[tuple(mas)]
        cara_menos[tuple(mas)] = solido[tuple(mas)] & ~solido[tuple(menos)]
        expuestas["xyz"[eje] + "-"] = cara_menos
        expuestas["xyz"[eje] + "+"] = cara_mas
    return expuestas


def pesos_area(solidos: Sequence[SolidoVertida], grilla: GrillaBIM) -> dict[str, np.ndarray]:
    """Peso w = A_real/A_staircase de cada cara de voxel, desde las normales de la malla.

    Una cara real de área A y normal unitaria n aparece en la escalera como
    caras de voxel en las tres direcciones, de área total
    (|n_x| + |n_y| + |n_z|)·A = ||n||₁·A >= A (√2 a 45°). Ponderar cada cara de
    voxel por w = 1/||n||₁ hace que la suma vuelva a ser A, así que el área
    expuesta converge al refinar.

    Para cada cara de borde de la región de una vertida, n es la del triángulo
    de su malla que **mira en esa dirección** (n·e > 0), cuya caja (ampliada en
    Δx) contiene el centro de la cara y cuyo plano está más cerca. Sin
    candidato (p. ej. suelo), w = 1.
    """
    d = np.asarray(grilla.paso)
    origen = np.asarray(grilla.definicion.origen)
    pesos = {c: np.ones(grilla.forma) for c in DIRECCIONES}
    for s in solidos:
        propio = grilla.vertida_id == s.vertida_id
        if not propio.any():
            continue
        t = s.triangulos
        normal = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        largo = np.linalg.norm(normal, axis=1)
        validos = largo > 0.0
        t, normal = t[validos], normal[validos] / largo[validos, None]
        lo, hi = t.min(axis=1) - d, t.max(axis=1) + d
        w_triangulo = 1.0 / np.abs(normal).sum(axis=1)
        for cara, mascara in caras_expuestas(propio).items():
            celdas = np.argwhere(mascara)
            if not len(celdas):
                continue
            eje, signo = "xyz".index(cara[0]), (1.0 if cara[1] == "+" else -1.0)
            P = origen + (celdas + 0.5) * d
            P[:, eje] += signo * d[eje] / 2.0  # centro de la cara
            mejor = np.full(len(P), np.inf)
            w = np.ones(len(P))
            for j in np.nonzero(signo * normal[:, eje] > 1e-9)[0]:
                cerca = np.all((P >= lo[j]) & (P <= hi[j]), axis=1)
                distancia = np.abs((P - t[j, 0]) @ normal[j])
                gana = cerca & (distancia < mejor)
                mejor[gana] = distancia[gana]
                w[gana] = w_triangulo[j]
            pesos[cara][tuple(celdas.T)] = w
    return pesos


def area_expuesta(
    expuestas: dict[str, np.ndarray],
    paso: Paso,
    mascara: np.ndarray | None = None,
    pesos: dict[str, np.ndarray] | None = None,
) -> dict[str, float]:
    """Área expuesta [m²]: laterales (x, y), superior (z+), inferior (z-).

    Sin ``pesos`` es el área staircase; con ``pesos_area`` es la corregida.
    """
    def suma(claves: Iterable[str]) -> float:
        total = 0.0
        for c in claves:
            e = expuestas[c] if mascara is None else expuestas[c] & mascara
            n = float(np.sum(pesos[c][e])) if pesos is not None else float(np.count_nonzero(e))
            total += n * area_cara(paso, "xyz".index(c[0]))
        return total

    lateral = suma(("x-", "x+", "y-", "y+"))
    superior = suma(("z+",))
    inferior = suma(("z-",))
    return {"lateral": lateral, "superior": superior, "inferior": inferior, "total": lateral + superior + inferior}


def resumen_volumetrico(solidos: Sequence[SolidoVertida], grilla: GrillaBIM) -> list[dict[str, float]]:
    """Por vertida: V de la malla, V_h de voxeles y e_V = |V_h - V| / V."""
    filas = []
    for s in sorted(solidos, key=lambda s: s.vertida_id):
        V = s.volumen
        Vh = grilla.volumen(s.vertida_id)
        filas.append({"vertida_id": s.vertida_id, "V_malla_m3": V, "V_h_m3": Vh, "e_V": abs(Vh - V) / V})
    return filas
