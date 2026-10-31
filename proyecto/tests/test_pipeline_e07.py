"""Pipeline E07/E08: extracción IFC, voxelización, hidratación, etapas y config."""

import ast
import inspect
import math
import subprocess
import sys
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
from mcplan.thermal import etapas as modulo_etapas
from mcplan.thermal.etapas import (
    Ambiente,
    CondicionBase,
    DominioVoxel,
    Hormigon,
    Material,
    ParametrosTiempo,
    PlanVertida,
    SimuladorEtapas,
)
from mcplan.thermal.hidratacion import HORA, ModeloHidratacion

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
    def f(te):
        return modelo.factor_arrhenius(T0 + modelo.elevacion(te))

    te, h = 0.0, 30.0
    for _ in range(int(72 * HORA / h)):
        k1 = f(te); k2 = f(te + h * k1 / 2); k3 = f(te + h * k2 / 2); k4 = f(te + h * k3)
        te += h * (k1 + 2 * k2 + 2 * k3 + k4) / 6
    T_ref = T0 + modelo.elevacion(te)

    errores = []
    for dt in (120.0, 60.0):
        sim = SimuladorEtapas(
            dominio_caja(), [PlanVertida(1, 0.0, T0, "M1")], {"M1": Hormigon(HORMIGON, modelo)},
            Ambiente(10.0, 0.0), CondicionBase("adiabatico"),
            ParametrosTiempo(72 * HORA, dt_max_s=dt, guardar_cada_s=6 * HORA),
        )
        r = sim.ejecutar()
        T = r.T_final[r.activo_final]
        np.testing.assert_allclose(T, T.mean(), atol=1e-9)  # sin pérdidas: campo uniforme
        assert abs(r.balance["residuo_J"]) < 1e-9 * abs(r.balance["E_final_J"])
        errores.append(abs(T.mean() - T_ref))
    assert errores[1] < 0.05
    assert errores[1] / errores[0] == pytest.approx(0.5, abs=0.05)  # Euler explícito: orden 1 en dt
    assert T_ref - T0 > 0.9 * modelo.elevacion(72 * HORA)  # Arrhenius acelera (T > T_ref)


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

    # La cara superior de la vertida 1 deja de estar expuesta al cubrirla la 2.
    tapa = (slice(1, 4), slice(1, 4), 2)
    for activas, expuesta in (({1}, True), ({1, 2}, False)):
        activo = np.isin(ids, list(activas))
        k = np.where(activo, HORMIGON.k, 1e-9)
        G_amb, _ = sim._conductancias_externas(0.0, activo, activo, k)
        assert np.all(G_amb[tapa] > 0) == expuesta
    assert abs(r.balance["residuo_J"]) < 1e-9 * abs(r.balance["E_final_J"])


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
        datos = aplicar_sobrescrituras(base, ["malla.paso_m=0.5", "simulacion.duracion_h=30",
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
