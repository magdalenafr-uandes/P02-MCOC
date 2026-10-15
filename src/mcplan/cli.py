"""Interfaz de línea de comandos de mcplan (Grupo 1)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import ErrorConfiguracion, cargar_sitio


def _crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcplan",
        description="Herramientas de planificación de vertidas de hormigón masivo (Grupo 1).",
    )
    parser.add_argument("--version", action="version", version=f"mcplan {__version__}")
    subcomandos = parser.add_subparsers(dest="comando", required=True)

    info = subcomandos.add_parser(
        "info",
        help="Muestra los datos oficiales del sitio y el estado del proyecto.",
    )
    info.add_argument(
        "--site",
        type=Path,
        default=None,
        metavar="RUTA",
        help=(
            "Archivo YAML de configuración del sitio. "
            "Por defecto se busca en configs/site.yaml relativo al directorio de trabajo."
        ),
    )
    return parser


def _cmd_info(ruta: Path | None) -> int:
    try:
        sitio = cargar_sitio(ruta)
    except ErrorConfiguracion as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("Proyecto:      ", sitio.proyecto)
    print("Grupo:         ", sitio.grupo)
    print("Etapa actual:  ", sitio.etapa_actual)
    print("Parque eólico: ", sitio.parque_eolico)
    print("Sitio:         ", f"{sitio.localidad}, Región de {sitio.region}")
    print("Latitud:       ", f"{sitio.latitud:.6f}")
    print("Longitud:      ", f"{sitio.longitud:.6f}")
    print("Zona horaria:  ", sitio.zona_horaria)
    print("Fuente:        ", sitio.fuente_documental)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _crear_parser().parse_args(argv)
    if args.comando == "info":
        return _cmd_info(args.site)
    return 1


if __name__ == "__main__":
    sys.exit(main())
