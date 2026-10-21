"""Lectura de vertidas desde un IFC usando IfcOpenShell.

Este módulo solo lee el archivo; no depende de Blender ni de Bonsai.

Regla de selección de vertidas (en orden de prioridad):

1. **Semántica**: todo ``IfcProduct`` que lleve el property set
   ``UANDES_HormigonMasivo`` con el campo ``VertidaID`` es una vertida.
2. **Clase IFC**: se espera ``IfcFooting``; si la clase difiere se registra
   una advertencia en el resumen, pero el objeto no se descarta (Bonsai puede
   convertir la clase al editar).
3. **Nombre**: solo se usa como etiqueta de presentación, nunca como filtro.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.util.element

PSET_HORMIGON = "UANDES_HormigonMasivo"
CLASE_ESPERADA = "IfcFooting"
CAMPOS_REQUERIDOS: tuple[str, ...] = (
    "VertidaID",
    "TipoHormigon",
    "Inicio_h",
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
    advertencias: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResumenIFC:
    """Resumen legible del modelo IFC."""

    schema: str
    proyecto: str
    unidades: tuple[str, ...]
    vertidas: tuple[VertidaIFC, ...]


def productos_vertida(modelo: ifcopenshell.file) -> list:
    """Productos que son vertidas según la regla semántica (pset + VertidaID).

    Devuelve la lista ordenada por ``VertidaID`` (y luego por nombre). El
    nombre del producto no participa en la selección.
    """
    productos: list = []
    for producto in modelo.by_type("IfcProduct"):
        psets = ifcopenshell.util.element.get_psets(producto)
        propiedades = psets.get(PSET_HORMIGON)
        if not propiedades or "VertidaID" not in propiedades:
            continue
        productos.append(producto)

    def _clave(producto):
        psets = ifcopenshell.util.element.get_psets(producto)
        vertida_id = psets[PSET_HORMIGON].get("VertidaID", 0)
        try:
            orden = int(vertida_id)
        except (TypeError, ValueError):
            orden = 0
        return (orden, producto.Name or "")

    productos.sort(key=_clave)
    return productos


def advertencias_clase(producto) -> tuple[str, ...]:
    """Advertencias de consistencia de la clase IFC de una vertida."""
    if producto.is_a() != CLASE_ESPERADA:
        return (
            f"clase IFC {producto.is_a()} distinta de la esperada "
            f"{CLASE_ESPERADA}",
        )
    return ()


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
    for producto in productos_vertida(modelo):
        psets = ifcopenshell.util.element.get_psets(producto)
        propiedades = dict(psets.get(PSET_HORMIGON, {}))
        propiedades.pop("id", None)
        tiene_geometria = bool(
            producto.Representation
            and getattr(producto.Representation, "Representations", None)
        )
        vertidas.append(
            VertidaIFC(
                nombre=producto.Name or "(sin nombre)",
                clase=producto.is_a(),
                guid=producto.GlobalId,
                tiene_geometria=tiene_geometria,
                propiedades=propiedades,
                advertencias=advertencias_clase(producto),
            )
        )

    return ResumenIFC(
        schema=modelo.schema,
        proyecto=proyecto,
        unidades=tuple(unidades),
        vertidas=tuple(vertidas),
    )
