"""Solver térmico 1D y utilidades asociadas (avance E01)."""

from .analytics import solucion_sinusoidal
from .boundaries import CondicionBorde, PropiedadesTermicas
from .solver1d import energia_1d, limite_estabilidad, resolver_1d

__all__ = [
    "CondicionBorde",
    "PropiedadesTermicas",
    "energia_1d",
    "limite_estabilidad",
    "resolver_1d",
    "solucion_sinusoidal",
]
