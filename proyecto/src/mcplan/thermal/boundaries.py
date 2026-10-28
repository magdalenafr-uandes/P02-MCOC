"""Propiedades térmicas y condiciones de borde para el solver 1D.

Convenciones:
- Temperaturas en grados Celsius (°C); las diferencias son equivalentes a kelvin.
- Longitudes en metros (m).
- Tiempo en segundos (s).
- ``k`` en W/(m·K), ``rho`` en kg/m³ y ``cp`` en J/(kg·K).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal

TipoBorde = Literal["dirichlet", "neumann", "robin"]


@dataclass(frozen=True)
class PropiedadesTermicas:
    """Propiedades constantes de un material homogéneo e isótropo."""

    k: float
    rho: float
    cp: float

    def __post_init__(self) -> None:
        if not isfinite(self.k) or self.k <= 0.0:
            raise ValueError("La conductividad k debe ser positiva [W/(m·K)].")
        if not isfinite(self.rho) or self.rho <= 0.0:
            raise ValueError("La densidad rho debe ser positiva [kg/m³].")
        if not isfinite(self.cp) or self.cp <= 0.0:
            raise ValueError("El calor específico cp debe ser positivo [J/(kg·K)].")

    @property
    def alpha(self) -> float:
        """Difusividad térmica alpha = k / (rho·cp) [m²/s]."""
        return self.k / (self.rho * self.cp)


@dataclass(frozen=True)
class CondicionBorde:
    """Condición de borde en un extremo de la barra 1D.

    - ``dirichlet``: ``valor`` es la temperatura impuesta [°C].
    - ``neumann``: ``valor`` es flujo normal saliente [W/m²]; cero adiabático.
    - ``robin``: ``valor`` es la temperatura del ambiente [°C] y ``h`` el
      coeficiente convectivo [W/(m²·K)].
    """

    tipo: TipoBorde
    valor: float = 0.0
    h: float = 0.0

    def __post_init__(self) -> None:
        if self.tipo not in ("dirichlet", "neumann", "robin"):
            raise ValueError(f"Tipo de borde no soportado: {self.tipo!r}.")
        if not isfinite(self.valor) or not isfinite(self.h):
            raise ValueError("El valor de borde y h deben ser finitos.")
        if self.tipo == "robin" and self.h < 0.0:
            raise ValueError("El coeficiente convectivo h no puede ser negativo.")
