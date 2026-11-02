"""Snapshots meteorológicos de Open-Meteo (guía G07) -> series para ``Ambiente``.

Estructura de un snapshot (una carpeta por descarga, nunca se sobrescribe)::

    data/weather/2026-11-20T1200/
    ├── metadata.json   # source, model, retrieved_at, latitude, longitude,
    │                   # timezone, variables, units
    └── forecast.json   # respuesta de la API: {"hourly": {"time": [...], ...},
                        #                       "hourly_units": {...}}

Variables (G07): ``temperature_2m`` obligatoria; ``wind_speed_10m`` si h
depende del viento; ``shortwave_radiation`` (GHI) si hay radiación solar.
Los tiempos son locales en la ``timezone`` del snapshot, igual que
``simulacion.inicio`` y los inicios de vertida.

Horizonte incompleto (G07): si el pronóstico no cubre toda la simulación, la
cola se completa solo con un método declarado en la configuración
(``clima.completar``); por defecto es error.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

METADATA_REQUERIDA = ("source", "model", "retrieved_at", "latitude", "longitude", "timezone", "variables", "units")
VAR_T = "temperature_2m"
VAR_VIENTO = "wind_speed_10m"
VAR_G = "shortwave_radiation"
_A_M_S = {"m/s": 1.0, "km/h": 1.0 / 3.6, "mp/h": 0.44704, "kn": 0.514444}
COMPLETAR = ("error", "repetir_ultimo_dia")


@dataclass(frozen=True)
class SnapshotClima:
    carpeta: Path
    metadata: dict[str, Any]
    tiempos: tuple[datetime, ...]
    T_C: np.ndarray
    viento_m_s: np.ndarray | None
    G_W_m2: np.ndarray | None


@dataclass(frozen=True)
class SeriesClima:
    """Series relativas al inicio de la simulación [s], listas para ``Ambiente``."""

    t_s: tuple[float, ...]
    T_C: tuple[float, ...]
    viento_m_s: tuple[float, ...]
    G_W_m2: tuple[float, ...]
    horas_completadas: float  # cola agregada con el método de completado
    nota: str


def leer_snapshot(carpeta: str | Path) -> SnapshotClima:
    carpeta = Path(carpeta)
    ruta_meta, ruta_datos = carpeta / "metadata.json", carpeta / "forecast.json"
    for ruta in (ruta_meta, ruta_datos):
        if not ruta.is_file():
            raise FileNotFoundError(f"Snapshot incompleto: falta {ruta}")
    meta = json.loads(ruta_meta.read_text(encoding="utf-8"))
    faltan = [k for k in METADATA_REQUERIDA if k not in meta]
    if faltan:
        raise ValueError(f"{ruta_meta}: faltan campos de metadata {faltan} (G07).")
    datos = json.loads(ruta_datos.read_text(encoding="utf-8"))
    horario, unidades = datos.get("hourly") or {}, datos.get("hourly_units") or {}
    if "time" not in horario or VAR_T not in horario:
        raise ValueError(f"{ruta_datos}: se requieren hourly.time y hourly.{VAR_T}.")

    tiempos = tuple(datetime.fromisoformat(t) for t in horario["time"])
    if len(tiempos) < 2 or any(b <= a for a, b in zip(tiempos, tiempos[1:])):
        raise ValueError(f"{ruta_datos}: tiempos estrictamente crecientes (al menos 2).")

    def serie(variable: str, unidad_esperada: dict[str, float] | str) -> np.ndarray | None:
        if variable not in horario:
            return None
        valores = np.array([math.nan if v is None else v for v in horario[variable]], dtype=float)
        if len(valores) != len(tiempos):
            raise ValueError(f"{ruta_datos}: {variable} no tiene un valor por tiempo.")
        if not np.all(np.isfinite(valores)):
            raise ValueError(f"{ruta_datos}: {variable} tiene valores faltantes (null).")
        unidad = unidades.get(variable, "")
        if isinstance(unidad_esperada, dict):
            if unidad not in unidad_esperada:
                raise ValueError(f"{variable}: unidad {unidad!r} no soportada {sorted(unidad_esperada)}.")
            return valores * unidad_esperada[unidad]
        if unidad != unidad_esperada:
            raise ValueError(f"{variable}: unidad {unidad!r}, se esperaba {unidad_esperada!r}.")
        return valores

    return SnapshotClima(
        carpeta, meta, tiempos,
        serie(VAR_T, "°C"), serie(VAR_VIENTO, _A_M_S), serie(VAR_G, "W/m²"),
    )


def series_para_simulacion(
    snapshot: SnapshotClima, inicio: datetime, duracion_s: float, completar: str = "error",
    desplazar_anios: int = 0,
) -> SeriesClima:
    """Recorta y, si se declara, completa el snapshot para [inicio, inicio + duración].

    ``desplazar_anios`` usa el clima de otro año como **análogo** de las mismas
    fechas (p. ej. ERA5 2025 para una obra en 2026 aún sin pronóstico): suma
    años enteros a los tiempos, conservando día y hora.
    """
    if completar not in COMPLETAR:
        raise ValueError(f"clima.completar debe ser uno de {COMPLETAR}.")
    if isinstance(desplazar_anios, bool) or not isinstance(desplazar_anios, int):
        raise ValueError("clima.desplazar_anios debe ser un entero.")
    try:
        tiempos = [x.replace(year=x.year + desplazar_anios) for x in snapshot.tiempos]
    except ValueError as exc:  # 29 de febrero en un año no bisiesto
        raise ValueError(f"No se puede desplazar {desplazar_anios} años: {exc}") from exc
    t = np.array([(x - inicio).total_seconds() for x in tiempos])
    if t[-1] < 0.0:
        raise ValueError(
            f"El clima termina {tiempos[-1]:%Y-%m-%d %H:%M}, antes del inicio de la simulación "
            f"{inicio:%Y-%m-%d %H:%M}. ¿Es un análogo de otro año? Usar clima.desplazar_anios."
        )
    if t[0] > 0.0:
        raise ValueError(
            f"El clima empieza {tiempos[0]:%Y-%m-%d %H:%M}, después del inicio de la "
            f"simulación {inicio:%Y-%m-%d %H:%M}."
        )
    columnas = [snapshot.T_C, snapshot.viento_m_s, snapshot.G_W_m2]
    horas_completadas = 0.0
    nota = f"{snapshot.metadata['source']} / {snapshot.metadata['model']}, descargado {snapshot.metadata['retrieved_at']}"
    if desplazar_anios:
        nota += (f"; ANÁLOGO: clima de {snapshot.tiempos[0]:%Y-%m-%d} a {snapshot.tiempos[-1]:%Y-%m-%d} "
                 f"desplazado {desplazar_anios:+d} año(s)")
    if t[-1] < duracion_s:
        faltan_h = (duracion_s - t[-1]) / 3600.0
        if completar == "error":
            raise ValueError(
                f"El clima cubre hasta {tiempos[-1]:%Y-%m-%d %H:%M} y faltan {faltan_h:.1f} h "
                "de simulación. Declarar cómo completar la cola (clima.completar, G07)."
            )
        paso = float(np.median(np.diff(t)))
        n_dia = int(round(86400.0 / paso))
        if n_dia < 1 or len(t) < n_dia:
            raise ValueError("repetir_ultimo_dia necesita al menos 24 h de datos regulares.")
        while t[-1] < duracion_s:
            t = np.concatenate([t, t[-1] + paso * np.arange(1, n_dia + 1)])
            columnas = [None if c is None else np.concatenate([c, c[-n_dia:]]) for c in columnas]
        horas_completadas = faltan_h
        nota += f"; últimas {faltan_h:.1f} h completadas repitiendo el último día"
    dentro = (t >= -1e-9) | np.r_[t[1:] > 0.0, True]  # conserva el punto anterior al inicio
    dentro &= np.r_[True, t[:-1] < duracion_s]  # y el primero después del fin
    tt = t[dentro]
    T, v, G = (None if c is None else c[dentro] for c in columnas)
    return SeriesClima(
        tuple(tt.tolist()), tuple(T.tolist()),
        () if v is None else tuple(v.tolist()),
        () if G is None else tuple(G.tolist()),
        horas_completadas, nota,
    )
