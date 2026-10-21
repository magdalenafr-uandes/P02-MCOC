"""Modelo BIM/IFC de la fundación y lectura con IfcOpenShell."""

from .foundation import (
    PSET_FOUNDATION,
    VERTIDAS_FOUNDATION,
    construir_foundation,
    guardar_foundation,
    resumen_geometrico,
    volumen_analitico,
)
from .ifc_io import (
    CAMPOS_REQUERIDOS,
    CLASE_ESPERADA,
    PSET_HORMIGON,
    leer_modelo,
    productos_vertida,
)

__all__ = [
    "CAMPOS_REQUERIDOS",
    "CLASE_ESPERADA",
    "PSET_FOUNDATION",
    "PSET_HORMIGON",
    "VERTIDAS_FOUNDATION",
    "construir_foundation",
    "guardar_foundation",
    "leer_modelo",
    "productos_vertida",
    "resumen_geometrico",
    "volumen_analitico",
]
