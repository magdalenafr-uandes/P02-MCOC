"""Genera `geometry/foundation.ifc`: la fundación de 5 vertidas de la guía Bonsai.

Geometría docente octagonal (18 m entre caras, pedestal Ø7 m), clase
IfcFooting y property set UANDES_HormigonMasivo. El archivo puede abrirse
y editarse en Bonsai (File > Open IFC Project); una vez editado ahí, no lo
regeneres sin `--forzar` (borrarías la edición del round-trip).

Uso:
    python scripts/make_foundation.py
    python scripts/make_foundation.py --salida geometry/otro.ifc
    python scripts/make_foundation.py --forzar
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mcplan.bim.foundation import guardar_foundation

RAIZ = Path(__file__).resolve().parents[1]
IFC_FOUNDATION = RAIZ / "geometry" / "foundation.ifc"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera foundation.ifc (5 IfcFooting, guía Bonsai)."
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=IFC_FOUNDATION,
        help="Ruta del IFC de salida (por defecto geometry/foundation.ifc).",
    )
    parser.add_argument(
        "--forzar",
        action="store_true",
        help="Permite sobrescribir un foundation.ifc existente (borra ediciones de Bonsai).",
    )
    args = parser.parse_args()

    if args.salida.exists() and not args.forzar:
        raise SystemExit(
            f"Abortado: {args.salida} ya existe. Si fue editado en Bonsai, "
            "regenerarlo borraría el round-trip. Repite con --forzar si es intencional."
        )

    ruta = guardar_foundation(args.salida)
    print(f"IFC generado: {ruta}")
    print("5 IfcFooting (Vertida_01..05), pset UANDES_HormigonMasivo.")


if __name__ == "__main__":
    main()
