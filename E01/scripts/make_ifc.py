"""Genera el IFC de ejemplo E01 con tres vertidas.

Uso:
    python scripts/make_ifc.py
    python scripts/make_ifc.py --salida geometry/otro.ifc
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mcplan.bim.build_model import guardar_modelo

RAIZ = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera un IFC4 de ejemplo con las vertidas Vertida_01..03."
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=RAIZ / "geometry" / "fundacion_e01_ejemplo.ifc",
        help="Ruta del archivo IFC de salida.",
    )
    args = parser.parse_args()

    ruta = guardar_modelo(args.salida)
    print(f"IFC generado: {ruta}")
    print("Geometría didáctica de ejemplo; NO es la geometría oficial.")


if __name__ == "__main__":
    main()
