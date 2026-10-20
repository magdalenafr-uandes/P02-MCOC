"""Abre un IFC con IfcOpenShell y lista nombres, clases, GUIDs y propiedades.

Uso:
    python scripts/inspect_ifc.py
    python scripts/inspect_ifc.py geometry/fundacion_e01_ejemplo.ifc
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mcplan.bim.ifc_io import CAMPOS_REQUERIDOS, PSET_HORMIGON, leer_modelo

RAIZ = Path(__file__).resolve().parents[1]


def _valor(propiedades: dict, campo: str) -> str:
    if campo not in propiedades:
        return "—"
    valor = propiedades[campo]
    if isinstance(valor, float):
        return f"{valor:g}"
    return str(valor)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lista las vertidas de un archivo IFC usando IfcOpenShell."
    )
    parser.add_argument(
        "ruta",
        nargs="?",
        type=Path,
        default=RAIZ / "geometry" / "fundacion_e01_ejemplo.ifc",
        help="Archivo IFC a inspeccionar.",
    )
    args = parser.parse_args()

    resumen = leer_modelo(args.ruta)

    print(f"Archivo:  {args.ruta}")
    print(f"Esquema:  {resumen.schema}")
    print(f"Proyecto: {resumen.proyecto}")
    print("Unidades:")
    for unidad in resumen.unidades:
        print(f"  - {unidad}")
    print()

    print(f"Property set esperado: {PSET_HORMIGON}")
    print(
        f"{'Vertida':<14} {'Clase':<10} {'GUID':<24} "
        f"{'VertidaID':<10} {'Inicio':<20} {'Tcoloc_C':>9}"
    )
    print("-" * 92)
    for vertida in resumen.vertidas:
        props = vertida.propiedades
        print(
            f"{vertida.nombre:<14} {vertida.clase:<10} {vertida.guid:<24} "
            f"{_valor(props, 'VertidaID'):<10} "
            f"{_valor(props, 'InicioPlanificado'):<20} "
            f"{_valor(props, 'TemperaturaColocacion_C'):>9}"
        )

    print()
    for vertida in resumen.vertidas:
        print(f"[{vertida.nombre}] geometría: {'sí' if vertida.tiene_geometria else 'no'}")
        for campo in CAMPOS_REQUERIDOS:
            print(f"  {campo}: {_valor(vertida.propiedades, campo)}")
        faltantes = [c for c in CAMPOS_REQUERIDOS if c not in vertida.propiedades]
        if faltantes:
            print(f"  FALTAN: {', '.join(faltantes)}")
        print()


if __name__ == "__main__":
    main()
