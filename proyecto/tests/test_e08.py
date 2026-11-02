"""Pipeline real, overrides de inputs, VTK y API local E08."""
import base64
import copy
import importlib.util
import json
from pathlib import Path
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from mcplan.bim.voxel_ifc import extraer_solidos
from mcplan.pipeline import Pipeline, cargar_plan, validar_plan

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def solidos():
    return extraer_solidos(RAIZ/'geometry/foundation.ifc')


@pytest.fixture
def plan():
    p = cargar_plan(RAIZ/'configs/e08.json')
    p['final_h'] = .02
    p['guardar_cada_h'] = .01
    p['vertidas'][1]['inicio_h'] = .005
    return p


def temperaturas(resultado, indice=-1):
    return np.frombuffer(base64.b64decode(resultado['fotogramas'][indice]['T_f32']), dtype='<f4')


def test_rutas_relativas_al_archivo_y_secuencia_en_inputs(plan, solidos):
    assert Path(plan['ifc']).is_absolute()
    assert Path(plan['material']).is_file()
    validar_plan(plan, solidos)
    assert len({v['inicio_h'] for v in plan['vertidas']}) >= 2


@pytest.mark.parametrize('campo,valor', [('paso_m', 0), ('paso_m', True), ('final_h', -1), ('dt_s', 0),
                                      ('guardar_cada_h', 1e-9), ('h_W_m2_K', -1), ('ambiente_C', -300),
                                      ('pasos_convergencia_m', [.4, .4, .1]), ('pasos_convergencia_m', [.4, .2])])
def test_inputs_invalidos_rechazados(plan, solidos, campo, valor):
    plan[campo] = valor
    with pytest.raises(ValueError):
        validar_plan(plan, solidos)


def test_ids_duplicados_desconocidos_o_omitidos(plan, solidos):
    for cambio in ('duplicado', 'desconocido', 'omitido'):
        p = copy.deepcopy(plan)
        if cambio == 'omitido':
            p['vertidas'].pop()
        else:
            p['vertidas'][1]['id'] = 1 if cambio == 'duplicado' else 99
        with pytest.raises(ValueError):
            validar_plan(p, solidos)


def test_override_horario_y_temperatura_llegan_al_solver_sin_modificar_ifc(plan, tmp_path):
    pipeline = Pipeline()
    original = Path(plan['ifc']).read_bytes()
    r0 = pipeline.ejecutar(plan, tmp_path/'base', convergencia=False)
    assert all(v['paso_m'] == plan['paso_m'] for v in r0['volumenes'])
    assert any(f['tiempo_h'] == .005 for f in r0['fotogramas'])
    vids = np.array(r0['vertida_id'])
    assert np.isnan(temperaturas(r0, 0)[vids == 2]).all()
    assert np.isfinite(temperaturas(r0)[vids == 2]).all()
    variante = copy.deepcopy(plan)
    variante['vertidas'][1]['inicio_h'] = .03
    r1 = pipeline.ejecutar(variante, tmp_path/'retraso', convergencia=False)
    assert np.isnan(temperaturas(r1)[vids == 2]).all()
    assert r1['fotogramas'][-1]['volumen_activo_m3'] < r0['fotogramas'][-1]['volumen_activo_m3']
    variante['vertidas'][1].update(inicio_h=.005, temperatura_C=35)
    r2 = pipeline.ejecutar(variante, tmp_path/'caliente', convergencia=False)
    assert r2['fotogramas'][-1]['Tmax_C'] > r0['fotogramas'][-1]['Tmax_C']+10
    assert Path(plan['ifc']).read_bytes() == original
    assert len(pipeline._grillas) == 1  # solo cambió la programación, no la geometría
    for r in (r0, r1, r2):
        b = r['balances'][-1]
        escala = max(abs(b['energia_J']), abs(b['colocacion_J'])+abs(b['hidratacion_J'])+abs(b['borde_J']), 1)
        assert abs(b['residuo_J'])/escala < 1e-12


def test_cambiar_dx_y_convergencia_reporta_cada_vertida(plan, tmp_path):
    plan['pasos_convergencia_m'] = [.8, .4, .2]
    pipeline = Pipeline()
    resultado = pipeline.ejecutar(plan, tmp_path/'convergencia')
    filas = resultado['volumenes']
    assert len(filas) == 18  # cinco vertidas + total por cada resolución
    totales = [v for v in filas if v['vertida_id'] == 'total']
    assert totales[-1]['error_relativo'] < totales[0]['error_relativo']
    plan['paso_m'] = .2
    fino = pipeline.ejecutar(plan, tmp_path/'fino', convergencia=False)
    assert fino['paso_m'] == .2
    assert len(fino['indices']) > len(resultado['indices'])
    assert fino['mallas'] == resultado['mallas']


