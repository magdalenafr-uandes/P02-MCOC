"""Verificación física y geométrica E07, con referencias independientes.

Los datos sintéticos de ajuste verifican el algoritmo; no calibran M1.
"""
from dataclasses import replace
from pathlib import Path
import json
import subprocess
import sys

import ifcopenshell
import ifcopenshell.api
import ifcopenshell.util.element
import ifcopenshell.util.placement
import numpy as np
import pytest

from mcplan.bim.foundation import construir_foundation, VERTIDAS_FOUNDATION, volumen_analitico
from mcplan.bim.ifc_io import productos_vertida
from mcplan.bim.voxel_ifc import SolidoIFC, contiene, extraer_solidos, voxelizar_ifc, caras_expuestas, interfaces
from mcplan.bim.voxelizacion import GrillaVertidas
from mcplan.thermal.boundaries import PropiedadesTermicas
from mcplan.thermal.hidratacion import HidratacionAdiabatica, ajustar_curva, ajustar_csv
from mcplan.thermal.material import cargar_hormigon
from mcplan.thermal.vertidas import SimuladorVertidas
from mcplan.thermal.voxel import MallaVoxel, SolverVoxel, adiabatico, robin

RAIZ = Path(__file__).resolve().parents[1]
PROPS = PropiedadesTermicas(2.22, 2400., 970.)


def caja(vid=1, inicio=0., T=18., origen=(0., 0., 0.)):
    vertices = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
                         [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]], float)+origen
    triangulos = np.array([[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7],
                           [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5],
                           [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]])
    return SolidoIFC(vid, str(vid), vertices, triangulos, inicio, T)


def simulador(ids, solidos=None, dx=1., incremento=0., h=0.):
    ids = np.asarray(ids, int)
    return SimuladorVertidas(GrillaVertidas(ids, (0., 0., 0.), dx), solidos or [caja()],
                            PROPS, HidratacionAdiabatica(incremento, 108000.), h=h)


@pytest.mark.parametrize('desplazamiento', [(0., 0., 0.), (350000., 6200000., 18.)])
@pytest.mark.parametrize('invertir', [False, True])
def test_caja_clasificacion_y_fronteras(desplazamiento, invertir):
    s = caja(origen=desplazamiento)
    if invertir:
        s = replace(s, triangulos=s.triangulos[:, ::-1])
    puntos = np.array([[.5, .5, .5], [1.01, .5, .5], [-.01, .5, .5],
                       [0, .5, .5], [0, 0, 0], [1, 1, .5]])+desplazamiento
    np.testing.assert_array_equal(contiene(s, puntos), [True, False, False, True, True, True])
    np.testing.assert_array_equal(contiene(s, puntos, False), [True, False, False, False, False, False])
    assert s.volumen == pytest.approx(1., abs=1e-10)


def test_caja_rotada_no_se_confunde_con_bounding_box():
    s = caja()
    angulo = np.pi/4
    R = np.array([[np.cos(angulo), -np.sin(angulo), 0], [np.sin(angulo), np.cos(angulo), 0], [0, 0, 1]])
    s = replace(s, vertices=s.vertices @ R.T)
    assert contiene(s, np.array([[0, .7, .5], [.6, .1, .5]])).tolist() == [True, False]


def test_voxelizar_conserva_unidad_volumen_y_origen():
    s = caja(origen=(10, 20, 30))
    g = voxelizar_ifc([s], .25)
    assert g.vertida_id.shape == (4, 4, 4)
    assert g.origen == (10, 20, 30)
    assert g.volumen(1) == 1.
    assert g.centros(2)[0] == 30.125


def test_frontera_compartida_determinista_y_solape_rechazado():
    a, b = caja(1), caja(2, origen=(1., 0., 0.))
    g = voxelizar_ifc([b, a], 2/3)
    # El centro x=1 está exactamente en la junta; prioridad al menor ID.
    assert np.all(g.vertida_id[1] == 1)
    with pytest.raises(ValueError, match='Solape'):
        voxelizar_ifc([a, caja(2, origen=(.5, 0., 0.))], .25)


def test_caras_expuestas_interfaces_y_sin_periodicidad():
    ids = np.array([1, 2]).reshape(2, 1, 1)
    antes = np.array([True, False]).reshape(ids.shape)
    assert sum(m.sum() for m in caras_expuestas(ids, antes).values()) == 6
    assert sum(m.sum() for m in interfaces(ids, antes).values()) == 0
    assert sum(m.sum() for m in caras_expuestas(ids).values()) == 10
    assert sum(m.sum() for m in interfaces(ids).values()) == 1
    assert interfaces(ids)['x+'][0, 0, 0]
    assert caras_expuestas(ids)['x-'][0, 0, 0]
    assert caras_expuestas(ids)['x+'][1, 0, 0]


