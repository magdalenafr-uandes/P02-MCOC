"""Hidratación estable en malla fina y tuberías de enfriamiento (pared Dirichlet)."""

import copy
import math
from pathlib import Path

import numpy as np
import pytest
import yaml

from mcplan.caso import ErrorConfiguracion, aplicar_sobrescrituras, leer_config
from mcplan.thermal.bordes import Ambiente, CondicionBase
from mcplan.thermal.etapas import DominioVoxel, Hormigon, Material, ParametrosTiempo, PlanVertida, SimuladorEtapas
from mcplan.thermal.hidratacion import ModeloHidratacion
from mcplan.thermal.tuberias import conductancia_pozo, tramos, trazar_tuberias

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = RAIZ / "configs" / "e07_caso_base.yaml"
HORA = 3600.0
HORMIGON = Material(2.22, 2400.0, 970.0)
# θ∞ del orden de la curva medida (124 K) con Arrhenius: el caso que antes explotaba
MEDIDA = ModeloHidratacion("exponencial", 124.0, 15.0, 2400.0, 970.0, Ea_J_mol=40000.0, T_ref_C=20.0)


# --- hidratación: el calor de un paso nunca supera lo que queda ---------------------------------

def test_calor_en_paso_no_supera_theta_inf_con_paso_grande():
    T0, T, te = 18.0, np.array([18.0]), np.array([0.0])
    for _ in range(200):  # dt de 2 h: con potencia·dt explícito esto divergía
        q, te = MEDIDA.calor_en_paso(te, T, 2 * HORA)
        T = T + q * 2 * HORA / (MEDIDA.rho * MEDIDA.cp)
        assert np.all(np.isfinite(T)) and T[0] <= T0 + MEDIDA.theta_inf_C + 1e-9
    assert T[0] == pytest.approx(T0 + float(MEDIDA.elevacion(te)[0]))  # adiabático: T = T0 + θ(te), exacto
    assert T[0] == pytest.approx(T0 + MEDIDA.theta_inf_C, abs=1e-3)


def test_cubo_adiabatico_en_malla_fina_queda_acotado():
    ids = np.zeros((6, 6, 6), dtype=np.int16)
    ids[1:5, 1:5, 1:5] = 1
    sim = SimuladorEtapas(DominioVoxel(ids, np.zeros(ids.shape, bool), 0.05), [PlanVertida(1, 0.0, 18.0, "M1")],
                          {"M1": Hormigon(HORMIGON, MEDIDA)}, Ambiente(15.0, 0.0), CondicionBase("adiabatico"),
                          ParametrosTiempo(120 * HORA, dt_max_s=0.5 * HORA))
    r = sim.ejecutar()
    assert np.all(np.isfinite(r.T_max_C))
    assert max(r.T_max_C) <= 18.0 + MEDIDA.theta_inf_C + 1e-6
    assert abs(r.balance["residuo_J"]) < 1e-9 * abs(r.balance["E_final_J"])


# --- tuberías: conductancia de pozo y trazado ---------------------------------------------------

def test_conductancia_pozo_formula_y_tubo_que_no_cabe():
    G = conductancia_pozo(2.22, 0.25, 0.25, 0.05, 0.0125)
    r_eq = 0.14 * math.hypot(0.25, 0.05)
    assert G == pytest.approx(2 * math.pi * 2.22 * 0.25 / math.log(r_eq / 0.0125))
    with pytest.raises(ValueError, match="no cabe"):
        conductancia_pozo(2.22, 0.05, 0.05, 0.05, 0.0125)  # r_eq = 9,9 mm < 12,5 mm


def _bloque():
    ids = np.zeros((14, 14, 6), dtype=np.int16)
    ids[2:12, 2:12, 1:5] = 1  # 1,0 × 1,0 × 0,4 m con paso 0,1
    return ids


def test_trazado_reparte_lineas_y_respeta_recubrimiento():
    ids = _bloque()
    t = trazar_tuberias(ids, (0.0, 0.0, 0.0), (0.1, 0.1, 0.1), "T", 1, cota_m=0.25, direccion="x",
                        separacion_m=0.3, diametro_m=0.02, T_agua_C=15.0, k_hormigon=2.22, recubrimiento_m=0.2)
    i, j, k = np.unravel_index(t.idx, ids.shape)
    assert set(k) == {2} and np.all(ids.ravel()[t.idx] == 1)
    assert len(set(j)) == 3  # huella de 1 m − 2·0,2 m = 0,6 m -> 3 líneas cada 0,3 m
    assert i.min() == 4 and i.max() == 9  # 2 celdas (0,2 m) de recubrimiento en cada extremo
    assert t.longitud_m == pytest.approx(3 * 0.6)
    assert len(tramos(t, ids.shape, (0, 0, 0), (0.1, 0.1, 0.1))) == 3
    with pytest.raises(ValueError, match="no cae dentro"):
        trazar_tuberias(ids, (0, 0, 0), (0.1, 0.1, 0.1), "T", 1, 0.9, "x", 0.3, 0.02, 15.0, 2.22)


