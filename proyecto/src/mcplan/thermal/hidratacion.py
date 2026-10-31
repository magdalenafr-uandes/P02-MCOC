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

MODELOS = ("exponencial", "schindler")


@dataclass(frozen=True)
class ModeloHidratacion:
    """Curva adiabática + cinética de un tipo de hormigón.

    - ``exponencial``: theta = theta_inf · (1 - exp(-t_e/tau))  (guía §24).
    - ``schindler``:   theta = theta_inf · exp(-(tau/t_e)^beta)  (curva en S).

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

    @property
    def calor_total_J_m3(self) -> float:
        """Calor de hidratación total por volumen, Q_inf = rho·cp·theta_inf [J/m³]."""
        return self.rho * self.cp * self.theta_inf_C

    def elevacion(self, te_s: np.ndarray | float) -> np.ndarray:
        """theta_ad(t_e) [K] para una edad equivalente en segundos."""
        te = np.maximum(np.asarray(te_s, dtype=float), 0.0) / HORA
        if self.modelo == "exponencial":
            return self.theta_inf_C * -np.expm1(-te / self.tau_h)
        with np.errstate(divide="ignore", over="ignore"):
            x = np.where(te > 0.0, (self.tau_h / np.where(te > 0.0, te, 1.0)) ** self.beta, np.inf)
        return self.theta_inf_C * np.exp(-x)

    def tasa_elevacion(self, te_s: np.ndarray | float) -> np.ndarray:
        """d(theta_ad)/dt_e [K/s]."""
        te = np.maximum(np.asarray(te_s, dtype=float), 0.0) / HORA
        if self.modelo == "exponencial":
            return self.theta_inf_C / (self.tau_h * HORA) * np.exp(-te / self.tau_h)
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