def test_ifc_real_extrae_propiedades_y_volumen():
    solidos = extraer_solidos(RAIZ/'geometry/foundation.ifc')
    assert len(solidos) == 5
    modelo = ifcopenshell.open(str(RAIZ/'geometry/foundation.ifc'))
    for s, producto in zip(solidos, productos_vertida(modelo)):
        p = ifcopenshell.util.element.get_psets(producto)['UANDES_HormigonMasivo']
        assert s.guid == producto.GlobalId
        assert s.inicio_s == float(p['Inicio_h'])*3600
        assert s.temperatura_C == float(p['TemperaturaColocacion_C'])
        assert s.tipo_hormigon == p['TipoHormigon']
        assert s.volumen > 0


def test_ifc_transformaciones_y_unidades_mm_se_convierten_una_vez(tmp_path):
    modelo = construir_foundation()
    ruta = tmp_path/'metros.ifc'
    modelo.write(str(ruta))
    base = extraer_solidos(ruta)
    # convert_file_length_units cambia unidades y todas las coordenadas IFC.
    from ifcopenshell.util.unit import convert_file_length_units
    mm = convert_file_length_units(modelo, target_units='MILLIMETER')
    ruta_mm = tmp_path/'milimetros.ifc'
    mm.write(str(ruta_mm))
    for a, b in zip(base, extraer_solidos(ruta_mm)):
        np.testing.assert_allclose(a.vertices, b.vertices, atol=1e-8)
        assert a.volumen == pytest.approx(b.volumen, rel=1e-10)
    producto = productos_vertida(modelo)[0]
    matriz = ifcopenshell.util.placement.get_local_placement(producto.ObjectPlacement)
    matriz[:3, 3] += [11, 22, 33]
    ifcopenshell.api.run('geometry.edit_object_placement', modelo, product=producto, matrix=matriz, is_si=True)
    modelo.write(str(ruta))
    trasladado = extraer_solidos(ruta)[0]
    np.testing.assert_allclose(trasladado.vertices, base[0].vertices+[11, 22, 33], atol=1e-9)


def test_ifc_generado_contra_volumen_analitico_independiente(tmp_path):
    ruta = tmp_path/'foundation.ifc'
    construir_foundation().write(str(ruta))
    solidos = extraer_solidos(ruta)
    for s, v in zip(solidos, VERTIDAS_FOUNDATION):
        assert s.volumen == pytest.approx(volumen_analitico(v), rel=1e-8)


def test_curva_adiabatica_y_calor_integrado():
    h = HidratacionAdiabatica(45, 108000)
    assert h.incremento(0) == 0
    assert h.incremento(108000) == pytest.approx(45*(1-1/np.e))
    assert h.qdot(0, PROPS.rho, PROPS.cp) == pytest.approx(970.)
    t = np.linspace(0, 20*h.escala_s, 100001)
    q = h.qdot(t, PROPS.rho, PROPS.cp)
    energia = np.trapezoid(q, t) if hasattr(np, 'trapezoid') else np.trapz(q, t)
    assert energia == pytest.approx(PROPS.rho*PROPS.cp*45, rel=1e-7)


def test_ajuste_recupera_parametros_y_datos_con_ruido():
    t = np.array([0, 6, 12, 24, 48, 72, 120, 168])*3600.
    y = 42*(1-np.exp(-t/(28*3600)))
    ajuste = ajustar_curva(t, y)
    assert ajuste.modelo.incremento_K == pytest.approx(42., rel=1e-7)
    assert ajuste.modelo.escala_s == pytest.approx(28*3600., rel=1e-7)
    assert ajuste.rmse_K < 1e-7
    ruido = np.array([0, .08, -.12, .15, -.10, .12, -.07, .05])
    ajuste = ajustar_curva(t[::-1], (y+ruido)[::-1])
    assert ajuste.modelo.incremento_K == pytest.approx(42., rel=.01)
    assert ajuste.modelo.escala_s == pytest.approx(28*3600., rel=.02)
    assert ajuste.rmse_K < .15


def test_ajuste_csv_trazable(tmp_path):
    archivo = tmp_path/'ensayo_sintetico.csv'
    archivo.write_text('edad_h,incremento_K\n0,0\n12,14.8355979284\n24,24.7801965707\n48,35.9146566902\n96,43.1657008209\n', encoding='utf-8')
    resultado, meta = ajustar_csv(archivo)
    assert resultado.modelo.incremento_K == pytest.approx(45., rel=.001)
    assert len(meta['sha256']) == 64
    assert meta['muestras'] == 5
    archivo.write_text('edad_h,temperatura_C\n0,20\n', encoding='utf-8')
    with pytest.raises(ValueError, match='Cabecera'):
        ajustar_csv(archivo)


