"""Verifica cronograma, definición del diferencial y umbral del riesgo de defensa."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from mcplan.thermal.etapas import ResultadoEtapas

RAIZ = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("script_defensa", RAIZ / "scripts/defensa.py")
defensa = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(defensa)


def test_duracion_fisica_incluye_la_espera_y_conserva_volumen():
    solidos = [SimpleNamespace(vertida_id=1, volumen=80), SimpleNamespace(vertida_id=2, volumen=40)]
    unica = defensa.cronograma(solidos, 40, {"activacion": "conjunta", "espera_h": 0}, 72)
    escalonada = defensa.cronograma(solidos, 40, {"activacion": "sucesiva", "espera_h": 3}, 72)
    assert [r["activacion_h"] for r in unica] == [0, 0]
    assert [r["inicio_h"] for r in unica] == [0, 2]
    assert unica[-1]["fin_h"] == 3
    assert escalonada[-1]["activacion_h"] == 5
    assert escalonada[-1]["fin_h"] == 6
    assert sum(r["volumen_m3"] for r in unica) == sum(r["volumen_m3"] for r in escalonada) == 120


def test_diferencial_global_usa_extremos_del_mismo_instante_y_sus_ubicaciones():
    nan = float("nan")
    simulacion = ResultadoEtapas(
        tiempos_s=[0, 3600, 7200, 336 * 3600],
        T_max_C=[48, 52, 55, 20], T_sup_min_C=[39, 19, 40, 20],
        T_max_vertida_C={1: [48, 52, 55, 20], 2: [nan, 21, 41, 20]},
        T_sup_min_vertida_C={1: [39, 42, 49, 20], 2: [nan, 19, 40, 20]},
        idx_max_vertida={1: [0, 0, 0, 0], 2: [-1, 1, 1, 1]},
        idx_sup_vertida={1: [0, 0, 0, 0], 2: [-1, 1, 1, 1]},
        cara_sup_vertida={1: ["z+"] * 4, 2: ["", "x+", "x+", "x+"]},
    )
    grilla = SimpleNamespace(forma=(2, 1, 1), paso=(.5, .5, .05), definicion=SimpleNamespace(origen=(0, 0, 0)))
    resultado = SimpleNamespace(simulacion=simulacion, grilla=grilla, volumetria=[],
                                config=SimpleNamespace(criterios=SimpleNamespace(profundidad_superficie_m=.025)))
    salida = defensa.metricas(resultado)
    assert salida["T_max_C"] == 55 and salida["t_T_h"] == 2
    assert salida["delta_C"] == 33 and salida["t_delta_h"] == 1
    assert salida["delta_dentro_vertida_C"] == 10
    assert salida["punto_caliente"]["vertida"] == 1
    assert salida["punto_frio"]["vertida"] == 2
    assert salida["punto_frio"]["punto_evaluado_m"] == pytest.approx([.975, .25, .025])
    assert all(np.isfinite(salida["series"]["delta_C"]))


@pytest.mark.parametrize(("peso_falla", "cumple"), [(0.05, "si"), (0.05004, "no")])
def test_falla_doble_cuenta_una_vez_y_el_umbral_no_redondea(peso_falla, cumple):
    resultados = [
        dict(curva="a", clima="comun", I_T=1, I_delta=1, I_F=1, pico_tardio=False),
        dict(curva="b", clima="comun", I_T=0, I_delta=0, I_F=0, pico_tardio=False),
    ]
    resumen = defensa.resumir(resultados, {"a": peso_falla, "b": 1 - peso_falla}, {"comun": 1})
    assert resumen == dict(P_T=peso_falla, P_delta=peso_falla, P_F=peso_falla, cumple=cumple)
    with pytest.raises(ValueError, match="una fila"):
        defensa.resumir(resultados[:1], {"a": .05, "b": .95}, {"comun": 1})
