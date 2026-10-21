"""Snapshot JSON del estado de las vertidas de un IFC (clave = GlobalId).

Captura, por cada vertida (selección semántica por pset), su clase, nombre,
property sets completos, bounding box en coordenadas de mundo y volumen de
malla. El resultado sirve como lado "antes" o "después" para ``ifc_diff.py``.

Uso:
    python scripts/ifc_state.py geometry/foundation.ifc
    python scripts/ifc_state.py geometry/foundation.ifc --salida estado.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
import numpy as np

from mcplan.bim.ifc_io import productos_vertida

RAIZ = Path(__file__).resolve().parents[1]


def _geometria_producto(producto) -> tuple[float, tuple[float, float, float], tuple[float, float, float]]:
    """Volumen de malla [m³] y bbox (mín, máx) en coordenadas de mundo."""
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    forma = ifcopenshell.geom.create_shape(settings, producto)
    verts = np.asarray(forma.geometry.verts, dtype=float).reshape(-1, 3)
    caras = np.asarray(forma.geometry.faces, dtype=np.int64).reshape(-1, 3)
    v0, v1, v2 = verts[caras[:, 0]], verts[caras[:, 1]], verts[caras[:, 2]]
    volumen = float(
        abs(np.einsum("ij,ij->i", v0, np.cross(v1, v2)).sum()) / 6.0
    )
    bbox_min = tuple(float(c) for c in verts.min(axis=0))
    bbox_max = tuple(float(c) for c in verts.max(axis=0))
    return volumen, bbox_min, bbox_max


def capturar_estado(ruta: str | Path) -> dict:
    """Estado completo de las vertidas de un IFC, con GlobalId como clave."""
    ruta = Path(ruta)
    modelo = ifcopenshell.open(str(ruta))

    proyectos = modelo.by_type("IfcProject")
    unidades: list[str] = []
    if proyectos and proyectos[0].UnitsInContext:
        for unidad in proyectos[0].UnitsInContext.Units:
            if unidad.is_a("IfcSIUnit"):
                unidades.append(f"{unidad.UnitType}: {unidad.Name}")
            elif unidad.is_a("IfcConversionBasedUnit"):
                unidades.append(f"{unidad.UnitType}: {unidad.Name}")

    vertidas: dict[str, dict] = {}
    volumen_total = 0.0
    for producto in productos_vertida(modelo):
        psets = ifcopenshell.util.element.get_psets(producto)
        psets_limpios: dict[str, dict] = {}
        for nombre_pset, valores in psets.items():
            psets_limpios[nombre_pset] = {
                k: v for k, v in valores.items() if k != "id"
            }
        volumen, bbox_min, bbox_max = _geometria_producto(producto)
        volumen_total += volumen
        vertidas[producto.GlobalId] = {
            "nombre": producto.Name or "(sin nombre)",
            "clase": producto.is_a(),
            "propiedades": psets_limpios,
            "volumen_m3": volumen,
            "bbox_min": list(bbox_min),
            "bbox_max": list(bbox_max),
        }

    return {
        "archivo": str(ruta),
        "schema": modelo.schema,
        "proyecto": proyectos[0].Name if proyectos else "(sin IfcProject)",
        "unidades": unidades,
        "vertidas": vertidas,
        "totales": {
            "n_vertidas": len(vertidas),
            "volumen_total_m3": volumen_total,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Vuelca un snapshot JSON del estado de las vertidas de un IFC."
    )
    parser.add_argument(
        "ruta",
        type=Path,
        default=RAIZ / "geometry" / "foundation.ifc",
        nargs="?",
        help="Archivo IFC a capturar (por defecto geometry/foundation.ifc).",
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=None,
        help="Ruta del JSON de salida (por defecto solo imprime un resumen).",
    )
    args = parser.parse_args()

    estado = capturar_estado(args.ruta)

    print(f"Archivo:  {args.ruta}")
    print(f"Esquema:  {estado['schema']}")
    print(f"Vertidas: {estado['totales']['n_vertidas']}")
    print(f"Volumen total de malla: {estado['totales']['volumen_total_m3']:.4f} m³")
    print(
        f"{'GUID':<24} {'Nombre':<14} {'Clase':<12} {'V m3':>10}"
    )
    print("-" * 64)
    for guid, datos in estado["vertidas"].items():
        print(
            f"{guid:<24} {datos['nombre']:<14} {datos['clase']:<12} "
            f"{datos['volumen_m3']:>10.4f}"
        )

    if args.salida is not None:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        with args.salida.open("w", encoding="utf-8") as archivo:
            json.dump(estado, archivo, indent=2, ensure_ascii=False, sort_keys=True)
            archivo.write("\n")
        print(f"\nSnapshot guardado: {args.salida}")


if __name__ == "__main__":
    main()
