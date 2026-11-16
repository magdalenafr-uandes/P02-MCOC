"""Intercambio térmico entre el hormigón y circuitos de agua recirculada."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

_CP_AGUA = 4180.0  # J/(kg K)
_RHO_AGUA = 1000.0  # kg/m³


@dataclass(frozen=True)
class Enfriamiento:
    T_agua_C: float = 15.0
    caudal_L_min: float = 12.0  # por circuito
    UA_lineal_W_mK: float = 8.0
    separacion_m: float = 1.5
    volumen_estanque_m3: float | None = 20.0  # None: entrada a temperatura regulada

    def __post_init__(self) -> None:
        positivos = {
            'caudal_L_min': self.caudal_L_min, 'UA_lineal_W_mK': self.UA_lineal_W_mK,
            'separacion_m': self.separacion_m,
        }
        if self.volumen_estanque_m3 is not None:
            positivos['volumen_estanque_m3'] = self.volumen_estanque_m3
        for nombre, valor in positivos.items():
            if not math.isfinite(valor) or valor <= 0.0:
                raise ValueError(f'Tuberías: {nombre} debe ser positivo y finito.')
        if not math.isfinite(self.T_agua_C):
            raise ValueError('Tuberías: la temperatura del agua debe ser finita.')


def trazar_circuitos(ids: np.ndarray, pasos: tuple[float, float, float],
                     vertidas: list[int], separacion_m: float) -> dict[int, list[np.ndarray]]:
    """Tramos rectos en X, distribuidos en Y a media altura de cada vertida."""
    circuitos = {}
    dy = pasos[1]
    for vid in vertidas:
        mascara = ids == vid
        niveles = np.flatnonzero(mascara.any(axis=(0, 1)))
        if not niveles.size:
            continue
        nivel = niveles[np.abs(niveles - (niveles[0] + niveles[-1]) / 2).argmin()]
        planta = mascara[:, :, nivel]
        filas_con_hormigon = np.flatnonzero(planta.any(axis=0))
        centro = (filas_con_hormigon[0] + filas_con_hormigon[-1]) / 2
        salto = max(separacion_m / dy, 1.0)
        cantidad_lado = int((filas_con_hormigon[-1] - centro) / salto)
        filas = np.floor(centro + np.arange(-cantidad_lado, cantidad_lado + 1) * salto + 0.5).astype(int)
        filas = filas[planta[:, filas].any(axis=0)]
        if not filas.size:
            filas = [filas_con_hormigon[np.abs(filas_con_hormigon - centro).argmin()]]
        tramos = []
        for fila in filas:
            columnas = np.flatnonzero(planta[:, fila])
            for contiguas in np.split(columnas, np.flatnonzero(np.diff(columnas) > 1) + 1):
                tramos.append(np.ravel_multi_index((contiguas, fila, nivel), ids.shape))
        circuitos[vid] = tramos
    return circuitos


class AguaRecirculada:
    """Un estanque mezclado alimenta circuitos paralelos, sin pérdidas al exterior."""

    def __init__(self, config: Enfriamiento, longitud_tramo_m: float) -> None:
        self.temperatura_C = config.T_agua_C
        self.capacidad_flujo_W_K = config.caudal_L_min * (_RHO_AGUA * _CP_AGUA / 60000.0)
        self.capacidad_estanque_J_K = (
            math.inf if config.volumen_estanque_m3 is None
            else config.volumen_estanque_m3 * (_RHO_AGUA * _CP_AGUA)
        )
        self._NTU = config.UA_lineal_W_mK * longitud_tramo_m / self.capacidad_flujo_W_K
        self.G_tramo_W_K = -self.capacidad_flujo_W_K * math.expm1(-self._NTU)

    def limite_dt_s(self, circuitos: list[np.ndarray]) -> float:
        G_total = self.capacidad_flujo_W_K * sum(-math.expm1(-self._NTU * len(c)) for c in circuitos)
        return self.capacidad_estanque_J_K / G_total if G_total > 0.0 else math.inf

    # [MAPA:tuberias-intercambio] cada tramo extrae potencia del voxel y calienta el agua
    def intercambiar(self, T: np.ndarray, fuente: np.ndarray, circuitos: list[np.ndarray],
                     dt_s: float, volumen_voxel: float) -> float:
        temperaturas = T.ravel()
        fuente_plana = fuente.ravel()
        P_total = 0.0
        fraccion = -math.expm1(-self._NTU)
        for circuito in circuitos:
            T_entrada = self.temperatura_C
            potencias = np.empty(circuito.size)
            for j, T_voxel in enumerate(temperaturas[circuito]):
                incremento = fraccion * (T_voxel - T_entrada)
                potencias[j] = self.capacidad_flujo_W_K * incremento
                T_entrada += incremento
            fuente_plana[circuito] -= potencias / volumen_voxel
            P_total += float(potencias.sum())
        energia_J = P_total * dt_s
        self.temperatura_C += energia_J / self.capacidad_estanque_J_K
        return energia_J
