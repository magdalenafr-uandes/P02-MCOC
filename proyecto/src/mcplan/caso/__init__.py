"""Caso de estudio: configuración externa y pipeline BIM -> grilla -> simulación."""

from .config import ConfigCaso, ErrorConfiguracion, aplicar_sobrescrituras, leer_config, resolver_plan
from .pipeline import ResultadoPipeline, construir_grilla, ejecutar_pipeline

__all__ = [
    "ConfigCaso",
    "ErrorConfiguracion",
    "ResultadoPipeline",
    "aplicar_sobrescrituras",
    "construir_grilla",
    "ejecutar_pipeline",
    "leer_config",
    "resolver_plan",
]
