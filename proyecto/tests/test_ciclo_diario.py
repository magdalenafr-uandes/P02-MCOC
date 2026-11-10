"""Clima sintético: procedencia, fase horaria y conexión con el caso físico."""
from datetime import datetime
from pathlib import Path
import copy

import numpy as np
import pytest

from mcplan.caso import ErrorConfiguracion, leer_config, resolver_plan
from mcplan.caso.ciclo_diario import leer_promedios, serie_diaria
from mcplan.pipeline import cargar_plan, configurar_caso

RAIZ = Path(__file__).resolve().parents[1]


def test_csv_aportados_y_media_publicada():
    tabla = leer_promedios(RAIZ / "data/clima_noviembre")
    assert tabla["valores"]["2026"] == dict(minima_C=5.5, maxima_C=28.6)
    assert all(len(huella) == 64 for huella in tabla["huellas"].values())
    assert "no son observaciones" in tabla["fuente"]


def test_extremos_fase_periodicidad_y_continuidad_en_medianoche():
    ts, temperaturas = serie_diaria(datetime(2026, 11, 27, 4), 48 * 3600, 5.5, 28.6)
    t = np.asarray(ts)
    T = np.asarray(temperaturas)
    assert np.interp(2 * 3600, t, T) == pytest.approx(5.5)
    assert np.interp(11 * 3600, t, T) == pytest.approx(28.6)
    assert np.interp(26 * 3600, t, T) == pytest.approx(5.5)
    assert np.interp(35 * 3600, t, T) == pytest.approx(28.6)
    assert T.min() >= 5.5 and T.max() <= 28.6
    assert T[0] == pytest.approx(T[-1])
    assert abs(np.interp(20 * 3600 - 1, t, T) - np.interp(20 * 3600 + 1, t, T)) < 0.01


def test_extremos_que_cruzan_medianoche_y_horas_fraccionarias():
    ts, T = serie_diaria(datetime(2026, 11, 27), 86400, 5.5, 28.6, 20.25, 4.75)
    assert np.interp(20.25 * 3600, ts, T) == pytest.approx(5.5)
    assert np.interp(4.75 * 3600, ts, T) == pytest.approx(28.6)


@pytest.mark.parametrize("parametros", [
    (30, 5, 6, 15), (5, 30, 6, 6), (5, 30, -1, 15),
    (5, 30, 6, 24), (float('nan'), 30, 6, 15), (-274, 30, 6, 15),
])
def test_ciclo_invalido(parametros):
    with pytest.raises(ValueError):
        serie_diaria(datetime(2026, 11, 27), 86400, *parametros)


def test_hora_de_obra_y_vertidas_llegan_al_motor_y_exportacion():
    p = cargar_plan(RAIZ / "configs/e08_demo.yaml")
    p.update(modo_ambiente="ciclo_diario", inicio_simulacion="2026-11-27T06:00")
    p["vertidas"][1]["inicio_h"] = 10.5
    c = configurar_caso(p)
    assert c.inicio == datetime(2026, 11, 27, 6)
    assert c.ambiente.temperatura(0) == pytest.approx(5.5)
    assert c.ambiente.temperatura(9 * 3600) == pytest.approx(28.6)
    assert c.ambiente.temperatura(24 * 3600) == pytest.approx(5.5)
    assert c.ambiente.h_viento is None and c.ambiente.emisividad == 0
    assert "ESCENARIO ESTIMADO" in c.nota_clima and "SHA-256" in c.nota_clima
    assert "clima" not in c.datos
    reproducido = leer_config(copy.deepcopy(c.datos), RAIZ)
    assert reproducido.ambiente.temperatura(9 * 3600) == pytest.approx(28.6)
    planes = resolver_plan(c, [(v, f"V{v}", {"TipoHormigon": "M1", "RetiroMoldaje_h": 72}) for v in range(1, 6)])
    assert planes[1].inicio_s == 10.5 * 3600


def test_otra_hora_de_inicio_cambia_el_aire_pero_no_la_edad_de_colocacion():
    p = cargar_plan(RAIZ / "configs/e08_demo.yaml")
    p.update(modo_ambiente="ciclo_diario", inicio_simulacion="2026-11-27T15:00")
    c = configurar_caso(p)
    assert c.ambiente.temperatura(0) == pytest.approx(28.6)
    assert c.datos["vertidas"][1]["inicio_h"] == 0


def test_sin_promedios_del_anio_no_se_extrapola_silenciosamente():
    p = cargar_plan(RAIZ / "configs/e08_demo.yaml")
    p.update(modo_ambiente="ciclo_diario", inicio_simulacion="2200-11-27T06:00")
    with pytest.raises(ValueError, match="No hay promedios"):
        configurar_caso(p)


def test_ciclo_y_snapshot_no_se_mezclan():
    c = configurar_caso(dict(cargar_plan(RAIZ / "configs/e08_demo.yaml"), modo_ambiente="ciclo_diario"))
    d = copy.deepcopy(c.datos)
    d["clima"] = {"snapshot": "no-se-debe-leer"}
    with pytest.raises(ErrorConfiguracion, match="no se mezcla"):
        leer_config(d, RAIZ)
