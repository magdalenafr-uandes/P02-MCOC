"""Lectura de vertidas desde un IFC usando IfcOpenShell.

Este módulo solo lee el archivo; no depende de Blender ni de Bonsai.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.util.element

PSET_HORMIGON = "Pset_HormigonMasivo"
CAMPOS_REQUERIDOS: tuple[str, ...] = (
    "VertidaID",
    "TipoHormigon",
    "InicioPlanificado",
    "TemperaturaColocacion_C",
    "Moldaje",
    "Aislacion",
    "RetiroMoldaje_h",
)


@dataclass(frozen=True)
class VertidaIFC:
    """Resumen de una vertida leída desde IFC."""

    nombre: str
    clase: str
    guid: str
    tiene_geometria: bool
    propiedades: dict[str, Any]


@dataclass(frozen=True)
class ResumenIFC:
    """Resumen legible del modelo IFC."""

    schema: str
    proyecto: str
    unidades: tuple[str, ...]
    vertidas: tuple[VertidaIFC, ...]


def leer_modelo(ruta: str | Path) -> ResumenIFC:
    """Abre un IFC y devuelve el resumen de proyecto, unidades y vertidas."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise FileNotFoundError(f"No se encontró el archivo IFC: {ruta}")

    modelo = ifcopenshell.open(str(ruta))

    proyectos = modelo.by_type("IfcProject")
    proyecto = proyectos[0].Name if proyectos else "(sin IfcProject)"

    unidades: list[str] = []
    if proyectos and proyectos[0].UnitsInContext:
        for unidad in proyectos[0].UnitsInContext.Units:
            if unidad.is_a("IfcSIUnit"):
                unidades.append(f"{unidad.UnitType}: {unidad.Name}")
            elif unidad.is_a("IfcConversionBasedUnit"):
                unidades.append(f"{unidad.UnitType}: {unidad.Name}")

    vertidas: list[VertidaIFC] = []
    for losa in modelo.by_type("IfcSlab"):
        psets = ifcopenshell.util.element.get_psets(losa)
        propiedades = dict(psets.get(PSET_HORMIGON, {}))
        propiedades.pop("id", None)
        tiene_geometria = bool(
            losa.Representation
            and getattr(losa.Representation, "Representations", None)
        )
        vertidas.append(
            VertidaIFC(
                nombre=losa.Name or "(sin nombre)",
                clase=losa.is_a(),
                guid=losa.GlobalId,
                tiene_geometria=tiene_geometria,
                propiedades=propiedades,
            )
        )

    vertidas.sort(key=lambda v: v.nombre)
    return ResumenIFC(
        schema=modelo.schema,
        proyecto=proyecto,
        unidades=tuple(unidades),
        vertidas=tuple(vertidas),
    )