@pytest.mark.parametrize('t,y', [([0, 1, 1, 3], [0, 1, 2, 3]), ([0, 1, 2, 3], [20, 21, 22, 23]),
                               ([0, 1, 2, 3], [0, 0, 0, 0]), ([0, 1, 2, np.nan], [0, 1, 2, 3]),
                               ([0, 1, 2], [0, 1, 2]), ([0, 1, 2, 3], [0, 1, -2, 3])])
def test_ajuste_rechaza_curvas_invalidas(t, y):
    with pytest.raises(ValueError):
        ajustar_curva(t, y)


def test_referencia_docente_no_se_presenta_como_calibracion():
    p, h, meta = cargar_hormigon(RAIZ/'configs/hormigon_M1.json')
    assert p == PROPS
    assert h.escala_s == 30*3600
    assert 'no_calibrada' in meta['estado']


def test_activacion_corta_eventos_sin_envejecer_material_no_colocado():
    sim = simulador(np.array([1, 2]).reshape(2, 1, 1), [caja(T=20), caja(2, inicio=73, T=15)], incremento=45)
    antes = sim.avanzar(72., 1000.)
    assert np.isnan(antes.T[1, 0, 0])
    evento = sim.avanzar(73., 1000.)
    assert evento.T[1, 0, 0] == 15
    assert evento.edad_s[1, 0, 0] == 0
    assert evento.edad_s[0, 0, 0] == 73
    assert abs(evento.residuo_energia_J) < 1e-7
    fin = sim.avanzar(500., 1000.)
    assert fin.edad_s[1, 0, 0] == 427
    assert abs(fin.residuo_energia_J) < 1e-7


def test_espera_hasta_primera_vertida_y_estado_independiente():
    sim = simulador(np.ones((1, 1, 1)), [caja(inicio=12)])
    e = sim.avanzar(11, 100)
    assert not e.activos.any()
    assert np.isnan(e.T).all()
    e = sim.avanzar(12, 100)
    assert e.T.item() == 18
    e.T[:] = 99
    assert sim.estado().T.item() == 18


def test_adiabatico_aislado_reproduce_curva_exacta_para_cualquier_paso():
    sim = simulador(np.ones((1, 1, 1)), incremento=45)
    e = sim.avanzar(7*86400, 12345)
    esperado = 18+45*(1-np.exp(-7*86400/108000))
    assert e.T.item() == pytest.approx(esperado, abs=1e-12)
    assert abs(e.residuo_energia_J) < 1e-6


def test_interfaz_conserva_energia_y_no_cruza_vacios():
    ids = np.array([1, 2, 0, 3]).reshape(4, 1, 1)
    sim = simulador(ids, [caja(T=60), caja(2, T=20), caja(3, T=5)])
    inicial = sim.estado().energia_J
    e = sim.avanzar(86400, 1000)
    assert e.T[0, 0, 0] < 60
    assert e.T[1, 0, 0] > 20
    assert e.T[3, 0, 0] == 5
    assert np.isnan(e.T[2, 0, 0])
    assert e.energia_J == pytest.approx(inicial, rel=1e-14)


def test_dominio_rectangular_coincide_con_solver_verificado():
    forma = (3, 2, 4)
    sim = simulador(np.ones(forma), dx=.2, h=8)
    T0 = np.random.default_rng(15).uniform(15, 40, forma)
    sim.T[:] = T0
    m = MallaVoxel.uniforme(forma, (.2, .2, .2), PROPS)
    solver = SolverVoxel(m, {c: robin(20., 8.) for c in m.caras})
    e = sim.avanzar(100, 10)
    referencia = solver.resolver(T0, dt=10., n_pasos=10)
    np.testing.assert_allclose(e.T, referencia.T, atol=1e-12)


def test_paso_grande_se_subdivide_y_respeta_principio_del_maximo():
    sim = simulador(np.ones((3, 3, 3)), dx=.1, h=10)
    sim.T[:] = 20
    sim.T[1, 1, 1] = 60
    e = sim.avanzar(10000, 10000)
    assert np.isfinite(e.T).all()
    assert e.T.min() >= 20-1e-12
    assert e.T.max() <= 60


