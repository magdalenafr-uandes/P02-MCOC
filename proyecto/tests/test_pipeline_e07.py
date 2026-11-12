"""Pipeline E07/E08: extracción IFC, voxelización, hidratación, etapas y config."""

import ast
import base64
import importlib.util
import inspect
import json
import math
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest
import yaml

from mcplan.bim.mallas_ifc import SolidoVertida, extraer_vertidas, solido_desde_malla
from mcplan.bim.foundation import VERTIDAS_FOUNDATION, volumen_analitico
from mcplan.bim.voxelizador import (
    area_expuesta,
    caras_expuestas,
    definir_grilla,
    ocupacion,
    pesos_area,
    resumen_volumetrico,
    voxelizar_solidos,
)
from mcplan.caso import ErrorConfiguracion, aplicar_sobrescrituras, ejecutar_pipeline, leer_config, resolver_plan
from mcplan.caso.clima import leer_snapshot, series_para_simulacion
from mcplan.thermal import etapas as modulo_etapas
from mcplan.thermal.etapas import (
    Ambiente,
    CondicionBase,
    DominioVoxel,
    Hormigon,
    Material,
    ParametrosTiempo,
    SIGMA,
    PlanVertida,
    SimuladorEtapas,
)
from mcplan.thermal.hidratacion import HORA, ModeloHidratacion, theta_inf_desde_dosificacion

RAIZ = Path(__file__).resolve().parents[1]
IFC = RAIZ / "geometry" / "foundation.ifc"
CONFIG = RAIZ / "configs" / "e07_caso_base.yaml"
HORMIGON = Material(2.22, 2400.0, 970.0)


def prisma(vid: int, poligono, z0: float, z1: float) -> SolidoVertida:
    """Prisma recto de un polígono convexo antihorario, con normales hacia afuera."""
    p = np.asarray(poligono, dtype=float)
    n = len(p)
    v = np.vstack([np.c_[p, np.full(n, z0)], np.c_[p, np.full(n, z1)]])
    caras = []
    for i in range(1, n - 1):
        caras.append((0, i + 1, i))  # base, normal -z
        caras.append((n, n + i, n + i + 1))  # tapa, normal +z
    for i in range(n):
        j = (i + 1) % n
        caras += [(i, j, n + j), (i, n + j, n + i)]
    return solido_desde_malla(vid, v, caras)


