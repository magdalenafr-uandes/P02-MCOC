"""Modelo BIM/IFC y lectura con IfcOpenShell."""

from .build_model import VERTIDAS_EJEMPLO, construir_modelo, guardar_modelo
from .ifc_io import CAMPOS_REQUERIDOS, PSET_HORMIGON, leer_modelo

__all__ = [
    "CAMPOS_REQUERIDOS",
    "PSET_HORMIGON",
    "VERTIDAS_EJEMPLO",
    "construir_modelo",
    "guardar_modelo",
    "leer_modelo",
]
