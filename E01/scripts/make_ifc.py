"""Genera un IFC de ejemplo E01 con tres vertidas.

El archivo versionado `geometry/fundacion_e01_ejemplo.ifc` fue **editado en
Bonsai** (Vertida_01 = 19 °C) y es la referencia canónica de la entrega. Para
no borrar esa edición, la salida por defecto de este script es
`geometry/fundacion_e01_generada.ifc`; escribir sobre el archivo versionado
exige `--forzar`.

Uso:
    python scripts/make_ifc.py
    python scripts/make_ifc.py --salida geometry/otro.ifc
    python scripts/make_ifc.py --salida geometry/fundacion_e01_ejemplo.ifc --forzar
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mcplan.bim.build_model import guardar_modelo

RAIZ = Path(__file__).resolve().parents[1]
IFC_VERSIONADO = RAIZ / "geometry" / "fundacion_e01_ejemplo.ifc"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera un IFC4 de ejemplo con las vertidas Vertida_01..03."
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=RAIZ / "geometry" / "fundacion_e01_generada.ifc",
        help=(
            "Ruta del archivo IFC de salida. Por defecto NO es el IFC "
            "versionado editado en Bonsai."
        ),
    )
    parser.add_argument(
        "--forzar",
        action="store_true",
        help=(
            "Permite sobrescribir el IFC versionado "
            "(borra la edición hecha en Bonsai)."
        ),
    )
    args = parser.parse_args()

    ruta = args.salida
    if ruta.resolve() == IFC_VERSIONADO.resolve() and ruta.exists() and not args.forzar:
        raise SystemExit(
            f"Abortado: {ruta} es el IFC versionado editado en Bonsai "
            "(Vertida_01 = 19 °C). Regenerarlo sin --forzar borraría esa "
            "edición y haría fallar test_ifc_versionado_fue_editado_en_bonsai. "
            "Usa otra ruta con --salida, o repite con --forzar si es intencional."
        )

    ruta = guardar_modelo(ruta)
    print(f"IFC generado: {ruta}")
    print("Geometría didáctica de ejemplo; NO es la geometría oficial.")


if __name__ == "__main__":
    main()
