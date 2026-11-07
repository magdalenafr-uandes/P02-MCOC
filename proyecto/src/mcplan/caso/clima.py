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

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

# [MAPA:snapshot-metadata] metadata mínima G07 + kind: forecast, reanálisis u observación
METADATA_REQUERIDA = (
    "source", "kind", "model", "retrieved_at", "latitude", "longitude", "timezone", "variables", "units",
)
VAR_T = "temperature_2m"
VAR_VIENTO = "wind_speed_10m"
VAR_G = "shortwave_radiation"
_A_M_S = {"m/s": 1.0, "km/h": 1.0 / 3.6, "mp/h": 0.44704, "kn": 0.514444}
COMPLETAR = ("error", "repetir_ultimo_dia", "respaldo")


@dataclass(frozen=True)
class SnapshotClima:
    carpeta: Path
    metadata: dict[str, Any]
    tiempos: tuple[datetime, ...]
    T_C: np.ndarray
    viento_m_s: np.ndarray | None
    G_W_m2: np.ndarray | None
    huella: str = ""  # SHA-256 (12 hex) de forecast.json: identifica el dato exacto usado

    def descripcion(self) -> str:
        m = self.metadata
        return (f"{m['source']} / {m['model']} ({m['kind']}), descargado {m['retrieved_at']}, "
                f"{self.carpeta.name}, huella {self.huella}")


@dataclass(frozen=True)
class SeriesClima:
    """Series relativas al inicio de la simulación [s], listas para ``Ambiente``."""

    t_s: tuple[float, ...]
    T_C: tuple[float, ...]
    viento_m_s: tuple[float, ...]
    G_W_m2: tuple[float, ...]
    horas_completadas: float  # cola agregada con el método de completado
    nota: str
    horas_principal: float = 0.0  # horas de la simulación cubiertas por el snapshot principal


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
    crudo = ruta_datos.read_bytes()
    # [MAPA:snapshot-huella] huella del archivo: el resultado cita exactamente qué dato usó
    huella = hashlib.sha256(crudo).hexdigest()[:12]
    datos = json.loads(crudo.decode("utf-8"))
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
        serie(VAR_T, "°C"), serie(VAR_VIENTO, _A_M_S), serie(VAR_G, "W/m²"), huella,
    )


def _relativos(snapshot: SnapshotClima, inicio: datetime, desplazar_anios: int) -> tuple[np.ndarray, list[datetime]]:
    if isinstance(desplazar_anios, bool) or not isinstance(desplazar_anios, int):
        raise ValueError("clima.desplazar_anios debe ser un entero.")
    try:
        tiempos = [x.replace(year=x.year + desplazar_anios) for x in snapshot.tiempos]
    except ValueError as exc:  # 29 de febrero en un año no bisiesto
        raise ValueError(f"No se puede desplazar {desplazar_anios} años: {exc}") from exc
    return np.array([(x - inicio).total_seconds() for x in tiempos]), tiempos


def _nota(snapshot: SnapshotClima, desplazar_anios: int) -> str:
    nota = snapshot.descripcion()
    if desplazar_anios:
        nota += (f"; ANÁLOGO: clima de {snapshot.tiempos[0]:%Y-%m-%d} a {snapshot.tiempos[-1]:%Y-%m-%d} "
                 f"desplazado {desplazar_anios:+d} año(s)")
    return nota


