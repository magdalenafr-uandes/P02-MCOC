"""Extracción de la geometría triangulada y propiedades de cada vertida del IFC.

Primer eslabón del pipeline BIM -> grilla. Usa la misma regla semántica que
``ifc_io.py`` (pset ``UANDES_HormigonMasivo`` con ``VertidaID``) y entrega, por
vertida, su malla cerrada en coordenadas de mundo [m] y su pset tal como está
en el IFC. No decide parámetros del caso: eso lo hace la configuración externa.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

PSET_HORMIGON = "UANDES_HormigonMasivo"


@dataclass(frozen=True)
class SolidoVertida:
    """Malla triangulada cerrada de una vertida."""

    vertida_id: int
    nombre: str
    guid: str
    triangulos: np.ndarray  # (n, 3, 3) vértices [m]
    propiedades: dict[str, Any] = field(default_factory=dict)

    @property
    def volumen(self) -> float:
        """Volumen de la malla por teorema de la divergencia [m³]."""
        a, b, c = self.triangulos[:, 0], self.triangulos[:, 1], self.triangulos[:, 2]
        return float(abs(np.einsum("ij,ij->i", a, np.cross(b, c)).sum()) / 6.0)

    @property
    def area(self) -> float:
        """Área total de la malla [m²]."""
        t = self.triangulos
        return float(0.5 * np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1).sum())

    @property
    def limites(self) -> tuple[np.ndarray, np.ndarray]:
        v = self.triangulos.reshape(-1, 3)
        return v.min(axis=0), v.max(axis=0)


def solido_desde_malla(
    vertida_id: int,
    vertices: np.ndarray,
    caras: np.ndarray,
    nombre: str = "",
    guid: str = "",
    propiedades: dict[str, Any] | None = None,
) -> SolidoVertida:
    """Construye un sólido desde vértices (m, 3) y caras triangulares (n, 3)."""
    vertices = np.asarray(vertices, dtype=float).reshape(-1, 3)
    caras = np.asarray(caras, dtype=int).reshape(-1, 3)
    if len(caras) < 4:
        raise ValueError(f"Vertida {vertida_id}: la malla necesita al menos 4 triángulos.")
    if not np.all(np.isfinite(vertices)):
        raise ValueError(f"Vertida {vertida_id}: vértices no finitos.")
    return SolidoVertida(
        int(vertida_id), nombre or f"Vertida_{vertida_id:02d}", guid, vertices[caras], dict(propiedades or {})
    )


# [MAPA:lectura-ifc] IFC -> mallas trianguladas + pset por vertida
def extraer_vertidas(ruta_ifc: str | Path) -> list[SolidoVertida]:
    """Lee el IFC y devuelve las vertidas ordenadas por ``VertidaID``."""
    import ifcopenshell
    import ifcopenshell.geom
    import ifcopenshell.util.element

    from .ifc_io import productos_vertida

    ruta_ifc = Path(ruta_ifc)
    if not ruta_ifc.is_file():
        raise FileNotFoundError(f"No se encontró el archivo IFC: {ruta_ifc}")
    modelo = ifcopenshell.open(str(ruta_ifc))
    ajustes = ifcopenshell.geom.settings()
    ajustes.set("use-world-coords", True)

    solidos: list[SolidoVertida] = []
    vistos: set[int] = set()
    for producto in productos_vertida(modelo):
        pset = dict(ifcopenshell.util.element.get_psets(producto)[PSET_HORMIGON])
        pset.pop("id", None)
        vid = int(pset["VertidaID"])
        if vid in vistos:
            raise ValueError(f"VertidaID {vid} repetido en el IFC.")
        if vid <= 0:
            raise ValueError(f"VertidaID debe ser positivo (0 = vacío); se leyó {vid}.")
        vistos.add(vid)
        forma = ifcopenshell.geom.create_shape(ajustes, producto)
        solidos.append(
            solido_desde_malla(
                vid,
                np.asarray(forma.geometry.verts),
                np.asarray(forma.geometry.faces),
                producto.Name or "",
                producto.GlobalId,
                pset,
            )
        )
    if not solidos:
        raise ValueError(f"{ruta_ifc.name} no contiene vertidas con el pset {PSET_HORMIGON}.")
    return solidos
