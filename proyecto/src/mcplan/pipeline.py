"""Pipeline E08 reproducible: entradas -> IFC -> grilla -> solver -> resultados.

Las propiedades de colocación del plan prevalecen sobre el IFC; los GUID y
la geometría siempre proceden del IFC. No hay secuencias en el solver.
"""
import base64
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

import numpy as np

from .bim.voxel_ifc import extraer_solidos, voxelizar_ifc
from .thermal.material import cargar_hormigon
from .thermal.vertidas import SimuladorVertidas

MAX_CELDAS = 2_000_000
MAX_FOTOGRAMAS = 250


def cargar_plan(ruta):
    ruta = Path(ruta).resolve()
    plan = json.loads(ruta.read_text(encoding='utf-8-sig'))
    for campo in ('ifc', 'material'):
        plan[campo] = str((ruta.parent/plan[campo]).resolve())
    return plan


def _numero(valor, nombre, minimo=None, positivo=False):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not np.isfinite(valor):
        raise ValueError(f'{nombre}: se requiere un número finito.')
    if (positivo and valor <= 0) or (minimo is not None and valor < minimo):
        raise ValueError(f'{nombre}: valor fuera de rango.')
    return float(valor)


def validar_plan(plan, solidos):
    esperados = {'ifc', 'material', 'paso_m', 'pasos_convergencia_m', 'final_h', 'dt_s',
                 'guardar_cada_h', 'ambiente_C', 'h_W_m2_K', 'vertidas'}
    if set(plan) != esperados:
        raise ValueError(f'Campos del plan incorrectos: faltan {esperados-set(plan)}, sobran {set(plan)-esperados}.')
    for campo in ('paso_m', 'final_h', 'dt_s', 'guardar_cada_h'):
        _numero(plan[campo], campo, positivo=True)
    _numero(plan['ambiente_C'], 'ambiente_C')
    _numero(plan['h_W_m2_K'], 'h_W_m2_K', minimo=0)
    if not isinstance(plan['pasos_convergencia_m'], list) or not 3 <= len(plan['pasos_convergencia_m']) <= 6:
        raise ValueError('Se requieren entre tres y seis pasos de convergencia.')
    for dx in plan['pasos_convergencia_m']:
        _numero(dx, 'pasos_convergencia_m', positivo=True)
    if len(set(plan['pasos_convergencia_m'])) != len(plan['pasos_convergencia_m']):
        raise ValueError('Los pasos de convergencia deben ser distintos.')
    if not isinstance(plan['vertidas'], list) or len(plan['vertidas']) != len(solidos):
        raise ValueError('El plan debe definir cada vertida del IFC exactamente una vez.')
    ids = []
    for v in plan['vertidas']:
        if set(v) != {'id', 'inicio_h', 'temperatura_C'} or type(v['id']) is not int:
            raise ValueError('Cada vertida requiere id entero, inicio_h y temperatura_C.')
        ids.append(v['id'])
        _numero(v['inicio_h'], 'inicio_h', minimo=0)
        _numero(v['temperatura_C'], 'temperatura_C')
        if v['temperatura_C'] <= -273.15:
            raise ValueError('Temperatura de colocación fuera del rango físico.')
    if len(set(ids)) != len(ids) or set(ids) != {s.vertida_id for s in solidos}:
        raise ValueError('IDs del plan duplicados o diferentes de los del IFC.')
    if plan['ambiente_C'] <= -273.15:
        raise ValueError('Temperatura ambiente fuera del rango físico.')
    if plan['final_h']/plan['guardar_cada_h'] + len(solidos) + 2 > MAX_FOTOGRAMAS:
        raise ValueError(f'Demasiados fotogramas; aumentar guardar_cada_h (máximo {MAX_FOTOGRAMAS}).')
    if plan['final_h']*3600/plan['dt_s'] > 1_000_000:
        raise ValueError('Demasiados pasos temporales solicitados.')
    return plan


def codificar_f32(datos):
    return base64.b64encode(np.asarray(datos, dtype='<f4').tobytes()).decode('ascii')


def exportar_vti(ruta, grilla, estado):
    """VTK ImageData: valores de celda, x rápido (orden Fortran), SI."""
    forma = grilla.vertida_id.shape
    extent = f'0 {forma[0]} 0 {forma[1]} 0 {forma[2]}'
    raiz = ET.Element('VTKFile', type='ImageData', version='0.1', byte_order='LittleEndian', header_type='UInt32')
    imagen = ET.SubElement(raiz, 'ImageData', WholeExtent=extent, Origin=' '.join(map(str, grilla.origen)), Spacing=' '.join([str(grilla.paso)]*3))
    pieza = ET.SubElement(imagen, 'Piece', Extent=extent)
    celdas = ET.SubElement(pieza, 'CellData', Scalars='temperatura_C')
    for nombre, arr, dtype, vtk in (
        ('temperatura_C', estado.T, '<f8', 'Float64'), ('edad_s', estado.edad_s, '<f8', 'Float64'),
        ('vertida_id', grilla.vertida_id, '<i4', 'Int32'), ('activo', estado.activos, 'u1', 'UInt8')):
        raw = np.asarray(arr, dtype=dtype).ravel(order='F').tobytes()
        encabezado = np.asarray([len(raw)], dtype='<u4').tobytes()
        elemento = ET.SubElement(celdas, 'DataArray', type=vtk, Name=nombre, format='binary')
        elemento.text = base64.b64encode(encabezado+raw).decode('ascii')
    ET.ElementTree(raiz).write(ruta, encoding='utf-8', xml_declaration=True)


