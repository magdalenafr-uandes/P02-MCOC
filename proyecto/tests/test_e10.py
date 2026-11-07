"""E10: condiciones de borde, moldaje/aislación/desmolde y pipeline meteorológico."""

import json
import math
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
import yaml

from mcplan.caso import ErrorConfiguracion, aplicar_sobrescrituras, leer_config, resolver_plan
from mcplan.caso.clima import leer_snapshot, series_para_simulacion
from mcplan.thermal.bordes import (
    Ambiente,
    CapaProteccion,
    CondicionBase,
    factor_viento_log,
    resistencia_proteccion,
)
from mcplan.thermal.etapas import DominioVoxel, Hormigon, Material, ParametrosTiempo, PlanVertida, SimuladorEtapas

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = RAIZ / "configs" / "e07_caso_base.yaml"
HORA = 3600.0
HORMIGON = Material(2.22, 2400.0, 970.0)


def base_yaml():
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


# --- viento y convección ------------------------------------------------------------------

def test_perfil_logaritmico_del_viento():
    assert factor_viento_log(10.0, 2.0, 0.03) == pytest.approx(math.log(2 / 0.03) / math.log(10 / 0.03))
    assert factor_viento_log(10.0, 10.0, 0.03) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        factor_viento_log(10.0, 0.01, 0.03)  # bajo la rugosidad


def test_h_de_conveccion_usa_el_viento_en_la_superficie():
    a = Ambiente(15.0, 0.0, serie_t_s=(0.0, 1.0), serie_T_C=(15.0, 15.0), serie_viento_m_s=(5.0, 5.0),
                 h_viento=(2.8, 3.0), factor_viento=0.72)
    assert a.h_conveccion(0.0) == pytest.approx(2.8 + 3.0 * 0.72 * 5.0)


def test_doble_conteo_de_radiacion_se_rechaza():
    datos = aplicar_sobrescrituras(base_yaml(), [
        "ambiente.conveccion_viento.a_W_m2K=5.7", "ambiente.conveccion_viento.b_J_m3K=3.8",
        "ambiente.conveccion_viento.incluye_radiacion=true",
    ])
    with pytest.raises(ErrorConfiguracion, match="dos veces|otra vez"):
        leer_config(datos, base_rutas=CONFIG.parent)
    sin_onda_larga = aplicar_sobrescrituras(datos, ["ambiente.emisividad=0"])
    assert leer_config(sin_onda_larga, base_rutas=CONFIG.parent).ambiente.emisividad == 0.0


def test_caso_base_usa_correlacion_solo_convectiva_y_perfil():
    c = leer_config(base_yaml(), base_rutas=CONFIG.parent)
    assert c.ambiente.h_viento == (2.8, 3.0)
    assert c.ambiente.factor_viento == pytest.approx(factor_viento_log(10.0, 2.0, 0.03))
    assert c.ambiente.emisividad > 0.0


# --- moldaje, aislación y desmolde ------------------------------------------------------------

def test_capa_R_igual_espesor_sobre_k_y_periodo():
    madera = CapaProteccion.desde_espesor("madera", 0.018, 0.15, ["lateral"], 0.0, 72 * HORA)
    assert madera.R == pytest.approx(0.12)
    manta = CapaProteccion.desde_espesor("manta", 0.05, 0.04, ["lateral", "superior"], 72 * HORA)
    capas = [madera, manta]
    assert resistencia_proteccion(capas, 10 * HORA, "lateral") == pytest.approx(0.12)
    assert resistencia_proteccion(capas, 80 * HORA, "lateral") == pytest.approx(1.25)  # desmoldado + manta
    assert resistencia_proteccion(capas, 10 * HORA, "superior") == 0.0
    assert resistencia_proteccion(capas, 80 * HORA, "superior") == pytest.approx(1.25)
    with pytest.raises(ValueError):
        CapaProteccion("x", 1.0, frozenset({"techo"}))


def test_desmolde_en_el_plan_de_vertida():
    manta = CapaProteccion("manta", 1.25, frozenset({"lateral"}), 72 * HORA)
    p = PlanVertida(1, 6 * HORA, 18.0, "M1", R_lateral=0.12, retiro_moldaje_s=72 * HORA, capas=(manta,))
    assert p.resistencia(6 * HORA + 71 * HORA, "lateral") == pytest.approx(0.12)
    assert p.resistencia(6 * HORA + 72 * HORA, "lateral") == pytest.approx(1.25)
    assert p.resistencia(6 * HORA + 72 * HORA, "inferior") == 0.0  # la manta no va bajo la pieza


