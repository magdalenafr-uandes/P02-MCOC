"""Carga y validación de la configuración del sitio (configs/site.yaml)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

RUTA_POR_DEFECTO = Path("configs") / "site.yaml"


class ErrorConfiguracion(Exception):
    """Error al cargar o validar la configuración del sitio."""


@dataclass(frozen=True)
class Sitio:
    """Datos oficiales del sitio asignado al Grupo 1."""

    proyecto: str
    grupo: str
    etapa_actual: str
    parque_eolico: str
    localidad: str
    region: str
    latitud: float
    longitud: float
    zona_horaria: str
    fuente_documental: str


def cargar_sitio(ruta: Path | None = None) -> Sitio:
    """Lee y valida el YAML del sitio.

    Si ``ruta`` es None se usa :data:`RUTA_POR_DEFECTO`
    (``configs/site.yaml`` relativo al directorio de trabajo actual).
    """
    ruta = ruta if ruta is not None else RUTA_POR_DEFECTO
    if not ruta.is_file():
        raise ErrorConfiguracion(
            f"No se encontró el archivo de configuración: {ruta}. "
            "Indique la ruta con --site o ejecute desde la raíz del repositorio."
        )
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ErrorConfiguracion(f"El archivo {ruta} no es un YAML válido: {exc}") from exc

    if not isinstance(datos, dict):
        raise ErrorConfiguracion(f"El archivo {ruta} debe contener un mapa YAML.")

    campos = (
        "proyecto",
        "grupo",
        "etapa_actual",
        "parque_eolico",
        "localidad",
        "region",
        "latitud",
        "longitud",
        "zona_horaria",
        "fuente_documental",
    )
    faltantes = [c for c in campos if c not in datos]
    if faltantes:
        raise ErrorConfiguracion(
            f"El archivo {ruta} no tiene los campos requeridos: {', '.join(faltantes)}."
        )

    try:
        return Sitio(
            proyecto=str(datos["proyecto"]),
            grupo=str(datos["grupo"]),
            etapa_actual=str(datos["etapa_actual"]),
            parque_eolico=str(datos["parque_eolico"]),
            localidad=str(datos["localidad"]),
            region=str(datos["region"]),
            latitud=float(datos["latitud"]),
            longitud=float(datos["longitud"]),
            zona_horaria=str(datos["zona_horaria"]),
            fuente_documental=str(datos["fuente_documental"]),
        )
    except (TypeError, ValueError) as exc:
        raise ErrorConfiguracion(f"Valores inválidos en {ruta}: {exc}") from exc
