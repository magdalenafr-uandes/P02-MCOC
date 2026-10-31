"""Fuente de calor de hidratación a partir de una curva de elevación adiabática.

Guía de difusión §23–25. Bajo condición adiabática la energía generada solo
eleva la temperatura, así que

    rho·cp · d(theta_ad)/dt = qdot_h(t)     =>     qdot_h = rho·cp · d(theta_ad)/dt

con ``theta_ad`` [K] la elevación adiabática acumulada y ``qdot_h`` [W/m³] la
tasa volumétrica de generación.

Dependencia con la temperatura (edad equivalente, Arrhenius):

    dt_e/dt = f(T) = exp( Ea/R · (1/T_ref - 1/T) )      (T en kelvin)
    qdot_h  = rho·cp · d(theta_ad)/dt_e · f(T)

La curva se escribe en **edad equivalente** ``t_e``: a T = T_ref coincide con
la edad real; más caliente avanza más rápido. En un ensayo adiabático se cumple
``T = T_0 + theta_ad(t_e)`` exactamente, cualquiera sea ``Ea``.

Este módulo no lee archivos ni conoce el IFC: recibe los parámetros ya
resueltos desde la configuración del caso.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import numpy as np

R_GAS = 8.314462618  # constante universal de los gases [J/(mol·K)]
CERO_ABSOLUTO_C = -273.15
HORA = 3600.0

MODELOS = ("exponencial", "schindler", "tabla")


def theta_inf_desde_dosificacion(
    cemento_kg_m3: float, calor_J_kg: float, grado_ultimo: float, rho: float, cp: float
) -> float:
    """theta_inf = C·H_u·alpha_u/(rho·cp) [K] desde la dosificación.

    ``calor_J_kg``: calor total de hidratación del cemento (p. ej. ensayo de
    calor o ficha del fabricante); ``grado_ultimo``: grado de hidratación final.
    """
    for nombre, valor in (("cemento_kg_m3", cemento_kg_m3), ("calor_J_kg", calor_J_kg),
                          ("rho", rho), ("cp", cp)):
        if not isfinite(valor) or valor <= 0.0:
            raise ValueError(f"{nombre} debe ser positivo y finito.")
    if not 0.0 < grado_ultimo <= 1.0:
        raise ValueError("grado_ultimo debe estar en (0, 1].")
    return cemento_kg_m3 * calor_J_kg * grado_ultimo / (rho * cp)


@dataclass(frozen=True)
class ModeloHidratacion:
    """Curva adiabática + cinética de un tipo de hormigón.

    - ``exponencial``: theta = theta_inf · (1 - exp(-t_e/tau))  (guía §24).
    - ``schindler``:   theta = theta_inf · exp(-(tau/t_e)^beta)  (curva en S).
    - ``tabla``:       curva **medida** (t_e [h], theta [K]) a T_ref, interpolada
      linealmente; después del último punto no se genera más calor.

    ``Ea_J_mol = 0`` desactiva la dependencia con la temperatura.
    """

    modelo: str
    theta_inf_C: float
    tau_h: float
    rho: float
    cp: float
    beta: float = 1.0
    Ea_J_mol: float = 0.0
    T_ref_C: float = 20.0
    tabla_t_h: tuple[float, ...] = ()
    tabla_theta_C: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if self.modelo not in MODELOS:
            raise ValueError(f"Modelo de hidratación {self.modelo!r} no soportado: {MODELOS}.")
        for nombre in ("theta_inf_C", "tau_h", "rho", "cp", "beta", "Ea_J_mol", "T_ref_C"):
            if not isfinite(getattr(self, nombre)):
                raise ValueError(f"{nombre} debe ser finito.")
        if self.theta_inf_C < 0.0:
            raise ValueError("theta_inf_C no puede ser negativa.")
        if self.tau_h <= 0.0 or self.beta <= 0.0:
            raise ValueError("tau_h y beta deben ser positivos.")
        if self.rho <= 0.0 or self.cp <= 0.0:
            raise ValueError("rho y cp deben ser positivos.")
        if self.Ea_J_mol < 0.0:
            raise ValueError("Ea_J_mol no puede ser negativa.")
        if self.modelo == "tabla":
            t, th = np.asarray(self.tabla_t_h, float), np.asarray(self.tabla_theta_C, float)
            if len(t) < 2 or len(t) != len(th) or not np.all(np.isfinite(t)) or not np.all(np.isfinite(th)):
                raise ValueError("tabla: al menos 2 pares (t_h, theta_C) finitos.")
            if t[0] != 0.0 or th[0] != 0.0:
                raise ValueError("tabla: debe partir en (0, 0): elevación medida desde la colocación.")
            if np.any(np.diff(t) <= 0.0):
                raise ValueError("tabla: tiempos estrictamente crecientes.")
            if np.any(np.diff(th) < 0.0):
                raise ValueError("tabla: la elevación adiabática no puede disminuir.")
            if abs(th[-1] - self.theta_inf_C) > 1e-9:
                raise ValueError("tabla: theta_inf_C debe ser el último valor de la tabla.")

    @property
    def calor_total_J_m3(self) -> float:
        """Calor de hidratación total por volumen, Q_inf = rho·cp·theta_inf [J/m³]."""
        return self.rho * self.cp * self.theta_inf_C

    def elevacion(self, te_s: np.ndarray | float) -> np.ndarray:
        """theta_ad(t_e) [K] para una edad equivalente en segundos."""
        te = np.maximum(np.asarray(te_s, dtype=float), 0.0) / HORA
        if self.modelo == "exponencial":
            return self.theta_inf_C * -np.expm1(-te / self.tau_h)
        if self.modelo == "tabla":
            return np.interp(te, self.tabla_t_h, self.tabla_theta_C)
        with np.errstate(divide="ignore", over="ignore"):
            x = np.where(te > 0.0, (self.tau_h / np.where(te > 0.0, te, 1.0)) ** self.beta, np.inf)
        return self.theta_inf_C * np.exp(-x)

    def tasa_elevacion(self, te_s: np.ndarray | float) -> np.ndarray:
        """d(theta_ad)/dt_e [K/s]."""
        te = np.maximum(np.asarray(te_s, dtype=float), 0.0) / HORA
        if self.modelo == "exponencial":
            return self.theta_inf_C / (self.tau_h * HORA) * np.exp(-te / self.tau_h)
        if self.modelo == "tabla":
            t = np.asarray(self.tabla_t_h)
            pendiente = np.diff(self.tabla_theta_C) / (np.diff(t) * HORA)
            i = np.clip(np.searchsorted(t, te, side="right") - 1, 0, len(pendiente) - 1)
            return np.where(te < t[-1], pendiente[i], 0.0)
        positivo = te > 0.0
        te_seguro = np.where(positivo, te, 1.0)
        with np.errstate(over="ignore", under="ignore"):
            x = (self.tau_h / te_seguro) ** self.beta
            d = self.theta_inf_C * np.exp(-x) * self.beta * x / (te_seguro * HORA)
        return np.where(positivo, d, 0.0)

    def factor_arrhenius(self, T_C: np.ndarray | float) -> np.ndarray:
        """f(T) = dt_e/dt [-]; vale 1 en T_ref."""
        T_C = np.asarray(T_C, dtype=float)
        if self.Ea_J_mol == 0.0:
            return np.ones_like(T_C)
        T_K = T_C - CERO_ABSOLUTO_C
        if np.any(T_K <= 0.0):
            raise ValueError("Temperatura bajo el cero absoluto en el factor de Arrhenius.")
        T_ref_K = self.T_ref_C - CERO_ABSOLUTO_C
        return np.exp(self.Ea_J_mol / R_GAS * (1.0 / T_ref_K - 1.0 / T_K))

    def potencia(self, te_s: np.ndarray | float, T_C: np.ndarray | float) -> np.ndarray:
        """qdot_h [W/m³] para la edad equivalente y la temperatura actuales."""
        return self.rho * self.cp * self.tasa_elevacion(te_s) * self.factor_arrhenius(T_C)
