"""Escenario diario estimado a partir de promedios de noviembre, no forecast."""
from __future__ import annotations

import csv
import hashlib
import math
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np


def leer_promedios(carpeta: Path) -> dict:
    """Conserva la media publicada de cada año; no promedia modelos de nuevo."""
    tablas, huellas = {}, {}
    for nombre in ("minimas", "maximas"):
        archivo = carpeta / f"{nombre}.csv"
        huellas[nombre] = hashlib.sha256(archivo.read_bytes()).hexdigest()
        with archivo.open(encoding="utf-8-sig", newline="") as entrada:
            lector = csv.DictReader(entrada, delimiter=";")
            if not lector.fieldnames or lector.fieldnames[-1] != "Valor medio de las simulaciones":
                raise ValueError(f"{archivo.name}: falta la columna de media publicada.")
            filas = {}
            for fila in lector:
                anio = int(fila[lector.fieldnames[0]])
                valor = float(fila[lector.fieldnames[-1]].replace(",", "."))
                if anio in filas or not math.isfinite(valor):
                    raise ValueError(f"{archivo.name}: año duplicado o temperatura inválida.")
                filas[anio] = valor
            tablas[nombre] = filas
    if tablas["minimas"].keys() != tablas["maximas"].keys():
        raise ValueError("Las tablas de mínimas y máximas deben cubrir los mismos años.")
    valores = {}
    for anio, minima in tablas["minimas"].items():
        maxima = tablas["maximas"][anio]
        if not -273.15 < minima <= maxima:
            raise ValueError(f"Temperaturas inválidas en {anio}.")
        valores[str(anio)] = dict(minima_C=minima, maxima_C=maxima)
    return dict(valores=valores, huellas=huellas,
                fuente="CSV aportados por el usuario; media de simulaciones climáticas de noviembre; "
                       "24.57°S, 69.58°O (distinto del sitio IFC); no son observaciones ni forecast horario")


# [MAPA:ciclo-diario] medias de noviembre -> ciclo sintético por hora local de la obra
def serie_diaria(inicio: datetime, duracion_s: float, minima_C: float, maxima_C: float,
                 hora_min: float = 6.0, hora_max: float = 15.0) -> tuple[tuple, tuple]:
    """Dos medios cosenos: calentamiento y enfriamiento, con extremos ajustables.

    Serie cada 5 minutos más extremos exactos. Repite el mismo día; no infiere
    variabilidad meteorológica ni valores de diciembre de las tablas de noviembre.
    """
    parametros = (minima_C, maxima_C, hora_min, hora_max, duracion_s)
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in parametros):
        raise ValueError("Ciclo diario: parámetros numéricos finitos.")
    if not -273.15 < minima_C <= maxima_C or not 0 <= hora_min < 24 or not 0 <= hora_max < 24 or hora_min == hora_max or duracion_s <= 0:
        raise ValueError("Ciclo diario: mín ≤ máx, duración positiva y horas distintas en [0,24).")
    if inicio.tzinfo is not None:
        raise ValueError("Ciclo diario: usar fecha y hora local sin offset, como el caso de obra.")
    medianoche = inicio.replace(hour=0, minute=0, second=0, microsecond=0)
    tiempos = {0.0, float(duracion_s)}
    tiempos.update(float(t) for t in np.arange(0, duracion_s, 300.0))
    for dia in range(-1, int(math.ceil(duracion_s / 86400)) + 2):
        for hora in (hora_min, hora_max):
            t = (medianoche + timedelta(days=dia, hours=hora) - inicio).total_seconds()
            if 0 <= t <= duracion_s:
                tiempos.add(t)
    tiempos = sorted(tiempos)
    hora_inicio = (inicio - medianoche).total_seconds() / 3600
    subida = (hora_max - hora_min) % 24
    temperaturas = []
    for t in tiempos:
        fase = (hora_inicio + t / 3600 - hora_min) % 24
        if fase <= subida:
            fraccion = (1 - math.cos(math.pi * fase / subida)) / 2
        else:
            fraccion = (1 + math.cos(math.pi * (fase - subida) / (24 - subida))) / 2
        temperaturas.append(minima_C + (maxima_C - minima_C) * fraccion)
    return tuple(tiempos), tuple(temperaturas)