def _sim(plan, h=10.0):
    ids = np.zeros((5, 5, 5), dtype=np.int16)
    ids[1:4, 1:4, 1:4] = 1
    return SimuladorEtapas(DominioVoxel(ids, np.zeros(ids.shape, dtype=bool), 0.1), plan,
                           {"M1": Hormigon(HORMIGON)}, Ambiente(15.0, h), CondicionBase("adiabatico"),
                           ParametrosTiempo(10 * HORA))


def test_desmolde_cambia_la_conductancia_y_corta_etapas():
    manta = CapaProteccion("manta", 1.25, frozenset({"lateral", "superior"}), 5 * HORA)
    sin = _sim([PlanVertida(1, 0.0, 20.0, "M1", R_lateral=0.12, retiro_moldaje_s=5 * HORA)])
    con = _sim([PlanVertida(1, 0.0, 20.0, "M1", R_lateral=0.12, retiro_moldaje_s=5 * HORA, capas=(manta,))])
    assert 5 * HORA in sin.eventos() and 5 * HORA in con.eventos()
    activo = sin.dominio.vertida_id > 0
    k = np.where(activo, HORMIGON.k, 1e-9)
    G = {n: s._conductancias_externas(t, activo, activo, k)[0].sum()
         for n, s, t in (("moldaje", sin, 0.0), ("desmoldado", sin, 6 * HORA), ("manta", con, 6 * HORA))}
    assert G["desmoldado"] > G["moldaje"] > G["manta"]  # quitar el moldaje aumenta la pérdida; la manta la corta
    r = con.ejecutar()
    assert abs(r.balance["residuo_J"]) < 1e-10 * abs(r.balance["E_final_J"])


def test_config_moldaje_y_aislacion_desde_catalogo():
    datos = aplicar_sobrescrituras(base_yaml(), [
        "vertidas.defecto.aislacion=manta_50mm", "vertidas.defecto.aislacion_caras=[superior, lateral]",
        "vertidas.defecto.aislacion_desde_h=desmolde",
    ])
    c = leer_config(datos, base_rutas=CONFIG.parent)
    plan = {p.vertida_id: p for p in resolver_plan(c, [(1, "V1", {"Inicio_h": 0.0, "TemperaturaColocacion_C": 18.0,
                                                                    "TipoHormigon": "M1", "RetiroMoldaje_h": 72.0})])}
    p = plan[1]
    assert p.R_lateral == pytest.approx(0.12) and "madera_18mm" in p.origen["R_lateral_m2K_W"]
    (capa,) = p.capas
    assert capa.R == pytest.approx(1.25) and capa.desde_s == 72 * HORA and capa.caras == {"superior", "lateral"}


@pytest.mark.parametrize("cambio, mensaje", [
    (["vertidas.defecto.moldaje=acero_3mm"], "no está en 'protecciones'"),
    (["vertidas.defecto.aislacion_caras=[superior]"], "sin 'aislacion'"),
    (["vertidas.defecto.aislacion=manta_50mm", "vertidas.defecto.aislacion_caras=[techo]"], "aislacion_caras"),
])
def test_config_proteccion_invalida(cambio, mensaje):
    c = leer_config(aplicar_sobrescrituras(base_yaml(), cambio), base_rutas=CONFIG.parent)
    with pytest.raises(ErrorConfiguracion, match=mensaje):
        resolver_plan(c, [(1, "V1", {"Inicio_h": 0.0, "TemperaturaColocacion_C": 18.0, "TipoHormigon": "M1"})])


def test_moldaje_del_ifc_si_no_es_tbd():
    datos = base_yaml()
    del datos["vertidas"]["defecto"]["moldaje"]
    c = leer_config(datos, base_rutas=CONFIG.parent)
    pset = {"Inicio_h": 0.0, "TemperaturaColocacion_C": 18.0, "TipoHormigon": "M1", "Moldaje": "madera_18mm"}
    (p,) = resolver_plan(c, [(1, "V1", pset)])
    assert p.R_lateral == pytest.approx(0.12) and p.origen["moldaje"] == "IFC:Moldaje"
    (p_tbd,) = resolver_plan(c, [(1, "V1", dict(pset, Moldaje="TBD"))])
    assert p_tbd.R_lateral == 0.0