class Pipeline:
    def __init__(self):
        self._grillas = {}

    def ejecutar(self, plan, salida, progreso=lambda mensaje: None, convergencia=True):
        plan = json.loads(json.dumps(plan, allow_nan=False))
        salida = Path(salida)
        ruta_ifc = Path(plan['ifc'])
        sha_ifc = hashlib.sha256(ruta_ifc.read_bytes()).hexdigest()
        progreso('Extrayendo geometría IFC')
        solidos_ifc = extraer_solidos(ruta_ifc)
        validar_plan(plan, solidos_ifc)
        propiedades, hidratacion, material = cargar_hormigon(plan['material'])
        if {s.tipo_hormigon for s in solidos_ifc} != {material['material']}:
            raise ValueError('TipoHormigon del IFC incompatible con el material seleccionado.')
        entradas = {v['id']: v for v in plan['vertidas']}
        solidos = [replace(s, inicio_s=entradas[s.vertida_id]['inicio_h']*3600,
                           temperatura_C=entradas[s.vertida_id]['temperatura_C']) for s in solidos_ifc]
        minimo = np.min([s.vertices.min(axis=0) for s in solidos], axis=0)
        maximo = np.max([s.vertices.max(axis=0) for s in solidos], axis=0)

        def grilla(dx):
            forma = np.ceil((maximo-minimo)/dx)
            if not np.isfinite(forma).all() or np.prod(forma) > MAX_CELDAS:
                raise ValueError(f'Grilla demasiado grande; aumentar Δx (máximo {MAX_CELDAS:,} celdas).')
            clave = (sha_ifc, float(dx))
            if clave not in self._grillas:
                progreso(f'Voxelizando Δx={dx:g} m')
                nueva = voxelizar_ifc(solidos_ifc, dx)
                if len(self._grillas) >= 6:
                    self._grillas.pop(next(iter(self._grillas)))
                self._grillas[clave] = nueva
            return self._grillas[clave]

        pasos = sorted(set([plan['paso_m']] + (plan['pasos_convergencia_m'] if convergencia else [])), reverse=True)
        volumenes = []
        for dx in pasos:
            g = grilla(dx)
            refs = [(s.vertida_id, s.volumen, g.volumen(s.vertida_id)) for s in solidos]
            refs.append(('total', sum(s.volumen for s in solidos), float(np.count_nonzero(g.vertida_id))*dx**3))
            for vid, ref, vh in refs:
                volumenes.append(dict(paso_m=dx, vertida_id=vid, ifc_m3=ref, voxel_m3=vh, error_relativo=abs(vh-ref)/ref))
        g = grilla(plan['paso_m'])
        sim = SimuladorVertidas(g, solidos, propiedades, hidratacion, plan['ambiente_C'], plan['h_W_m2_K'])
        fin = plan['final_h']*3600
        tiempos = sorted(set([0., fin] + list(np.arange(0., fin, plan['guardar_cada_h']*3600)) +
                             [s.inicio_s for s in solidos if s.inicio_s <= fin]))
        mascara = g.vertida_id > 0
        indices = np.argwhere(mascara)
        fotogramas = []
        balances = []
        salida.mkdir(parents=True, exist_ok=True)
        coleccion = ET.Element('VTKFile', type='Collection', version='0.1', byte_order='LittleEndian')
        datasets = ET.SubElement(coleccion, 'Collection')
        for numero, t in enumerate(tiempos):
            progreso(f'Simulando {t/3600:g} / {plan["final_h"]:g} h')
            estado = sim.avanzar(t, plan['dt_s'])
            temperaturas = estado.T[mascara]
            activos = temperaturas[np.isfinite(temperaturas)]
            fotogramas.append(dict(tiempo_h=t/3600, T_f32=codificar_f32(temperaturas),
                                   Tmax_C=float(activos.max()) if len(activos) else None,
                                   Tmin_C=float(activos.min()) if len(activos) else None,
                                   volumen_activo_m3=int(estado.activos.sum())*g.paso**3))
            balances.append(dict(tiempo_h=t/3600, energia_J=estado.energia_J, hidratacion_J=estado.hidratacion_J,
                                 borde_J=estado.borde_J, colocacion_J=estado.colocacion_J, residuo_J=estado.residuo_energia_J))
            archivo = f'temperatura_{numero:04d}.vti'
            exportar_vti(salida/archivo, g, estado)
            ET.SubElement(datasets, 'DataSet', timestep=str(t), group='', part='0', file=archivo)
        ET.ElementTree(coleccion).write(salida/'temperaturas.pvd', encoding='utf-8', xml_declaration=True)
        try:
            commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=Path(__file__).resolve().parents[3], capture_output=True, text=True, timeout=5).stdout.strip() or None
            cambios = subprocess.run(['git', 'status', '--porcelain'], cwd=Path(__file__).resolve().parents[3], capture_output=True, text=True, timeout=5)
            codigo_modificado = bool(cambios.stdout.strip()) if cambios.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            commit = None
            codigo_modificado = None
        resultado = dict(plan=plan, ifc_sha256=sha_ifc, commit=commit, codigo_modificado=codigo_modificado, material=material,
                         material_sha256=hashlib.sha256(Path(plan['material']).read_bytes()).hexdigest(),
                         origen_m=list(g.origen), forma=list(g.vertida_id.shape), paso_m=g.paso,
                         indices=indices.tolist(), vertida_id=g.vertida_id[mascara].tolist(),
                         volumenes=volumenes, balances=balances, fotogramas=fotogramas,
                         mallas=[dict(id=s.vertida_id, guid=s.guid, vertices=s.vertices.tolist(), triangulos=s.triangulos.tolist()) for s in solidos])
        (salida/'plan_ejecutado.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        (salida/'resultado.json').write_text(json.dumps(resultado, ensure_ascii=False, allow_nan=False), encoding='utf-8')
        progreso('Completado')
        return resultado
