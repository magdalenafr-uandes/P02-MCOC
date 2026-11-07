"""Condiciones de borde del caso real: ambiente, moldaje/aislación y base (E10).

Este módulo describe **qué ve cada cara expuesta del sólido**; el simulador
(``etapas.py``) lo convierte en una conductancia en serie por cara::

    q = (T_eq - T_i) / (r_media + R_protección + 1/h_tot)     [W/m²]

- ``r_media = (Δ/2)/k``: media celda de hormigón (o suelo) hasta la cara.
- ``R_protección``: moldaje y aislación activos en ese instante (``CapaProteccion``).
- ``1/h_tot``: película exterior, con ``h_tot = h_c + h_r`` (convección + onda larga).
- ``T_eq``: temperatura **sol-aire** de la orientación (``Ambiente.condiciones``).

Cada mecanismo aparece **una sola vez**: la convección en ``h_c`` (correlación
solo convectiva), la onda larga en ``h_r`` hacia el cielo y el sol en ``α·G``.
Una correlación de viento que ya incluye radiación (McAdams 5,7 + 3,8·v)
contaría la onda larga dos veces si además ``emisividad > 0``: la
configuración lo rechaza (``incluye_radiacion``).

La base de la caja (``CondicionBase``) es Dirichlet a la temperatura del suelo
profundo o adiabática; las caras laterales y superior de la caja son
adiabáticas porque los márgenes de aire y suelo las alejan del hormigón.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

from .hidratacion import CERO_ABSOLUTO_C

SIGMA = 5.670374419e-8  # Stefan-Boltzmann [W/(m²·K⁴)]
ORIENTACIONES = ("superior", "lateral", "inferior")


def orientacion(cara: str) -> str:
    """'z+' -> superior, 'z-' -> inferior, x/y -> lateral."""
    return {"z+": "superior", "z-": "inferior"}.get(cara, "lateral")


# --- viento -----------------------------------------------------------------------------

# [MAPA:viento-perfil] el viento del pronóstico (10 m) se lleva a la altura de la superficie
def factor_viento_log(altura_medicion_m: float, altura_superficie_m: float, rugosidad_m: float) -> float:
    """v(z_sup)/v(z_med) con el perfil logarítmico neutro v ∝ ln(z/z0).

    Open-Meteo entrega ``wind_speed_10m``; las correlaciones de convección usan
    el viento cerca de la superficie. Terreno abierto/desierto: z0 ≈ 0,01–0,03 m.
    """
    for nombre, valor in (("altura_medicion_m", altura_medicion_m),
                          ("altura_superficie_m", altura_superficie_m), ("rugosidad_m", rugosidad_m)):
        if not math.isfinite(valor) or valor <= 0.0:
            raise ValueError(f"{nombre} debe ser positivo y finito.")
    if min(altura_medicion_m, altura_superficie_m) <= rugosidad_m:
        raise ValueError("Las alturas deben superar la rugosidad z0.")
    return math.log(altura_superficie_m / rugosidad_m) / math.log(altura_medicion_m / rugosidad_m)


# --- ambiente (sol-aire) -------------------------------------------------------------------

@dataclass(frozen=True)
class Ambiente:
    """Intercambio de las caras expuestas con el exterior.

    Temperatura **sol-aire**: cada cara ve un ambiente equivalente

        h_tot = h_c + h_r
        T_eq  = (h_c·T_aire + h_r·T_rad + α·G·f) / h_tot

    - h_c: convección, constante (``h``) o ``a + b·(f_v·v)`` con el viento v
      [m/s] y ``f_v = factor_viento`` (perfil logarítmico, 10 m -> superficie).
    - h_r = 4·ε·σ·T_m³: onda larga linealizada hacia T_rad. La cara superior ve
      el cielo, T_cielo = 0,0552·T_aire^1,5 [K] (Swinbank); las laterales ven
      mitad cielo y mitad entorno: T_rad = (T_cielo + T_aire)/2.
    - α·G·f: radiación solar absorbida (flujo solar [W/m²]); f = 1 en la cara
      superior, ``factor_solar_lateral`` en las laterales y 0 en las inferiores.

    La radiación se absorbe y emite en la cara exterior (moldaje o aislación);
    después atraviesa R y la media celda como el resto del flujo. Series en
    segundos desde el inicio de la simulación, interpoladas linealmente.
    """

    T_C: float
    h: float  # W/(m²·K) si no hay modelo de viento; 0 y sin radiación = adiabático
    serie_t_s: tuple[float, ...] = ()
    serie_T_C: tuple[float, ...] = ()
    serie_viento_m_s: tuple[float, ...] = ()
    serie_G_W_m2: tuple[float, ...] = ()
    h_viento: tuple[float, float] | None = None  # (a, b): h_c = a + b·v
    absortividad: float = 0.0
    emisividad: float = 0.0
    factor_solar_lateral: float = 0.0
    factor_viento: float = 1.0  # v_superficie / v_medición

    def __post_init__(self) -> None:
        if not math.isfinite(self.T_C) or not math.isfinite(self.h) or self.h < 0.0:
            raise ValueError("Ambiente: T finita y h >= 0.")
        n = len(self.serie_t_s)
        if len(self.serie_T_C) != n:
            raise ValueError("Ambiente: la serie necesita igual número de tiempos y temperaturas.")
        for nombre in ("serie_viento_m_s", "serie_G_W_m2"):
            serie = getattr(self, nombre)
            if serie and len(serie) != n:
                raise ValueError(f"Ambiente: {nombre} debe tener un valor por tiempo de la serie.")
            if serie and (not np.all(np.isfinite(serie)) or min(serie) < 0.0):
                raise ValueError(f"Ambiente: {nombre} finita y no negativa.")
        if self.serie_t_s and np.any(np.diff(self.serie_t_s) <= 0.0):
            raise ValueError("Ambiente: tiempos de la serie estrictamente crecientes.")
        if self.h_viento is not None:
            if not self.serie_viento_m_s:
                raise ValueError("Ambiente: h dependiente del viento requiere la serie de viento.")
            if min(self.h_viento) < 0.0 or not all(map(math.isfinite, self.h_viento)):
                raise ValueError("Ambiente: coeficientes de viento finitos y no negativos.")
        if self.absortividad > 0.0 and not self.serie_G_W_m2:
            raise ValueError("Ambiente: absortividad > 0 requiere la serie de radiación solar.")
        for nombre in ("absortividad", "emisividad", "factor_solar_lateral"):
            if not 0.0 <= getattr(self, nombre) <= 1.0:
                raise ValueError(f"Ambiente: {nombre} en [0, 1].")
        if not math.isfinite(self.factor_viento) or self.factor_viento <= 0.0:
            raise ValueError("Ambiente: factor_viento positivo y finito.")

    def _serie(self, t: float, serie: tuple[float, ...]) -> float:
        return float(np.interp(t, self.serie_t_s, serie))

    # [MAPA:temperatura-ambiente] T del aire en t: constante o serie del snapshot interpolada
    def temperatura(self, t: float) -> float:
        if not self.serie_t_s:
            return self.T_C
        return self._serie(t, self.serie_T_C)

    # [MAPA:viento-conveccion] h_c = a + b·v_superficie (correlación solo convectiva)
    def h_conveccion(self, t: float) -> float:
        if self.h_viento is None:
            return self.h
        a, b = self.h_viento
        return a + b * self.factor_viento * self._serie(t, self.serie_viento_m_s)

    # [MAPA:sol-aire] convección + radiación de onda larga + sol -> (h_tot, T_eq) por orientación
    def condiciones(self, t: float) -> tuple[float, dict[str, float]]:
        """(h_tot, T_eq por orientación 'superior' | 'lateral' | 'inferior')."""
        T_a = self.temperatura(t)
        h_c = self.h_conveccion(t)
        G = self._serie(t, self.serie_G_W_m2) if self.serie_G_W_m2 else 0.0
        h_r = 0.0
        T_cielo = T_a
        if self.emisividad > 0.0:
            T_a_K = T_a - CERO_ABSOLUTO_C
            T_cielo = 0.0552 * T_a_K**1.5 + CERO_ABSOLUTO_C
            T_m_K = 0.5 * (T_a + T_cielo) - CERO_ABSOLUTO_C
            h_r = 4.0 * self.emisividad * SIGMA * T_m_K**3
        h_tot = h_c + h_r
        if h_tot <= 0.0:
            return 0.0, {o: T_a for o in ORIENTACIONES}
        solar = self.absortividad * G  # [MAPA:flujo-solar] flujo solar absorbido α·G [W/m²]
        T_rad = {"superior": T_cielo, "lateral": 0.5 * (T_cielo + T_a), "inferior": T_a}
        f = {"superior": 1.0, "lateral": self.factor_solar_lateral, "inferior": 0.0}
        return h_tot, {o: (h_c * T_a + h_r * T_rad[o] + solar * f[o]) / h_tot for o in ORIENTACIONES}

    @property
    def sin_intercambio(self) -> bool:
        """Caras expuestas adiabáticas: sin convección ni radiación."""
        return self.h == 0.0 and self.h_viento is None and self.emisividad == 0.0 and self.absortividad == 0.0

    def h_max(self, t0: float, t1: float) -> float:
        """Máximo de h_tot en [t0, t1] (para el paso estable)."""
        instantes = [t0, t1] + [t for t in self.serie_t_s if t0 < t < t1]
        return max(self.condiciones(t)[0] for t in instantes)


# --- moldaje y aislación ---------------------------------------------------------------------

# [MAPA:capas-proteccion] moldaje/aislación: R = e/k en serie, en ciertas caras y durante un período
@dataclass(frozen=True)
class CapaProteccion:
    """Moldaje o aislación de una vertida.

    ``R = espesor/k`` [m²K/W] se suma en serie a la película exterior en las
    caras de ``caras`` (``superior``, ``lateral``, ``inferior``) mientras
    ``desde_s <= t - inicio_vertida < hasta_s``. Desmoldar es que la capa del
    moldaje deje de estar activa: esa cara pasa a ver el aire directamente
    (o la aislación que se coloque después).
    """

    nombre: str
    R: float
    caras: frozenset[str]
    desde_s: float = 0.0
    hasta_s: float = math.inf

    def __post_init__(self) -> None:
        if not math.isfinite(self.R) or self.R < 0.0:
            raise ValueError(f"{self.nombre}: R no negativa y finita.")
        if not self.caras or not set(self.caras) <= set(ORIENTACIONES):
            raise ValueError(f"{self.nombre}: caras dentro de {ORIENTACIONES}.")
        if not (0.0 <= self.desde_s < self.hasta_s):
            raise ValueError(f"{self.nombre}: período [desde, hasta) válido y no negativo.")

    @staticmethod
    def desde_espesor(nombre: str, espesor_m: float, k_W_mK: float, caras: Iterable[str],
                      desde_s: float = 0.0, hasta_s: float = math.inf) -> CapaProteccion:
        """Capa con R = e/k (p. ej. 18 mm de madera, k = 0,15 -> 0,12 m²K/W)."""
        if not espesor_m > 0.0 or not k_W_mK > 0.0:
            raise ValueError(f"{nombre}: espesor y k positivos.")
        return CapaProteccion(nombre, espesor_m / k_W_mK, frozenset(caras), desde_s, hasta_s)

    def activa(self, t_rel_s: float) -> bool:
        return self.desde_s <= t_rel_s < self.hasta_s


# [MAPA:moldaje-retiro] R de protección en t: suma de capas activas; desmoldar quita la capa del moldaje
def resistencia_proteccion(capas: Iterable[CapaProteccion], t_rel_s: float, orientacion_cara: str) -> float:
    """R total [m²K/W] de las capas activas en ``t_rel_s`` (desde el inicio de la vertida)."""
    return sum(c.R for c in capas if orientacion_cara in c.caras and c.activa(t_rel_s))


# --- base de la caja ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CondicionBase:
    """Cara inferior de la caja (bajo el suelo, o bajo el hormigón si no hay suelo)."""

    tipo: str  # "dirichlet" | "adiabatico"
    T_C: float = math.nan

    def __post_init__(self) -> None:
        if self.tipo not in ("dirichlet", "adiabatico"):
            raise ValueError("Base: tipo 'dirichlet' o 'adiabatico'.")
        if self.tipo == "dirichlet" and not math.isfinite(self.T_C):
            raise ValueError("Base Dirichlet necesita T_C finita.")