def _sim_tubos(tuberias, T0=40.0, duracion_h=48):
    ids = _bloque()
    return SimuladorEtapas(DominioVoxel(ids, np.zeros(ids.shape, bool), 0.1), [PlanVertida(1, 0.0, T0, "M1")],
                           {"M1": Hormigon(HORMIGON)}, Ambiente(T0, 0.0), CondicionBase("adiabatico"),
                           ParametrosTiempo(duracion_h * HORA, guardar_cada_s=HORA), tuberias=tuberias).ejecutar()


def _tubo(**kw):
    datos = dict(cota_m=0.25, direccion="x", separacion_m=0.3, diametro_m=0.02, T_agua_C=15.0, k_hormigon=2.22,
                 recubrimiento_m=0.2)
    datos.update(kw)
    return trazar_tuberias(_bloque(), (0.0, 0.0, 0.0), (0.1, 0.1, 0.1), "T", 1, **datos)


def test_tuberia_dirichlet_extrae_energia_variable_y_cierra_balance():
    sin, con = _sim_tubos([]), _sim_tubos([_tubo()])
    P = np.asarray(con.potencia_tuberias_W)
    assert P.max() > 0 and P[-1] < 0.5 * P.max()  # el hormigón se enfría: el agua extrae cada vez menos
    E = con.energia_por_tuberia_J["T"]
    assert E > 0 and con.balance["tuberias_J"] == pytest.approx(E) and sin.balance["tuberias_J"] == 0.0
    assert abs(con.balance["residuo_J"]) < 1e-9 * abs(con.balance["E_final_J"])
    assert np.nanmax(con.T_max_C[-1]) < np.nanmax(sin.T_max_C[-1]) - 1.0  # sin tubos: adiabático a 40 °C
    # la energía extraída es la que falta en el hormigón (sin otras pérdidas)
    C = HORMIGON.rho * HORMIGON.cp * 0.1 ** 3
    assert E == pytest.approx(C * float(np.sum(40.0 - con.T_final[con.activo_final])), rel=1e-6)


def test_agua_mas_fria_extrae_mas_y_tuberia_apagada_no_extrae():
    fria, tibia = _sim_tubos([_tubo(T_agua_C=5.0)]), _sim_tubos([_tubo(T_agua_C=25.0)])
    assert fria.energia_por_tuberia_J["T"] > tibia.energia_por_tuberia_J["T"]
    corta = _sim_tubos([_tubo(hasta_s=12 * HORA)])
    t = np.asarray(corta.tiempos_s)
    P = np.asarray(corta.potencia_tuberias_W)
    assert np.all(P[t > 12 * HORA] == 0.0) and P[(t > 0) & (t < 12 * HORA)].min() > 0


# --- YAML y visor -------------------------------------------------------------------------------

def test_caso_base_declara_tuberias_y_se_cambian_con_set():
    datos = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert len(leer_config(CONFIG).tuberias) == 5
    d = aplicar_sobrescrituras(datos, ["tuberias.0.T_agua_C=8", "tuberias.2.separacion_m=0.75"])
    assert d["tuberias"][0]["T_agua_C"] == 8 and d["tuberias"][2]["separacion_m"] == 0.75
    assert datos["tuberias"][0]["T_agua_C"] == 15.0  # el original no cambia
    with pytest.raises(ErrorConfiguracion, match="fuera de la lista"):
        aplicar_sobrescrituras(datos, ["tuberias.9.T_agua_C=8"])
    assert aplicar_sobrescrituras(datos, ["tuberias=[]"])["tuberias"] == []


def test_config_tuberia_invalida():
    datos = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    datos["ifc"] = str((CONFIG.parent / datos["ifc"]).resolve())
    datos["tuberias"][0]["direccion"] = "z"
    ruta = RAIZ / "configs" / "_tmp_tuberias_invalida.yaml"
    try:
        ruta.write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")
        with pytest.raises((ErrorConfiguracion, ValueError)):
            leer_config(ruta)
    finally:
        ruta.unlink(missing_ok=True)


def test_visor_activa_desactiva_y_cambia_tuberias():
    from mcplan.pipeline import _aplicar_tuberias, cargar_plan
    p = cargar_plan(RAIZ / "configs" / "e08_demo.yaml")
    assert p["tuberias_ctrl"]["activas"] and p["tuberias_ctrl"]["n_circuitos"] == 5
    datos = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    d = copy.deepcopy(datos)
    _aplicar_tuberias(d, {"tuberias_ctrl": dict(activas=True, T_agua_C=10.0, separacion_m=0.75, diametro_mm=32.0)})
    assert all(c["T_agua_C"] == 10.0 and c["separacion_m"] == 0.75 and c["diametro_m"] == pytest.approx(0.032)
               for c in d["tuberias"])
    d = copy.deepcopy(datos)
    _aplicar_tuberias(d, {"tuberias_ctrl": dict(activas=False)})
    assert d["tuberias"] == []
    with pytest.raises(ValueError, match="no declara circuitos"):
        _aplicar_tuberias({"tuberias": []}, {"tuberias_ctrl": dict(activas=True, T_agua_C=10.0, separacion_m=1.0,
                                                                     diametro_mm=25.0)})
    with pytest.raises(ValueError, match="booleano"):
        _aplicar_tuberias(copy.deepcopy(datos), {"tuberias_ctrl": dict(activas="si")})
