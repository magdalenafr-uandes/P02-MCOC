"""Voxelización cartesiana de la fundación (avance BIM -> grilla del solver).

Regla de la guía G04: un voxel pertenece a una vertida si su **centro** está
dentro del sólido (frontera "staircase"). Cada voxel guarda ``vertida_id``
(0 = fuera del hormigón). La geometría se toma de la misma definición
paramétrica (``VERTIDAS_FOUNDATION``) con la que se construye
``geometry/foundation.ifc``; leer las mallas trianguladas del IFC queda para W3.

Sólidos soportados: prisma de polígono regular y tronco de pirámide de
polígono regular (radio al vértice que varía linealmente con z).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass
class GrillaVertidas:
    """Resultado de la voxelización."""

    vertida_id: np.ndarray  # (nx, ny, nz) int, 0 = vacío
    origen: tuple[float, float, float]  # esquina mínima de la grilla [m]
    paso: float  # tamaño de voxel [m]

    def volumen(self, vid: int) -> float:
        return float(np.count_nonzero(self.vertida_id == vid)) * self.paso**3

    def centros(self, eje: int) -> np.ndarray:
        n = self.vertida_id.shape[eje]
        return self.origen[eje] + (np.arange(n) + 0.5) * self.paso


def _dentro_poligono(
    x: np.ndarray, y: np.ndarray, n_lados: int, radio: np.ndarray, rotacion: float
) -> np.ndarray:
    """Punto dentro de un polígono regular centrado en el origen.

    Un polígono regular es la intersección de ``n`` semiplanos: la proyección
    del punto sobre la normal de cada cara debe ser <= apotema.
    """
    apotema = radio * math.cos(math.pi / n_lados)
    dentro = np.ones(np.broadcast(x, y, radio).shape, dtype=bool)
    for i in range(n_lados):
        phi = rotacion + math.pi / n_lados + 2.0 * math.pi * i / n_lados
        dentro &= x * math.cos(phi) + y * math.sin(phi) <= apotema
    return dentro


def voxelizar(vertidas: Sequence, paso: float, margen: float = 0.0) -> GrillaVertidas:
    """Voxeliza las vertidas (objetos con la interfaz de ``VertidaFoundation``)."""
    if paso <= 0.0:
        raise ValueError("paso debe ser positivo.")
    r_max = max(max(v.radio_inferior, v.radio_superior or 0.0) for v in vertidas)
    z_min = min(v.z_base for v in vertidas)
    z_max = max(v.z_base + v.altura for v in vertidas)
    semi = r_max + margen
    nxy = int(math.ceil(2.0 * semi / paso))
    nz = int(math.ceil((z_max - z_min + 2.0 * margen) / paso))
    origen = (-nxy * paso / 2.0, -nxy * paso / 2.0, z_min - margen)
    x = origen[0] + (np.arange(nxy) + 0.5) * paso
    y = origen[1] + (np.arange(nxy) + 0.5) * paso
    z = origen[2] + (np.arange(nz) + 0.5) * paso
    X, Y = np.meshgrid(x, y, indexing="ij")

    ids = np.zeros((nxy, nxy, nz), dtype=np.int16)
    for v in vertidas:
        r_sup = v.radio_inferior if v.radio_superior is None else v.radio_superior
        rot = math.radians(v.rotacion_grados)
        for kz in np.nonzero((z >= v.z_base) & (z < v.z_base + v.altura))[0]:
            s = (z[kz] - v.z_base) / v.altura
            radio = v.radio_inferior + s * (r_sup - v.radio_inferior)
            dentro = _dentro_poligono(X, Y, v.n_lados, np.asarray(radio), rot)
            capa = ids[:, :, kz]
            capa[dentro & (capa == 0)] = v.vertida_id
    return GrillaVertidas(ids, origen, paso)
