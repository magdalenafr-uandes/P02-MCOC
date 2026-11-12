"""E12: control del paso por hidratación, vertidas escalonadas y ubicación de los máximos."""

import math
from pathlib import Path

import numpy as np
import pytest
import yaml

from mcplan.caso import ErrorConfiguracion, aplicar_sobrescrituras, leer_config
from mcplan.thermal.bordes import Ambiente, CondicionBase
from mcplan.thermal.etapas import DominioVoxel, Hormigon, Material, ParametrosTiempo, PlanVertida, SimuladorEtapas
from mcplan.thermal.hidratacion import ModeloHidratacion

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = RAIZ / "configs" / "e07_caso_base.yaml"
HORA = 3600.0
HORMIGON = Material(2.22, 2400.0, 970.0)
MEDIDA = ModeloHidratacion("exponencial", 124.0, 15.0, 2400.0, 970.0, Ea_J_mol=40000.0, T_ref_C=20.0)


def _columna(inicio_2_h, dtheta=math.inf, T0=18.0, h=0.0):
    """Dos vertidas apiladas (3×3×2 celdas cada una), adiabáticas salvo la cara superior."""
    ids = np.zeros((5, 5, 6), dtype=np.int16)
    ids[1:4, 1:4, 1:3] = 1
    ids[1:4, 1:4, 3:5] = 2
    plan = [PlanVertida(1, 0.0, T0, "M1"), PlanVertida(2, inicio_2_h * HORA, T0, "M1")]
    return SimuladorEtapas(DominioVoxel(ids, np.zeros(ids.shape, bool), 0.1), plan, {"M1": Hormigon(HORMIGON, MEDIDA)},
                           Ambiente(T0, h), CondicionBase("adiabatico"),
                           ParametrosTiempo(96 * HORA, dt_max_s=0.5 * HORA, dtheta_max_K=dtheta),
                           guardar_campos=True).ejecutar()


def test_vertida_sobre_hormigon_caliente_supera_T0_mas_theta():
    cota = 18.0 + MEDIDA.theta_inf_C
    juntas = _columna(0.0, dtheta=1.0)
    assert max(juntas.T_max_C) <= cota + 1e-6  # misma edad: nunca sobre T0 + θ∞
    escalonada = _columna(24.0, dtheta=1.0)
    # la vertida 2 se coloca sobre la 1 ya caliente: se precalienta y además libera su propio θ∞
    assert escalonada.pico(2)[0] > cota + 5.0
    assert abs(escalonada.balance["residuo_J"]) < 1e-9 * abs(escalonada.balance["E_final_J"])


def test_tope_de_theta_por_paso_resuelve_la_cinetica():
    gruesa, fina, mas_fina = (_columna(24.0, dtheta=d) for d in (math.inf, 1.0, 0.5))
    # con el tope el pico no depende del paso; sin tope la curva entera cabe en pocos pasos
    assert fina.pico(2)[0] == pytest.approx(mas_fina.pico(2)[0], abs=1.0)
    assert sum(e["pasos"] for e in fina.etapas) > sum(e["pasos"] for e in gruesa.etapas)
    with pytest.raises(ValueError, match="dtheta_max_K"):
        ParametrosTiempo(HORA, dtheta_max_K=0.0)


def test_ubicacion_de_los_maximos():
    r = _columna(24.0, dtheta=1.0, h=10.0)
    ids = np.zeros((5, 5, 6), dtype=np.int16)
    ids[1:4, 1:4, 1:3] = 1
    ids[1:4, 1:4, 3:5] = 2
    t_fin = max(r.campos)
    for vid in (1, 2):
        i_max = r.idx_max_vertida[vid][-1]
        assert ids.ravel()[i_max] == vid
        assert r.campos[t_fin].ravel()[i_max] == pytest.approx(r.T_max_vertida_C[vid][-1], abs=1e-4)
        assert ids.ravel()[r.idx_sup_vertida[vid][-1]] == vid
    assert r.cara_sup_vertida[2][-1] in ("x-", "x+", "y-", "y+", "z+")  # la 2 tiene caras laterales y superior
    assert r.idx_max_vertida[2][0] == -1  # antes de colocarse no hay ubicación


def test_config_lee_tope_de_theta():
    datos = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert leer_config(CONFIG).tiempo.dtheta_max_K == 1.0
    with pytest.raises(ErrorConfiguracion, match="dtheta_max_paso_K"):
        leer_config(aplicar_sobrescrituras(datos, ["simulacion.dtheta_max_paso_K=0"]), base_rutas=CONFIG.parent)