# [MAPA:clima] snapshot de clima -> series T, viento, radiación
def series_para_simulacion(
    snapshot: SnapshotClima, inicio: datetime, duracion_s: float, completar: str = "error",
    desplazar_anios: int = 0, respaldo: SnapshotClima | None = None, respaldo_desplazar_anios: int = 0,
) -> SeriesClima:
    """Recorta y, si se declara, completa el snapshot para [inicio, inicio + duración].

    ``desplazar_anios`` usa el clima de otro año como **análogo** de las mismas
    fechas (p. ej. ERA5 2025 para una obra en 2026 aún sin pronóstico): suma
    años enteros a los tiempos, conservando día y hora.

    Horizonte incompleto (G07), según ``completar``:

    - ``error``: el pronóstico debe cubrir toda la simulación.
    - ``repetir_ultimo_dia``: la cola repite las últimas 24 h del snapshot.
    - ``respaldo``: lo que cubre el snapshot principal (el pronóstico) sale de
      él; la cola, de ``respaldo`` (p. ej. el reanálisis de las mismas fechas).
      La nota declara cuántas horas vienen de cada fuente.
    """
    if completar not in COMPLETAR:
        raise ValueError(f"clima.completar debe ser uno de {COMPLETAR}.")
    if completar == "respaldo":
        if respaldo is None:
            raise ValueError("clima.completar 'respaldo' necesita clima.respaldo.snapshot.")
        return _con_respaldo(snapshot, inicio, duracion_s, desplazar_anios, respaldo, respaldo_desplazar_anios)
    t, tiempos = _relativos(snapshot, inicio, desplazar_anios)
    if t[-1] < 0.0:
        raise ValueError(
            f"El clima termina {tiempos[-1]:%Y-%m-%d %H:%M}, antes del inicio de la simulación "
            f"{inicio:%Y-%m-%d %H:%M}. ¿Es un análogo de otro año? Usar clima.desplazar_anios; "
            "si es un pronóstico que todavía no llega a la fecha, usar clima.completar: respaldo."
        )
    if t[0] > 0.0:
        raise ValueError(
            f"El clima empieza {tiempos[0]:%Y-%m-%d %H:%M}, después del inicio de la "
            f"simulación {inicio:%Y-%m-%d %H:%M}."
        )
    columnas = [snapshot.T_C, snapshot.viento_m_s, snapshot.G_W_m2]
    horas_completadas = 0.0
    nota = _nota(snapshot, desplazar_anios)
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
    return _recortar(t, columnas, duracion_s, horas_completadas, nota, duracion_s / 3600.0 - horas_completadas)


def _recortar(t, columnas, duracion_s, horas_completadas, nota, horas_principal) -> SeriesClima:
    dentro = (t >= -1e-9) | np.r_[t[1:] > 0.0, True]  # conserva el punto anterior al inicio
    dentro &= np.r_[True, t[:-1] < duracion_s]  # y el primero después del fin
    tt = t[dentro]
    T, v, G = (None if c is None else c[dentro] for c in columnas)
    return SeriesClima(
        tuple(tt.tolist()), tuple(T.tolist()),
        () if v is None else tuple(v.tolist()),
        () if G is None else tuple(G.tolist()),
        horas_completadas, nota, horas_principal,
    )


# [MAPA:completar-pronostico] la cola que el pronóstico no cubre sale de un snapshot de respaldo declarado
def _con_respaldo(principal: SnapshotClima, inicio: datetime, duracion_s: float, desplazar: int,
                  respaldo: SnapshotClima, desplazar_respaldo: int) -> SeriesClima:
    t, tiempos = _relativos(principal, inicio, desplazar)
    tr, tiempos_r = _relativos(respaldo, inicio, desplazar_respaldo)
    if t[0] > 0.0:
        raise ValueError(
            f"El pronóstico empieza {tiempos[0]:%Y-%m-%d %H:%M}, después del inicio de la simulación: "
            "un pronóstico se descarga antes de la obra."
        )
    corte = t[-1]  # fin del pronóstico, relativo al inicio de la simulación
    if corte >= duracion_s:
        return series_para_simulacion(principal, inicio, duracion_s, "error", desplazar)
    if tr[0] > max(corte, 0.0) or tr[-1] < duracion_s:
        raise ValueError(
            f"El respaldo ({tiempos_r[0]:%Y-%m-%d %H:%M} a {tiempos_r[-1]:%Y-%m-%d %H:%M}) no cubre la cola "
            f"desde {max(corte, 0.0) / 3600:.0f} h hasta {duracion_s / 3600:.0f} h."
        )
    columnas = []
    for nombre, a, b in (("temperatura", principal.T_C, respaldo.T_C),
                         ("viento", principal.viento_m_s, respaldo.viento_m_s),
                         ("radiación", principal.G_W_m2, respaldo.G_W_m2)):
        if (a is None) != (b is None):
            raise ValueError(f"{nombre}: está en un snapshot y no en el otro; no se pueden empalmar.")
        columnas.append(None if a is None else np.concatenate([a, b[tr > corte]]))
    tt = np.concatenate([t, tr[tr > corte]])
    horas_principal = max(0.0, min(corte, duracion_s)) / 3600.0
    horas_relleno = duracion_s / 3600.0 - horas_principal
    nota = (f"{_nota(principal, desplazar)} [cubre {horas_principal:.0f} h de {duracion_s / 3600:.0f}"
            f"{'; termina ' + format(tiempos[-1], '%Y-%m-%d %H:%M') + ', antes del inicio' if corte < 0 else ''}]"
            f"; COLA de {horas_relleno:.0f} h completada con respaldo: {_nota(respaldo, desplazar_respaldo)}")
    return _recortar(tt, columnas, duracion_s, horas_relleno, nota, horas_principal)