def test_vti_celdas_orden_fortran_y_tiempos_pvd(plan, tmp_path):
    r = Pipeline().ejecutar(plan, tmp_path, convergencia=False)
    pvd = ET.parse(tmp_path/'temperaturas.pvd')
    archivos = pvd.findall('./Collection/DataSet')
    assert [float(a.attrib['timestep']) for a in archivos] == [f['tiempo_h']*3600 for f in r['fotogramas']]
    vti = ET.parse(tmp_path/archivos[-1].attrib['file'])
    imagen = vti.find('./ImageData')
    assert list(map(float, imagen.attrib['Origin'].split())) == r['origen_m']
    assert list(map(float, imagen.attrib['Spacing'].split())) == [plan['paso_m']]*3
    nx, ny, nz = r['forma']
    assert imagen.attrib['WholeExtent'] == f'0 {nx} 0 {ny} 0 {nz}'
    arreglos = {}
    for elemento in vti.findall('./ImageData/Piece/CellData/DataArray'):
        raw = base64.b64decode(elemento.text)
        assert int(np.frombuffer(raw[:4], dtype='<u4')[0]) == len(raw)-4
        dtype = {'Float64': '<f8', 'Int32': '<i4', 'UInt8': 'u1'}[elemento.attrib['type']]
        arreglos[elemento.attrib['Name']] = np.frombuffer(raw[4:], dtype=dtype).reshape(r['forma'], order='F')
    indices = np.asarray(r['indices'])
    indices_tuple = tuple(indices.T)
    np.testing.assert_array_equal(arreglos['vertida_id'][indices_tuple], r['vertida_id'])
    np.testing.assert_allclose(arreglos['temperatura_C'][indices_tuple], temperaturas(r), rtol=1e-6, equal_nan=True)
    assert np.isnan(arreglos['temperatura_C'][arreglos['activo'] == 0]).all()
    ejecutado = json.loads((tmp_path/'plan_ejecutado.json').read_text(encoding='utf-8'))
    assert ejecutado == plan
    assert len(r['ifc_sha256']) == 64


def test_limite_memoria_y_material_incompatible(plan, tmp_path):
    plan['paso_m'] = .0001
    with pytest.raises(ValueError, match='Grilla demasiado grande'):
        Pipeline().ejecutar(plan, tmp_path/'grande', convergencia=False)
    p = json.loads((RAIZ/'configs/hormigon_M1.json').read_text(encoding='utf-8'))
    p['material'] = 'otro'
    ruta = tmp_path/'material.json'
    ruta.write_text(json.dumps(p), encoding='utf-8')
    plan['material'] = str(ruta)
    with pytest.raises(ValueError, match='TipoHormigon'):
        Pipeline().ejecutar(plan, tmp_path/'material', convergencia=False)


def test_api_servidor_ejecuta_pipeline_real_y_rechaza_origen_ajeno(plan, tmp_path):
    spec = importlib.util.spec_from_file_location('demo_e08', RAIZ/'scripts/demo_e08.py')
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    servidor, executor = modulo.crear_servidor(plan, 0, tmp_path)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    url = f'http://127.0.0.1:{servidor.server_port}'

    def obtener(ruta):
        with urlopen(url+ruta, timeout=10) as respuesta:
            return json.load(respuesta)

    body = json.dumps(dict(plan=plan, convergencia=False)).encode()
    try:
        assert obtener('/api/plan') == plan
        with urlopen(url, timeout=10) as respuesta:
            html = respuesta.read().decode()
        assert 'Ejecutar simulación' in html
        request = Request(url+'/api/ejecutar', data=body, headers={'Content-Type': 'application/json', 'Origin': 'https://externo.invalid'})
        with pytest.raises(HTTPError) as error:
            urlopen(request, timeout=10)
        assert error.value.code == 403
        request = Request(url+'/api/ejecutar', data=body, headers={'Content-Type': 'application/json', 'Origin': url})
        with urlopen(request, timeout=10) as respuesta:
            assert respuesta.status == 202
        limite = time.monotonic()+60
        while time.monotonic() < limite:
            estado = obtener('/api/estado')
            if estado['estado'] != 'running':
                break
            time.sleep(.05)
        assert estado['estado'] == 'done', estado
        assert len(obtener('/api/resultado')['fotogramas']) >= 3
        assert Path(estado['carpeta']).is_relative_to(tmp_path.resolve())
    finally:
        servidor.shutdown()
        servidor.server_close()
        executor.shutdown(wait=True)
        hilo.join(timeout=5)