def rectangulo(x0, x1, y0, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def poligono_regular(n, r, rot=0.0):
    a = rot + 2 * np.pi * np.arange(n) / n
    return np.c_[r * np.cos(a), r * np.sin(a)]


# --- extracción y voxelización ------------------------------------------------------

def test_volumen_y_area_de_malla():
    s = prisma(1, rectangulo(0, 2, 0, 1), 0, 0.5)
    assert s.volumen == pytest.approx(1.0)
    assert s.area == pytest.approx(2 * (2 * 1 + 1 * 0.5 + 0.5 * 2))  # 2·(ab+bc+ca) = 7


def test_caja_alineada_volumen_y_superficie_exactos():
    s = prisma(1, rectangulo(-1, 1, -0.5, 0.5), 0, 0.5)
    g = voxelizar_solidos([s], definir_grilla([s], 0.25, 0.5, 0.5))
    assert g.volumen(1) == pytest.approx(1.0)
    a = area_expuesta(caras_expuestas(g.vertida_id > 0), g.paso)
    assert a["lateral"] == pytest.approx(2 * (2 * 0.5) + 2 * (1 * 0.5))
    assert a["superior"] == pytest.approx(2.0)
    assert a["inferior"] == 0.0  # la base toca la caja: la trata la condición de base


def test_error_de_volumen_baja_al_refinar():
    s = prisma(1, poligono_regular(8, 5.0, rot=0.3), 0, 1.0)
    errores = []
    for d in (0.4, 0.2, 0.1):
        g = voxelizar_solidos([s], definir_grilla([s], d, 2 * d, 2 * d))
        errores.append(resumen_volumetrico([s], g)[0]["e_V"])
    assert errores[2] < errores[0]
    assert errores[2] < 0.01


def test_area_staircase_no_converge_en_caras_oblicuas():
    # Cuadrado girado 45°: cada cara lateral se ve como escalera con |nx|+|ny| = √2.
    a = 4.0
    s = prisma(1, poligono_regular(4, a / math.sqrt(2), rot=np.pi / 4 + np.pi / 4), 0, 1.0)
    real = 4 * a * 1.0
    for d in (0.1, 0.05):
        g = voxelizar_solidos([s], definir_grilla([s], d, 2 * d, 2 * d))
        lateral = area_expuesta(caras_expuestas(g.vertida_id > 0), d)["lateral"]
        assert lateral / real == pytest.approx(math.sqrt(2), rel=0.03)


def test_area_corregida_converge_en_caras_oblicuas():
    a = 4.0
    s = prisma(1, poligono_regular(4, a / math.sqrt(2), rot=np.pi / 2), 0, 1.0)  # caras a 45°
    errores = []
    for d in (0.2, 0.1, 0.05):
        g = voxelizar_solidos([s], definir_grilla([s], d, 2 * d, 2 * d))
        lateral = area_expuesta(caras_expuestas(g.vertida_id > 0), d, pesos=pesos_area([s], g))["lateral"]
        errores.append(abs(lateral / (4 * a) - 1.0))
    assert errores[-1] < 0.02
    assert errores[-1] < errores[0]


def test_area_corregida_no_cambia_caras_alineadas():
    s = prisma(1, rectangulo(-1, 1, -0.5, 0.5), 0, 0.5)
    g = voxelizar_solidos([s], definir_grilla([s], 0.25, 0.5, 0.5))
    e = caras_expuestas(g.vertida_id > 0)
    assert area_expuesta(e, 0.25, pesos=pesos_area([s], g)) == pytest.approx(area_expuesta(e, 0.25))


def area_exterior_real(solidos) -> float:
    """Caras no horizontales + huella - proyección vertical de las caras oblicuas que miran arriba."""
    no_horizontal = proyeccion = 0.0
    for s in solidos:
        t = s.triangulos
        n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        A = 0.5 * np.linalg.norm(n, axis=1)
        nz = n[:, 2] / (2 * A)
        oblicua = np.abs(nz) < 0.999
        no_horizontal += A[oblicua].sum()
        proyeccion += (A * nz)[oblicua & (nz > 0)].sum()
    huella = solidos[0].volumen / (solidos[0].limites[1][2] - solidos[0].limites[0][2])
    return no_horizontal + huella - proyeccion


def test_area_exterior_fundacion_corregida_converge():
    solidos = extraer_vertidas(IFC)
    real = area_exterior_real(solidos)
    assert real == pytest.approx(373.5, abs=0.1)
    errores = []
    for d in (0.2, 0.1):
        g = voxelizar_solidos(solidos, definir_grilla(solidos, d, 2 * d, 2 * d))
        e = caras_expuestas(g.vertida_id > 0)
        staircase = area_expuesta(e, d)
        corregida = area_expuesta(e, d, pesos=pesos_area(solidos, g))
        assert (staircase["lateral"] + staircase["superior"]) / real == pytest.approx(1.30, abs=0.02)
        errores.append(abs((corregida["lateral"] + corregida["superior"]) / real - 1.0))
    assert errores[1] < errores[0]
    assert errores[1] < 0.025


def test_desempate_interfaz_horizontal_va_a_vertida_inferior():
    abajo = prisma(1, rectangulo(-1, 1, -1, 1), 0, 0.55)
    arriba = prisma(2, rectangulo(-1, 1, -1, 1), 0.55, 1.1)
    g = voxelizar_solidos([abajo, arriba], definir_grilla([abajo, arriba], 0.1, 0.2, 0.2))
    assert g.voxeles_solapados == 0
    assert g.volumen(1) == pytest.approx(4 * 0.6)  # capas con centro 0.05..0.55
    assert g.volumen(2) == pytest.approx(4 * 0.5)


def test_dz_que_divide_espesores_hace_exactas_las_interfaces():
    abajo = prisma(1, rectangulo(-1, 1, -1, 1), 0, 0.55)
    arriba = prisma(2, rectangulo(-1, 1, -1, 1), 0.55, 1.1)
    for paso, exacto in (((0.25, 0.25, 0.25), False), ((0.25, 0.25, 0.05), True)):
        g = voxelizar_solidos([abajo, arriba], definir_grilla([abajo, arriba], paso, 0.5, 0.5))
        errores = [abs(g.volumen(v) - 4 * 0.55) / (4 * 0.55) for v in (1, 2)]
        if exacto:
            assert max(errores) < 1e-9
        else:
            assert max(errores) > 0.05  # 0.55 no es múltiplo de 0.25


def test_area_expuesta_anisotropica():
    s = prisma(1, rectangulo(-1, 1, -0.5, 0.5), 0, 0.5)
    paso = (0.25, 0.25, 0.05)
    g = voxelizar_solidos([s], definir_grilla([s], paso, 0.5, 0.5))
    assert g.volumen(1) == pytest.approx(1.0)
    a = area_expuesta(caras_expuestas(g.vertida_id > 0), paso)
    assert a["lateral"] == pytest.approx(3.0)
    assert a["superior"] == pytest.approx(2.0)


def test_malla_abierta_se_rechaza():
    s = prisma(1, rectangulo(0, 1, 0, 1), 0, 1)
    abierta = SolidoVertida(1, "abierta", "", s.triangulos[1:])  # falta medio fondo
    with pytest.raises(ValueError, match="no es cerrada"):
        ocupacion(abierta, definir_grilla([s], 0.2, 0.4, 0.4))


def test_ifc_cinco_vertidas_cerradas_y_volumen():
    solidos = extraer_vertidas(IFC)
    assert [s.vertida_id for s in solidos] == [1, 2, 3, 4, 5]
    # La malla del IFC es exactamente el sólido de la definición paramétrica.
    for s, v in zip(solidos, VERTIDAS_FOUNDATION):
        assert s.volumen == pytest.approx(volumen_analitico(v), rel=1e-9)
    V = sum(s.volumen for s in solidos)
    for d, tolerancia in ((0.2, 0.015), (0.1, 0.005)):
        g = voxelizar_solidos(solidos, definir_grilla(solidos, d, 2 * d, 2 * d))
        assert g.voxeles_solapados == 0
        assert sum(g.volumen(i) for i in range(1, 6)) == pytest.approx(V, rel=tolerancia)


# --- hidratación --------------------------------------------------------------------

@pytest.mark.parametrize("modelo", ["exponencial", "schindler"])
def test_tasa_es_derivada_de_la_curva(modelo):
    h = ModeloHidratacion(modelo, 45.0, 20.0, 2400.0, 970.0, beta=0.9)
    te = np.linspace(1.0, 200.0, 50) * HORA
    eps = 1.0
    numerica = (h.elevacion(te + eps) - h.elevacion(te - eps)) / (2 * eps)
    np.testing.assert_allclose(h.tasa_elevacion(te), numerica, rtol=1e-5)
    assert h.tasa_elevacion(0.0) == pytest.approx(0.0 if modelo == "schindler" else 45.0 / (20.0 * HORA))


def test_arrhenius_y_calor_total():
    h = ModeloHidratacion("exponencial", 45.0, 30.0, 2400.0, 970.0, Ea_J_mol=40000.0, T_ref_C=20.0)
    assert h.factor_arrhenius(20.0) == pytest.approx(1.0)
    assert h.factor_arrhenius(40.0) > 2.5 > 1.0 > h.factor_arrhenius(5.0)
    t = np.linspace(0.0, 2000.0, 200001) * HORA
    Q = np.trapezoid(h.potencia(t, 20.0), t) if hasattr(np, "trapezoid") else np.trapz(h.potencia(t, 20.0), t)
    assert Q == pytest.approx(h.calor_total_J_m3, rel=1e-6)  # ρ·cp·θ∞ [J/m³]


# --- simulación por etapas ------------------------------------------------------------

def dominio_caja(forma=(5, 5, 5), activo=(slice(1, 4),) * 3, vid=1, paso=0.1):
    ids = np.zeros(forma, dtype=np.int16)
    ids[activo] = vid
    return DominioVoxel(ids, np.zeros(forma, dtype=bool), paso)


def test_adiabatico_sigue_la_curva_en_edad_equivalente():
    modelo = ModeloHidratacion("exponencial", 45.0, 30.0, 2400.0, 970.0, Ea_J_mol=40000.0, T_ref_C=20.0)
    T0 = 15.0

    # Referencia independiente: RK4 de dte/dt = f(T0 + θ(te)); en adiabático T = T0 + θ(te).
    # Se compara a las 24 h, en plena subida: a las 72 h la curva ya saturó y el calor de cada paso
    # (incremento exacto de θ, acotado por θ∞) deja un error ~1e-5 °C que no mide el orden.
    D = 24 * HORA

    def f(te):
        return modelo.factor_arrhenius(T0 + modelo.elevacion(te))

    te, h = 0.0, 30.0
    for _ in range(int(D / h)):
        k1 = f(te); k2 = f(te + h * k1 / 2); k3 = f(te + h * k2 / 2); k4 = f(te + h * k3)
        te += h * (k1 + 2 * k2 + 2 * k3 + k4) / 6
    T_ref = T0 + modelo.elevacion(te)

    errores = []
    for dt in (600.0, 300.0):
        sim = SimuladorEtapas(
            dominio_caja(), [PlanVertida(1, 0.0, T0, "M1")], {"M1": Hormigon(HORMIGON, modelo)},
            Ambiente(10.0, 0.0), CondicionBase("adiabatico"),
            ParametrosTiempo(D, dt_max_s=dt, guardar_cada_s=6 * HORA),
        )
        r = sim.ejecutar()
        T = r.T_final[r.activo_final]
        np.testing.assert_allclose(T, T.mean(), atol=1e-9)  # sin pérdidas: campo uniforme
        assert abs(r.balance["residuo_J"]) < 1e-9 * abs(r.balance["E_final_J"])
        errores.append(abs(T.mean() - T_ref))
    assert errores[1] < 0.25
    assert errores[1] / errores[0] == pytest.approx(0.5, abs=0.05)  # Arrhenius al inicio del paso: orden 1 en dt
    assert T_ref - T0 > 1.05 * modelo.elevacion(D)  # Arrhenius acelera (T > T_ref)


def test_activacion_por_etapas_y_caras_expuestas():
    ids = np.zeros((5, 5, 6), dtype=np.int16)
    ids[1:4, 1:4, 1:3] = 1
    ids[1:4, 1:4, 3:5] = 2
    dom = DominioVoxel(ids, np.zeros(ids.shape, dtype=bool), 0.1)
    plan = [PlanVertida(1, 0.0, 20.0, "M1"), PlanVertida(2, 10 * HORA, 30.0, "M1")]
    sim = SimuladorEtapas(
        dom, plan, {"M1": Hormigon(HORMIGON)}, Ambiente(15.0, 10.0), CondicionBase("adiabatico"),
        ParametrosTiempo(20 * HORA, guardar_cada_s=HORA), guardar_campos=True,
    )
    assert sim.eventos() == [0.0, 10 * HORA, 20 * HORA]
    r = sim.ejecutar()
    assert [e["nuevas"] for e in r.etapas] == [[1], [2]]
    antes = max(t for t in r.campos if t < 10 * HORA)
    assert antes > 8 * HORA
    assert np.all(r.campos[antes][ids == 2] == 15.0)  # aún no vertida: vacío a T del aire
    assert np.all(r.campos[10 * HORA][ids == 2] == 30.0)  # se activa a T de colocación
    assert all(math.isnan(x) for x in r.T_max_vertida_C[2][:10])
    # ΔT dentro de cada vertida: la 2 recién colocada (uniforme a 30 °C) no hereda
    # el contraste con la 1; el global sí los mezcla y es una cota superior.
    for vid in (1, 2):
        dv = r.delta_T_vertida_C(vid)
        assert np.all(dv[~np.isnan(dv)] <= r.delta_T_C[~np.isnan(dv)] + 1e-12)
    i = next(j for j, t in enumerate(r.tiempos_s) if t >= 10 * HORA)
    assert r.T_max_vertida_C[2][i] == 30.0 and r.T_sup_min_vertida_C[2][i] < 30.0
    assert r.delta_T_max_por_vertida()[0] <= np.nanmax(r.delta_T_C)

    # La cara superior de la vertida 1 deja de estar expuesta al cubrirla la 2.
    tapa = (slice(1, 4), slice(1, 4), 2)
    for activas, expuesta in (({1}, True), ({1, 2}, False)):
        activo = np.isin(ids, list(activas))
        k = np.where(activo, HORMIGON.k, 1e-9)
        G_amb, _ = sim._conductancias_externas(0.0, activo, activo, k)
        assert np.all(G_amb[tapa] > 0) == expuesta
    assert abs(r.balance["residuo_J"]) < 1e-9 * abs(r.balance["E_final_J"])


def test_temperatura_superficial_es_la_de_la_cara_no_la_del_centro():
    # Campo uniforme a 20 °C y aire a 15 °C: el mismo flujo cruza la media celda y la
    # película de aire, así que Ts = Ti + φ(T_aire - Ti) con φ = r_media/(r_media + 1/h).
    k, h, paso = HORMIGON.k, 10.0, (0.1, 0.1, 0.02)
    sim = SimuladorEtapas(
        DominioVoxel(dominio_caja().vertida_id, dominio_caja().es_suelo, paso),
        [PlanVertida(1, 0.0, 20.0, "M1")], {"M1": Hormigon(HORMIGON)},
        Ambiente(15.0, h), CondicionBase("adiabatico"), ParametrosTiempo(HORA, guardar_cada_s=HORA),
    )
    r = sim.ejecutar()
    phi = (0.1 / 2 / k) / (0.1 / 2 / k + 1 / h)  # la cara lateral (Δ = 0,1) es la más fría
    assert r.T_sup_min_C[0] == pytest.approx(20.0 + phi * (15.0 - 20.0))
    assert r.T_sup_min_C[0] < r.T_min_C[0]  # la cara está más fría que cualquier centro


def test_dominio_anisotropico_conserva_energia():
    ids = np.zeros((5, 5, 12), dtype=np.int16)
    ids[1:4, 1:4, 1:6] = 1
    ids[1:4, 1:4, 6:11] = 2
    modelo = ModeloHidratacion("exponencial", 40.0, 20.0, 2400.0, 970.0, Ea_J_mol=40000.0)
    sim = SimuladorEtapas(
        DominioVoxel(ids, np.zeros(ids.shape, dtype=bool), (0.2, 0.2, 0.05)),
        [PlanVertida(1, 0.0, 18.0, "M1", R_lateral=0.1, retiro_moldaje_s=4 * HORA),
         PlanVertida(2, 3 * HORA, 12.0, "M1")],
        {"M1": Hormigon(HORMIGON, modelo)}, Ambiente(10.0, 8.0), CondicionBase("dirichlet", 10.0),
        ParametrosTiempo(10 * HORA),
    )
    r = sim.ejecutar()
    assert abs(r.balance["residuo_J"]) < 1e-10 * abs(r.balance["E_final_J"])
    assert all(e["dt_s"] <= e["dt_limite_s"] for e in r.etapas)


def test_peso_de_area_escala_la_conductancia_convectiva():
    base = dominio_caja()
    activo = base.vertida_id > 0
    k = np.where(activo, HORMIGON.k, 1e-9)
    G = {}
    for nombre, pesos in (("sin", None), ("medio", {c: np.full(activo.shape, 0.5) for c in
                                                     ("x-", "x+", "y-", "y+", "z-", "z+")})):
        dom = DominioVoxel(base.vertida_id, base.es_suelo, base.paso, pesos)
        sim = SimuladorEtapas(dom, [PlanVertida(1, 0.0, 20.0, "M1")], {"M1": Hormigon(HORMIGON)},
                              Ambiente(15.0, 10.0), CondicionBase("adiabatico"), ParametrosTiempo(HORA))
        G[nombre], _ = sim._conductancias_externas(0.0, activo, activo, k)
    np.testing.assert_allclose(G["medio"], 0.5 * G["sin"])


def test_retiro_de_moldaje_aumenta_perdidas_laterales():
    plan = [PlanVertida(1, 0.0, 20.0, "M1", R_lateral=1.0, retiro_moldaje_s=5 * HORA)]
    sim = SimuladorEtapas(
        dominio_caja(), plan, {"M1": Hormigon(HORMIGON)}, Ambiente(15.0, 10.0), CondicionBase("adiabatico"),
        ParametrosTiempo(10 * HORA),
    )
    activo = sim.dominio.vertida_id > 0
    k = np.where(activo, HORMIGON.k, 1e-9)
    con, _ = sim._conductancias_externas(0.0, activo, activo, k)
    sin, _ = sim._conductancias_externas(6 * HORA, activo, activo, k)
    assert sin.sum() > con.sum()
    assert 5 * HORA in sim.eventos()


# --- configuración y desacople ----------------------------------------------------------

def test_solver_no_lee_configuracion_ni_ifc():
    importados = set()
    for nodo in ast.walk(ast.parse(inspect.getsource(modulo_etapas))):
        if isinstance(nodo, ast.Import):
            importados |= {a.name for a in nodo.names}
        elif isinstance(nodo, ast.ImportFrom):
            importados.add(nodo.module or "")
    assert not any(m.startswith(("yaml", "ifcopenshell", "mcplan.caso")) or m == "caso" for m in importados)


def test_config_base_y_prioridad_config_sobre_ifc():
    datos = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    datos = aplicar_sobrescrituras(datos, ["vertidas.2.inicio_h=12", "vertidas.defecto.R_superior_m2K_W=0.5"])
    config = leer_config(datos, base_rutas=CONFIG.parent)
    solidos = extraer_vertidas(config.ruta_ifc)
    plan = {p.vertida_id: p for p in resolver_plan(config, [(s.vertida_id, s.nombre, s.propiedades) for s in solidos])}
    assert plan[2].inicio_s == 12 * HORA and plan[2].origen["inicio_h"] == "vertidas.2"
    assert plan[3].inicio_s == 12 * HORA and plan[3].origen["inicio_h"] == "IFC:Inicio_h"
    assert plan[1].R_superior == 0.5 and plan[1].origen["R_superior_m2K_W"] == "vertidas.defecto"


@pytest.mark.parametrize("cambio, mensaje", [
    (["malla.pazo_m=0.2"], "claves desconocidas"),
    (["vertidas.9.inicio_h=1"], "no existen en el IFC"),
    (["vertidas.1.hormigon=M9"], "no está en 'hormigones'"),
    (["base.tipo=dirichlet", "base.T_C=null"], "número"),
    (["malla.corregir_area=3"], "true o false"),
])
def test_config_invalida_se_rechaza(cambio, mensaje):
    datos = aplicar_sobrescrituras(yaml.safe_load(CONFIG.read_text(encoding="utf-8")), cambio)
    with pytest.raises(ErrorConfiguracion, match=mensaje):
        config = leer_config(datos, base_rutas=CONFIG.parent)
        solidos = extraer_vertidas(config.ruta_ifc)
        resolver_plan(config, [(s.vertida_id, s.nombre, s.propiedades) for s in solidos])


def test_dato_ausente_en_config_y_en_ifc_es_error():
    config = leer_config(yaml.safe_load(CONFIG.read_text(encoding="utf-8")), base_rutas=CONFIG.parent)
    with pytest.raises(ErrorConfiguracion, match="falta 'inicio_h'"):
        resolver_plan(config, [(1, "V1", {"TemperaturaColocacion_C": 18.0, "TipoHormigon": "M1", "Inicio_h": "TBD"})])


def test_pipeline_completo_responde_a_la_configuracion():
    base = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    rapido = ["malla.paso_m=0.5", "simulacion.duracion_h=30"]
    picos = []
    for T_col in (18, 10):
        datos = aplicar_sobrescrituras(base, rapido + [f"vertidas.defecto.T_colocacion_C={T_col}"])
        r = ejecutar_pipeline(leer_config(datos, base_rutas=CONFIG.parent))
        b = r.simulacion.balance
        assert abs(b["residuo_J"]) < 1e-10 * abs(b["E_final_J"])
        picos.append(max(r.simulacion.T_max_C))
    assert picos[1] < picos[0]  # menor T de colocación => menor pico, sin tocar código


def test_correccion_de_area_reduce_perdidas_por_conveccion():
    base = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    perdidas = {}
    for corregir in (False, True):
        # Aire constante: con clima real el sol puede volver neta la ganancia y la prueba
        # dejaría de aislar el efecto del área.
        datos = aplicar_sobrescrituras(base, ["malla.paso_m=0.5", "simulacion.duracion_h=30",
                                              "clima=null", "ambiente={T_C: 15, h_W_m2K: 10}",
                                              f"malla.corregir_area={str(corregir).lower()}"])
        r = ejecutar_pipeline(leer_config(datos, base_rutas=CONFIG.parent))
        perdidas[corregir] = -r.simulacion.balance["ambiente_J"]
        assert r.area_exterior_corregida_m2["total"] < r.area_exterior_m2["total"]
    assert 0.6 < perdidas[True] / perdidas[False] < 0.95  # menos área real => menos pérdida


def test_cli_pipeline():
    script = RAIZ / "scripts" / "pipeline_e07.py"
    ok = subprocess.run([sys.executable, str(script), "--solo-grilla", "--set", "malla.paso_m=0.5"],
                        capture_output=True, text=True, encoding="utf-8")
    assert ok.returncode == 0, ok.stderr
    assert "solapados = 0" in ok.stdout
    mal = subprocess.run([sys.executable, str(script), "--solo-grilla", "--set", "malla.pazo_m=0.5"],
                         capture_output=True, text=True, encoding="utf-8")
    assert mal.returncode == 2 and "pazo_m" in mal.stderr


# --- hidratación desde datos medidos ------------------------------------------------------

def test_hidratacion_tabla_medida():
    tabla = ((0.0, 12.0, 24.0, 72.0), (0.0, 10.0, 25.0, 40.0))
    h = ModeloHidratacion("tabla", 40.0, 1.0, 2400.0, 970.0, tabla_t_h=tabla[0], tabla_theta_C=tabla[1])
    assert h.elevacion(18 * HORA) == pytest.approx(17.5)
    assert h.tasa_elevacion(18 * HORA) == pytest.approx(15.0 / (12 * HORA))
    assert h.tasa_elevacion(100 * HORA) == 0.0  # después de la tabla no hay más calor
    with pytest.raises(ValueError, match="no puede disminuir"):
        ModeloHidratacion("tabla", 5.0, 1.0, 2400.0, 970.0, tabla_t_h=(0.0, 1.0, 2.0), tabla_theta_C=(0.0, 6.0, 5.0))


def test_theta_inf_desde_dosificacion_y_config():
    # 350 kg/m³ · 450 kJ/kg · 0,8 / (2400·970) = 54,1 K
    assert theta_inf_desde_dosificacion(350, 450e3, 0.8, 2400, 970) == pytest.approx(54.12, abs=0.01)
    base = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    # Parte de la curva pedagógica (el caso base usa la fuente medida: test_fuente_calor.py).
    base["hormigones"]["M1"]["hidratacion"] = {"modelo": "exponencial", "theta_inf_C": 45.0, "tau_h": 30.0,
                                               "beta": 1.0, "Ea_J_mol": 40000, "T_ref_C": 20.0}
    dosis = aplicar_sobrescrituras(base, [
        "hormigones.M1.hidratacion.cemento_kg_m3=350", "hormigones.M1.hidratacion.calor_cemento_J_kg=450000",
        "hormigones.M1.hidratacion.grado_hidratacion_ultimo=0.8",
    ])
    with pytest.raises(ErrorConfiguracion, match="no ambas"):
        leer_config(dosis, base_rutas=CONFIG.parent)
    del dosis["hormigones"]["M1"]["hidratacion"]["theta_inf_C"]
    c = leer_config(dosis, base_rutas=CONFIG.parent)
    assert c.hormigones["M1"].hidratacion.theta_inf_C == pytest.approx(54.12, abs=0.01)
    tabla = aplicar_sobrescrituras(base, ["hormigones.M1.hidratacion.modelo=tabla",
                                          "hormigones.M1.hidratacion.tabla=[[0,0],[24,30],[168,45]]"])
    for clave in ("theta_inf_C", "tau_h", "beta"):
        del tabla["hormigones"]["M1"]["hidratacion"][clave]
    assert leer_config(tabla, base_rutas=CONFIG.parent).hormigones["M1"].hidratacion.theta_inf_C == 45.0


# --- clima, radiación y fechas --------------------------------------------------------------

def test_temperatura_sol_aire():
    a = Ambiente(15.0, 10.0, serie_t_s=(0.0, 1.0), serie_T_C=(15.0, 15.0), serie_G_W_m2=(600.0, 600.0),
                 absortividad=0.5)
    h, T_eq = a.condiciones(0.0)
    assert h == 10.0
    assert T_eq["superior"] == pytest.approx(15.0 + 0.5 * 600.0 / 10.0)  # +30 K por el sol
    assert T_eq["lateral"] == T_eq["inferior"] == 15.0
    noche = Ambiente(15.0, 10.0, emisividad=0.9)
    h, T_eq = noche.condiciones(0.0)
    T_cielo = 0.0552 * 288.15**1.5 - 273.15
    h_r = 4 * 0.9 * SIGMA * (0.5 * (288.15 + T_cielo + 273.15)) ** 3
    assert h == pytest.approx(10.0 + h_r)
    assert T_eq["superior"] == pytest.approx((10 * 15 + h_r * T_cielo) / (10 + h_r))
    assert T_eq["superior"] < T_eq["lateral"] < 15.0  # la cara superior ve el cielo frío
    viento = Ambiente(15.0, 0.0, serie_t_s=(0.0, 1.0), serie_T_C=(15.0, 15.0), serie_viento_m_s=(2.0, 2.0),
                      h_viento=(5.7, 3.8))
    assert viento.condiciones(0.0)[0] == pytest.approx(5.7 + 3.8 * 2.0)


def test_sol_calienta_y_el_balance_cierra():
    serie_t = tuple(np.arange(0, 25) * HORA)
    G = tuple(max(0.0, 800.0 * math.sin(math.pi * (t / HORA - 6) / 12)) for t in serie_t)  # día de 6 a 18 h
    resultados = {}
    for alfa in (0.0, 0.7):
        sim = SimuladorEtapas(
            dominio_caja(), [PlanVertida(1, 0.0, 15.0, "M1")], {"M1": Hormigon(HORMIGON)},
            Ambiente(15.0, 10.0, serie_t_s=serie_t, serie_T_C=(15.0,) * 25, serie_G_W_m2=G,
                     absortividad=alfa, emisividad=0.9),
            CondicionBase("adiabatico"), ParametrosTiempo(24 * HORA),
        )
        r = sim.ejecutar()
        assert abs(r.balance["residuo_J"]) < 1e-10 * abs(r.balance["E_final_J"])
        resultados[alfa] = float(r.T_final[r.activo_final].mean())
    assert resultados[0.0] < 15.0  # sin sol, la radiación al cielo enfría
    assert resultados[0.7] > resultados[0.0] + 0.2  # solo la cara superior (1/6 del área) recibe sol


def snapshot_sintetico(carpeta: Path, inicio="2026-11-27T00:00", horas=48, viento_kmh=7.2):
    t0 = datetime.fromisoformat(inicio)
    tiempos = [(t0 + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(horas)]
    carpeta.mkdir(parents=True)
    (carpeta / "forecast.json").write_text(json.dumps({
        "hourly_units": {"time": "iso8601", "temperature_2m": "°C", "wind_speed_10m": "km/h",
                         "shortwave_radiation": "W/m²"},
        "hourly": {
            "time": tiempos,
            "temperature_2m": [15 + 5 * math.sin(2 * math.pi * (i - 9) / 24) for i in range(horas)],
            "wind_speed_10m": [viento_kmh] * horas,
            "shortwave_radiation": [max(0.0, 700 * math.sin(math.pi * ((i % 24) - 6) / 12)) for i in range(horas)],
        },
    }), encoding="utf-8")
    (carpeta / "metadata.json").write_text(json.dumps({
        "source": "sintético", "kind": "prueba sintética", "model": "prueba", "retrieved_at": "2026-11-20T12:00:00+00:00",
        "latitude": -33.4, "longitude": -70.6, "timezone": "America/Santiago",
        "variables": ["temperature_2m", "wind_speed_10m", "shortwave_radiation"], "units": {},
    }), encoding="utf-8")
    return carpeta


def test_snapshot_clima_unidades_y_horizonte(tmp_path):
    snap = leer_snapshot(snapshot_sintetico(tmp_path / "s"))
    assert snap.viento_m_s[0] == pytest.approx(2.0)  # 7,2 km/h
    inicio = datetime(2026, 11, 27, 4)
    s = series_para_simulacion(snap, inicio, 24 * HORA)
    assert s.t_s[0] <= 0.0 <= s.t_s[1] and s.t_s[-1] >= 24 * HORA and s.horas_completadas == 0.0
    with pytest.raises(ValueError, match="completar"):
        series_para_simulacion(snap, inicio, 72 * HORA)
    larga = series_para_simulacion(snap, inicio, 72 * HORA, "repetir_ultimo_dia")
    assert larga.t_s[-1] >= 72 * HORA and larga.horas_completadas > 0 and "completadas" in larga.nota
    with pytest.raises(ValueError, match="después del inicio"):
        series_para_simulacion(snap, datetime(2026, 11, 26), 3600.0)


def test_clima_analogo_de_otro_anio(tmp_path):
    snap = leer_snapshot(snapshot_sintetico(tmp_path / "s", inicio="2025-11-27T00:00"))
    with pytest.raises(ValueError, match="desplazar_anios"):
        series_para_simulacion(snap, datetime(2026, 11, 27, 4), 24 * HORA)
    s = series_para_simulacion(snap, datetime(2026, 11, 27, 4), 24 * HORA, desplazar_anios=1)
    assert "ANÁLOGO" in s.nota and "2025-11-27" in s.nota
    # misma hora del día: a las 04:00 el valor es el de las 04:00 de 2025
    assert np.interp(0.0, s.t_s, s.T_C) == pytest.approx(snap.T_C[4])


def test_superficie_a_la_profundidad_del_criterio():
    k, h, paso = HORMIGON.k, 10.0, (0.1, 0.1, 0.1)

    def T_sup(profundidad):
        sim = SimuladorEtapas(
            DominioVoxel(dominio_caja().vertida_id, dominio_caja().es_suelo, paso),
            [PlanVertida(1, 0.0, 20.0, "M1")], {"M1": Hormigon(HORMIGON)},
            Ambiente(15.0, h), CondicionBase("adiabatico"), ParametrosTiempo(HORA, guardar_cada_s=HORA),
            profundidad_superficie_m=profundidad,
        )
        return sim.ejecutar().T_sup_min_C[0]

    phi = (0.05 / k) / (0.05 / k + 1 / h)
    Ts = 20.0 + phi * (15.0 - 20.0)
    assert T_sup(0.0) == pytest.approx(Ts)  # la cara
    assert T_sup(0.025) == pytest.approx(0.5 * (Ts + 20.0))  # mitad entre cara y centro
    assert T_sup(0.05) == pytest.approx(20.0)  # el centro del voxel superficial
    assert T_sup(0.2) == pytest.approx(20.0)  # más hondo que el centro: se usa el centro


def test_criterios_en_config():
    base = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    c = leer_config(base, base_rutas=CONFIG.parent)
    assert (c.criterios.T_max_C, c.criterios.delta_T_C, c.criterios.profundidad_superficie_m) == (70.0, 20.0, 0.025)
    assert c.tiempo.duracion_s == 14 * 24 * HORA
    assert "ANÁLOGO" in c.nota_clima
    with pytest.raises(ErrorConfiguracion, match="claves desconocidas"):
        leer_config(aplicar_sobrescrituras(base, ["criterios.Tmax=70"]), base_rutas=CONFIG.parent)


def test_config_con_clima_y_fechas(tmp_path):
    carpeta = snapshot_sintetico(tmp_path / "weather" / "s")
    datos = aplicar_sobrescrituras(yaml.safe_load(CONFIG.read_text(encoding="utf-8")), [
        "simulacion.inicio=2026-11-27T04:00", "simulacion.duracion_h=24",
        f"clima.snapshot={carpeta.as_posix()}", "clima.desplazar_anios=0",
        "clima.completar=error", "clima.respaldo=null",
        "ambiente.conveccion_viento={a_W_m2K: 5.7, b_J_m3K: 3.8}",
        "ambiente.absortividad_solar=0.6", "ambiente.emisividad=0.9",
        "vertidas.2.inicio=2026-11-27T10:30",
    ])
    c = leer_config(datos, base_rutas=CONFIG.parent)
    assert c.ambiente.h_viento == (5.7, 3.8) and c.ambiente.serie_G_W_m2
    assert "sintético" in c.nota_clima
    solidos = extraer_vertidas(c.ruta_ifc)
    plan = {p.vertida_id: p for p in resolver_plan(c, [(s.vertida_id, s.nombre, s.propiedades) for s in solidos])}
    assert plan[2].inicio_s == pytest.approx(6.5 * HORA)
    assert plan[1].inicio_s == 0.0  # del IFC
    sin_inicio = dict(datos, simulacion={k: v for k, v in datos["simulacion"].items() if k != "inicio"})
    with pytest.raises(ErrorConfiguracion, match="simulacion.inicio"):
        leer_config(sin_inicio, base_rutas=CONFIG.parent)
    largo = aplicar_sobrescrituras(datos, ["simulacion.duracion_h=100"])
    with pytest.raises(ErrorConfiguracion, match="completar"):
        leer_config(largo, base_rutas=CONFIG.parent)


def _cargar_script(nombre: str):
    spec = importlib.util.spec_from_file_location(nombre, RAIZ / "scripts" / f"{nombre}.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_snapshot_de_descarga_no_se_sobrescribe(tmp_path):
    modulo = _cargar_script("descargar_clima")
    url = modulo.construir_url("pronostico", -33.45, -70.66, date(2026, 11, 27), date(2026, 12, 11), None)
    assert "hourly=temperature_2m%2Cwind_speed_10m%2Cshortwave_radiation" in url and "wind_speed_unit=ms" in url
    respuesta = json.loads((snapshot_sintetico(tmp_path / "s") / "forecast.json").read_text(encoding="utf-8"))
    momento = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
    carpeta = modulo.guardar_snapshot(respuesta, url, "pronostico", None, -33.45, -70.66, tmp_path / "w", momento)
    assert leer_snapshot(carpeta).metadata["model"] == "best_match"
    with pytest.raises(FileExistsError):
        modulo.guardar_snapshot(respuesta, url, "pronostico", None, -33.45, -70.66, tmp_path / "w", momento)


def test_richardson():
    modulo = _cargar_script("convergencia_e07")
    f = [1.0 + 0.4**2, 1.0 + 0.2**2, 1.0 + 0.1**2]  # f = 1 + Δ²: orden 2, límite 1
    p, extrapolado = modulo.richardson(f)
    assert p == pytest.approx(2.0) and extrapolado == pytest.approx(1.0)
    assert math.isnan(modulo.richardson([1.0, 2.0, 1.5])[0])


# --- E08: visualización, apoyo de vertidas y comparación ------------------------------------

def _leer_vti(ruta: Path) -> dict[str, np.ndarray]:
    """Lector mínimo del .vti que escribe visualizacion.py (verifica el formato)."""
    import xml.etree.ElementTree as ET
    import struct as st
    raiz = ET.parse(ruta).getroot()
    tipos = {"Float32": np.float32, "Int16": np.int16, "UInt8": np.uint8}
    img = raiz.find("ImageData")
    nx, ny, nz = (int(v) for v in img.get("WholeExtent").split()[1::2])
    campos = {}
    for arr in raiz.iter("DataArray"):
        crudo = base64.b64decode(arr.text)
        n = st.unpack("<Q", crudo[:8])[0]
        campos[arr.get("Name")] = np.frombuffer(crudo[8:8 + n], dtype=tipos[arr.get("type")]).reshape(
            (nx, ny, nz), order="F")
    return campos


def test_vti_ida_y_vuelta(tmp_path):
    from mcplan.visualizacion import escribir_vti
    s = prisma(1, rectangulo(-1, 1, -0.5, 0.5), 0, 0.5)
    g = voxelizar_solidos([s], definir_grilla([s], (0.25, 0.25, 0.1), 0.5, 0.5))
    T = np.random.default_rng(0).random(g.forma).astype(np.float32)
    ruta = escribir_vti(tmp_path / "t.vti", g, {"temperatura": T, "vertida_id": g.vertida_id.astype(np.int16)})
    leido = _leer_vti(ruta)
    np.testing.assert_array_equal(leido["temperatura"], T)
    np.testing.assert_array_equal(leido["vertida_id"], g.vertida_id)
    texto = ruta.read_text(encoding="ascii")
    assert 'Spacing="0.25 0.25 0.1"' in texto


def test_serie_vtk_y_campos_cada(tmp_path):
    from mcplan.visualizacion import escribir_serie_vtk
    s = prisma(1, rectangulo(-0.3, 0.3, -0.3, 0.3), 0, 0.3)
    g = voxelizar_solidos([s], definir_grilla([s], 0.1, 0.2, 0.2))
    plan = [PlanVertida(1, 2 * HORA, 20.0, "M1")]
    sim = SimuladorEtapas(
        DominioVoxel(g.vertida_id, g.es_suelo, g.paso), plan, {"M1": Hormigon(HORMIGON)},
        Ambiente(15.0, 10.0), CondicionBase("adiabatico"), ParametrosTiempo(10 * HORA, guardar_cada_s=HORA),
        guardar_campos=True, campos_cada_s=4 * HORA,
    )
    r = sim.ejecutar()
    # Registros exactos cada 4 h, más activación y final.
    assert sorted(t / HORA for t in r.campos) == pytest.approx([0.0, 2.0, 4.0, 8.0, 10.0], abs=1e-10)
    assert all(c.dtype == np.float32 for c in r.campos.values())
    pvd = escribir_serie_vtk(tmp_path / "vtk", g, plan, r)
    assert pvd.read_text(encoding="ascii").count("<DataSet") == 5
    inicial = _leer_vti(tmp_path / "vtk" / "temperatura_0000.vti")
    assert np.all(np.isnan(inicial["temperatura"]))  # t = 0: aún no vertida, todo vacío
    assert not np.any(inicial["material"])
    colocado = _leer_vti(tmp_path / "vtk" / "temperatura_0001.vti")
    np.testing.assert_allclose(colocado['temperatura'][g.vertida_id == 1],20.)
    final = _leer_vti(tmp_path / "vtk" / "temperatura_0004.vti")
    assert np.all(final["material"][g.vertida_id == 1] == 1)


def test_caras_3d_de_un_cubo():
    from mcplan.visualizacion import _caras
    quads, celdas = _caras(np.ones((2, 2, 2), dtype=bool), np.zeros(3), np.ones(3))
    assert len(quads) == 24  # 6 caras × 4 voxeles
    assert quads.min() == 0.0 and quads.max() == 2.0


def test_advertencias_de_apoyo():
    ids = np.zeros((3, 3, 4), dtype=np.int16)
    ids[:, :, 1] = 1
    ids[:, :, 2] = 2
    dom = DominioVoxel(ids, np.zeros(ids.shape, dtype=bool), 0.1)

    def avisos(plan):
        return SimuladorEtapas(dom, plan, {"M1": Hormigon(HORMIGON)}, Ambiente(15.0, 10.0),
                               CondicionBase("adiabatico"), ParametrosTiempo(HORA)).advertencias_apoyo()

    assert avisos([PlanVertida(1, 0.0, 20.0, "M1"), PlanVertida(2, HORA, 20.0, "M1")]) == []
    assert "se vierte después" in avisos([PlanVertida(1, 2 * HORA, 20.0, "M1"), PlanVertida(2, HORA, 20.0, "M1")])[0]
    assert "oculta" in avisos([PlanVertida(1, 0.0, 20.0, "M1", visible=False), PlanVertida(2, HORA, 20.0, "M1")])[0]
    assert avisos([PlanVertida(1, 0.0, 20.0, "M1"), PlanVertida(2, HORA, 20.0, "M1", visible=False)]) == []


def test_ocultar_vertida_no_cambia_la_caja_y_no_la_activa():
    base = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    rapido = ["malla.paso_m=0.5", "malla.paso_z_m=0.275", "suelo.espesor_m=1.1", "simulacion.duracion_h=30"]
    r_todas = ejecutar_pipeline(leer_config(aplicar_sobrescrituras(base, rapido), base_rutas=CONFIG.parent))
    r_oculta = ejecutar_pipeline(leer_config(aplicar_sobrescrituras(base, rapido + ["vertidas.5.visible=false"]),
                                             base_rutas=CONFIG.parent))
    assert r_oculta.grilla.forma == r_todas.grilla.forma  # misma caja: corridas comparables
    assert all(math.isnan(x) for x in r_oculta.simulacion.T_max_vertida_C[5])
    assert r_oculta.area_exterior_m2["total"] != r_todas.area_exterior_m2["total"]
    assert abs(r_oculta.simulacion.balance["residuo_J"]) < 1e-10 * abs(r_oculta.simulacion.balance["E_final_J"])


def test_cli_comparar_e08(tmp_path):
    script = RAIZ / "scripts" / "comparar_e08.py"
    r = subprocess.run(
        [sys.executable, str(script), "--variante", "vertidas.defecto.T_colocacion_C=10",
         "--comun", "malla.paso_z_m=0.275", "--comun", "suelo.espesor_m=1.1", "--comun", "simulacion.duracion_h=12",
         "--salida", str(tmp_path / "c.png")],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert r.returncode == 0, r.stderr
    assert "Efecto: T_max -" in r.stdout and (tmp_path / "c.png").is_file()