# --- pipeline meteorológico ---------------------------------------------------------------------

def snapshot(carpeta: Path, inicio: str, horas: int, kind="forecast determinista", T0=20.0):
    t0 = datetime.fromisoformat(inicio)
    carpeta.mkdir(parents=True)
    (carpeta / "forecast.json").write_text(json.dumps({
        "hourly_units": {"time": "iso8601", "temperature_2m": "°C", "wind_speed_10m": "m/s",
                         "shortwave_radiation": "W/m²"},
        "hourly": {"time": [(t0 + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(horas)],
                   "temperature_2m": [T0] * horas, "wind_speed_10m": [3.0] * horas,
                   "shortwave_radiation": [0.0] * horas},
    }), encoding="utf-8")
    (carpeta / "metadata.json").write_text(json.dumps({
        "source": "prueba", "kind": kind, "model": "m", "retrieved_at": "2026-11-07T20:00:00+00:00",
        "latitude": -24.95, "longitude": -70.0, "timezone": "America/Santiago",
        "variables": ["temperature_2m"], "units": {},
    }), encoding="utf-8")
    return leer_snapshot(carpeta)


def test_metadata_exige_kind_y_registra_huella(tmp_path):
    s = snapshot(tmp_path / "a", "2026-11-27T00:00", 24)
    assert len(s.huella) == 12 and s.huella in s.descripcion() and "forecast determinista" in s.descripcion()
    meta = json.loads((tmp_path / "a" / "metadata.json").read_text(encoding="utf-8"))
    del meta["kind"]
    (tmp_path / "a" / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(ValueError, match="kind"):
        leer_snapshot(tmp_path / "a")


def test_pronostico_parcial_y_cola_con_respaldo(tmp_path):
    inicio = datetime(2026, 11, 27, 0)
    pron = snapshot(tmp_path / "p", "2026-11-20T00:00", 7 * 24 + 48, T0=30.0)  # cubre 48 h
    resp = snapshot(tmp_path / "r", "2025-11-26T00:00", 20 * 24, kind="observación / reanálisis", T0=10.0)
    s = series_para_simulacion(pron, inicio, 96 * HORA, "respaldo", 0, resp, 1)
    assert s.horas_principal == pytest.approx(47.0) and s.horas_completadas == pytest.approx(49.0)
    assert "COLA de 49 h" in s.nota and resp.huella in s.nota and pron.huella in s.nota
    assert np.interp(24 * HORA, s.t_s, s.T_C) == 30.0  # del pronóstico
    assert np.interp(80 * HORA, s.t_s, s.T_C) == 10.0  # del respaldo
    with pytest.raises(ValueError, match="respaldo"):
        series_para_simulacion(pron, inicio, 96 * HORA, "respaldo")
    with pytest.raises(ValueError, match="no cubre la cola"):
        series_para_simulacion(pron, inicio, 30 * 24 * HORA, "respaldo", 0, resp, 1)


def test_pronostico_que_no_llega_a_la_fecha(tmp_path):
    inicio = datetime(2026, 11, 27, 4)
    pron = snapshot(tmp_path / "p", "2026-11-07T00:00", 16 * 24)  # termina el 22-nov
    resp = snapshot(tmp_path / "r", "2025-11-26T00:00", 20 * 24, kind="observación / reanálisis")
    with pytest.raises(ValueError, match="respaldo"):
        series_para_simulacion(pron, inicio, 336 * HORA)  # sin declarar cómo completar: error
    s = series_para_simulacion(pron, inicio, 336 * HORA, "respaldo", 0, resp, 1)
    assert s.horas_principal == 0.0 and s.horas_completadas == pytest.approx(336.0)
    assert "antes del inicio" in s.nota


def test_caso_base_declara_fuentes_del_clima():
    c = leer_config(base_yaml(), base_rutas=CONFIG.parent)
    assert "pronostico" in c.nota_clima and "COLA de 336 h" in c.nota_clima and "ANÁLOGO" in c.nota_clima
    for carpeta in ("2026-11-07T2001_pronostico", "2026-10-31T1807_historico"):
        assert leer_snapshot(RAIZ / "data" / "weather" / carpeta).huella in c.nota_clima


def test_cli_listar_clima():
    r = subprocess.run([sys.executable, str(RAIZ / "scripts" / "listar_clima.py")],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    assert "forecast determinista" in r.stdout and "reanálisis" in r.stdout and "análogo" in r.stdout