def test_convergencia_temporal_con_fuente_y_robin_analitico():
    tfin, dx, h = 3600., .2, 8.
    tasa = 6/(dx/(2*PROPS.k)+1/h)/(PROPS.rho*PROPS.cp*dx)
    tau, amplitud = 108000., 45.
    exacta = 20+(18-20)*np.exp(-tasa*tfin) + amplitud/tau*(np.exp(-tfin/tau)-np.exp(-tasa*tfin))/(tasa-1/tau)
    errores = []
    for dt in (100., 50., 25.):
        sim = simulador(np.ones((1, 1, 1)), dx=dx, h=h, incremento=amplitud)
        e = sim.avanzar(tfin, dt)
        errores.append(abs(e.T.item()-exacta))
        assert abs(e.residuo_energia_J) < 1e-8
    assert 1.9 < errores[0]/errores[1] < 2.1
    assert 1.9 < errores[1]/errores[2] < 2.1


def test_convergencia_espacial_neumann_coseno():
    errores = []
    for n in (8, 16, 32):
        dx = 1/n
        sim = simulador(np.ones((n, 1, 1)), dx=dx)
        x = (np.arange(n)+.5)*dx
        sim.T[:, 0, 0] = 20+5*np.cos(np.pi*x)
        tfin = 10000.
        e = sim.avanzar(tfin, 1.)
        exacta = 20+5*np.cos(np.pi*x)*np.exp(-PROPS.alpha*np.pi**2*tfin)
        errores.append(float(abs(e.T[:, 0, 0]-exacta).max()))
    orden = np.log2(np.array(errores[:-1])/errores[1:])
    assert np.all((orden > 1.8) & (orden < 2.2)), (errores, orden)


def test_flujo_completo_cli_y_archivos_resultado(tmp_path):
    salida = tmp_path/'demo'
    ejecucion = subprocess.run([sys.executable, str(RAIZ/'scripts/demo_e07.py'), '--pasos', '.4', '--horas', '.1', '--salida', str(salida)],
                              capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
    assert ejecucion.returncode == 0, ejecucion.stdout+ejecucion.stderr
    meta = json.loads((salida/'parametros.json').read_text(encoding='utf-8'))
    assert meta['escala_s'] == 108000
    assert meta['ajuste'] is None
    assert all((salida/n).stat().st_size > 0 for n in ['volumenes.csv', 'activacion.csv', 'voxelizacion.png', 'activacion.png', 'hidratacion.png', 'estado_final.npz'])
    resumen = json.loads((salida/'resumen.json').read_text(encoding='utf-8'))
    assert resumen['residuo_final_relativo'] < 1e-12
    curva = tmp_path/'curva.csv'
    curva.write_text('edad_h,incremento_K\n0,0\n12,14.8355979284\n24,24.7801965707\n48,35.9146566902\n96,43.1657008209\n', encoding='utf-8')
    ejecucion = subprocess.run([sys.executable, str(RAIZ/'scripts/demo_e07.py'), '--pasos', '.4', '--horas', '.1', '--salida', str(salida), '--curva-adiabatica', str(curva)],
                              capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
    assert ejecucion.returncode == 0, ejecucion.stdout+ejecucion.stderr
    meta = json.loads((salida/'parametros.json').read_text(encoding='utf-8'))
    assert meta['ajuste']['rmse_K'] < .01
    assert meta['material']['hidratacion']['escala_s'] == meta['escala_s']


@pytest.mark.parametrize('dx', [0., -1., np.nan, np.inf])
def test_rechaza_pasos_geometricos_invalidos(dx):
    with pytest.raises(ValueError):
        voxelizar_ifc([caja()], dx)


@pytest.mark.parametrize('final,dt', [(-1, 1), (1, 0), (np.nan, 1), (1, np.inf)])
def test_rechaza_avance_temporal_invalido(final, dt):
    sim = simulador(np.ones((1, 1, 1)))
    with pytest.raises(ValueError):
        sim.avanzar(final, dt)


def test_no_simula_materiales_diferentes_como_si_fueran_iguales():
    with pytest.raises(ValueError, match='TipoHormigon'):
        simulador(np.array([1, 2]).reshape(2, 1, 1), [caja(), replace(caja(2), tipo_hormigon='M2')])


def test_rechaza_ids_y_mascaras_invalidos():
    with pytest.raises(ValueError):
        caras_expuestas(np.ones((1, 1)))
    with pytest.raises(ValueError):
        caras_expuestas(np.ones((2, 1, 1), int), np.ones((1, 1, 1), bool))
    with pytest.raises(ValueError):
        SimuladorVertidas(GrillaVertidas(np.full((1, 1, 1), 1.5), (0, 0, 0), 1), [caja()], PROPS, HidratacionAdiabatica(45, 108000))
    with pytest.raises(ValueError):
        simulador(np.ones((1, 1, 1)), [caja(), caja(2)])
