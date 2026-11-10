"""Pipeline E08 reproducible: entradas -> IFC -> grilla -> solver -> resultados.

Las propiedades de colocación del plan prevalecen sobre el IFC; los GUID y
la geometría siempre proceden del IFC. No hay secuencias en el solver.
"""
import base64
from dataclasses import replace
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

import numpy as np
import copy
import math
from types import SimpleNamespace
import yaml

from .bim.voxel_ifc import extraer_solidos, voxelizar_ifc
from .thermal.material import cargar_hormigon
from .thermal.vertidas import SimuladorVertidas

MAX_CELDAS = 2_000_000
MAX_FOTOGRAMAS = 512


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
    imagen = ET.SubElement(raiz, 'ImageData', WholeExtent=extent, Origin=' '.join(map(str, grilla.origen)), Spacing=' '.join(map(str, (grilla.paso,)*3 if np.isscalar(grilla.paso) else grilla.paso)))
    pieza = ET.SubElement(imagen, 'Piece', Extent=extent)
    celdas = ET.SubElement(pieza, 'CellData', Scalars='temperatura_C')
    for nombre, arr, dtype, vtk in (
        ('temperatura_C', estado.T, '<f8', 'Float64'), ('edad_s', estado.edad_s, '<f8', 'Float64'),
        ('vertida_id', grilla.vertida_id, '<i4', 'Int32'), ('activo', estado.activos, 'u1', 'UInt8')):
        raw = np.asarray(arr, dtype=dtype).ravel(order='F').tobytes()
        encabezado = np.asarray([len(raw)], dtype='<u4').tobytes()
        elemento = ET.SubElement(celdas, 'DataArray', type=vtk, Name=nombre, format='binary')
        elemento.text = base64.b64encode(encabezado+raw).decode('ascii')
    if hasattr(grilla,'es_suelo'):
        material = estado.activos.astype(np.uint8)+2*grilla.es_suelo.astype(np.uint8)
        raw=material.ravel(order='F').tobytes()
        elemento=ET.SubElement(celdas,'DataArray',type='UInt8',Name='material',format='binary')
        elemento.text=base64.b64encode(np.asarray([len(raw)],dtype='<u4').tobytes()+raw).decode('ascii')
    ET.ElementTree(raiz).write(ruta, encoding='utf-8', xml_declaration=True)


# Compatibilidad con planes JSON E08 anteriores. La ejecución usa siempre
# SimuladorEtapas; el modelo simple queda solo en las demos/verificaciones E07.
_cargar_json = cargar_plan
_validar_basico = validar_plan


def _normalizar_caso(datos):
    datos = copy.deepcopy(datos)
    datos['vertidas'] = {int(k) if str(k).isdigit() else k: v for k,v in datos.get('vertidas', {}).items()}
    return datos


def cargar_plan(ruta):
    from .caso.config import leer_config, resolver_plan, aplicar_sobrescrituras
    from .bim.mallas_ifc import extraer_vertidas
    ruta = Path(ruta).resolve()
    if ruta.suffix.lower() == '.json':
        return _cargar_json(ruta)
    datos = yaml.safe_load(ruta.read_text(encoding='utf-8-sig'))
    pasos_conv = [.5, .375, .25]
    if 'caso' in datos:
        if set(datos) != {'caso', 'ajustes', 'pasos_convergencia_m'}:
            raise ValueError('Perfil de demo: campos caso, ajustes y pasos_convergencia_m.')
        fuente = (ruta.parent/datos['caso']).resolve()
        pasos_conv = datos['pasos_convergencia_m']
        datos = aplicar_sobrescrituras(yaml.safe_load(fuente.read_text(encoding='utf-8')), datos['ajustes'])
    else:
        fuente = ruta
    datos['ifc'] = str((fuente.parent/datos['ifc']).resolve())
    if datos.get('clima'):
        datos['clima']['snapshot'] = str((fuente.parent/datos['clima']['snapshot']).resolve())
        if (datos['clima'].get('respaldo') or {}).get('snapshot'):
            datos['clima']['respaldo']['snapshot'] = str((fuente.parent/datos['clima']['respaldo']['snapshot']).resolve())
    config = leer_config(datos, fuente.parent)
    solidos = extraer_vertidas(config.ruta_ifc)
    planes = resolver_plan(config, [(s.vertida_id,s.nombre,s.propiedades) for s in solidos])
    return dict(ifc=str(config.ruta_ifc), material=str(fuente), caso=datos,
                paso_m=config.malla.paso_m, paso_z_m=config.malla.pasos[2],
                pasos_convergencia_m=pasos_conv, final_h=config.tiempo.duracion_s/3600,
                dt_s=min(config.tiempo.dt_max_s, 1800.), guardar_cada_h=config.tiempo.guardar_cada_s/3600,
                ambiente_C=round(config.ambiente.T_C, 1), h_W_m2_K=round(config.ambiente.h_conveccion(0), 2),
                usar_clima=bool(datos.get('clima') or datos['ambiente'].get('ciclo_diario')),
                vertidas=[dict(id=p.vertida_id,inicio_h=p.inicio_s/3600,temperatura_C=p.T_colocacion_C) for p in planes],
                **_controles_e10(datos, config, planes))


def _controles_e10(datos, config, planes):
    """Valores actuales de moldaje, aislación y clima del YAML, y las opciones para la página."""
    from .caso.clima import resumen_snapshots
    from .caso.ciclo_diario import leer_promedios
    defecto = (datos.get('vertidas') or {}).get('defecto') or {}
    p0 = planes[0]
    retiro = None if math.isinf(p0.retiro_moldaje_s) else p0.retiro_moldaje_s/3600
    if defecto.get('moldaje'):
        moldaje = defecto['moldaje']
    else:
        moldaje = 'yaml' if p0.R_lateral > 0 else None  # R numérico del YAML, sin nombre de catálogo
    proteccion = dict(moldaje=moldaje, R_moldaje_yaml=p0.R_lateral, retiro_moldaje_h=retiro,
                      aislacion=defecto.get('aislacion'), aislacion_caras=defecto.get('aislacion_caras', ['superior']),
                      aislacion_desde=defecto.get('aislacion_desde_h', 0), aislacion_hasta_h=defecto.get('aislacion_hasta_h'))
    protecciones = {}
    for nombre, d in (datos.get('protecciones') or {}).items():
        protecciones[nombre] = dict(espesor_m=d['espesor_m'], k_W_mK=d['k_W_mK'], R=d['espesor_m']/d['k_W_mK'])
    snapshots, carpeta, actual = [], None, None
    if datos.get('clima') and config.inicio is not None:
        actual_ruta = Path(datos['clima']['snapshot'])
        carpeta, actual = actual_ruta.parent, actual_ruta.name
        snapshots = resumen_snapshots(carpeta, config.inicio, config.tiempo.duracion_s)
    inicio = None if config.inicio is None else config.inicio.isoformat(timespec='minutes')
    ciclo = datos['ambiente'].get('ciclo_diario')
    return dict(proteccion=proteccion, clima_snapshot=actual, inicio_simulacion=inicio,
                modo_ambiente='ciclo_diario' if ciclo else 'snapshot' if datos.get('clima') else 'constante',
                ciclo_diario=dict(hora_min=(ciclo or {}).get('hora_min', 6.0), hora_max=(ciclo or {}).get('hora_max', 15.0)),
                opciones=dict(protecciones=protecciones, snapshots=snapshots,
                              noviembre=leer_promedios(Path(__file__).resolve().parents[2]/'data/clima_noviembre'),
                              carpeta_snapshots=None if carpeta is None else str(carpeta),
                              inicio=inicio))


# [MAPA:visor-proteccion-clima] controles E10 del visor -> moldaje, aislación y snapshot en el YAML
def _aplicar_controles_e10(datos, plan):
    """Escribe en 'vertidas.defecto' y 'clima' lo elegido en la página (mismas claves que --set)."""
    prot = plan.get('proteccion')
    if prot is not None:
        d = datos.setdefault('vertidas', {}).setdefault('defecto', {})
        catalogo = plan['opciones']['protecciones']
        if prot['moldaje'] != 'yaml':
            d.pop('moldaje', None)
            d.pop('R_lateral_m2K_W', None)
            if prot['moldaje']:
                if prot['moldaje'] not in catalogo:
                    raise ValueError(f"Moldaje {prot['moldaje']!r} no está en el catálogo.")
                d['moldaje'] = prot['moldaje']
            else:
                d['R_lateral_m2K_W'] = 0.0
        if prot['retiro_moldaje_h'] is not None:
            d['retiro_moldaje_h'] = _numero(prot['retiro_moldaje_h'], 'retiro_moldaje_h', positivo=True)
        for clave in ('aislacion', 'aislacion_caras', 'aislacion_desde_h', 'aislacion_hasta_h'):
            d.pop(clave, None)
        if prot['aislacion']:
            if prot['aislacion'] not in catalogo:
                raise ValueError(f"Aislación {prot['aislacion']!r} no está en el catálogo.")
            caras = prot['aislacion_caras']
            if not isinstance(caras, list) or not caras or not set(caras) <= {'superior', 'lateral', 'inferior'}:
                raise ValueError('Aislación: elegir al menos una cara (superior, lateral).')
            d.update(aislacion=prot['aislacion'], aislacion_caras=list(caras))
            desde = prot['aislacion_desde']
            d['aislacion_desde_h'] = 'desmolde' if desde == 'desmolde' else _numero(desde, 'aislacion_desde', minimo=0)
            if prot['aislacion_hasta_h'] is not None:
                d['aislacion_hasta_h'] = _numero(prot['aislacion_hasta_h'], 'aislacion_hasta_h', positivo=True)
    nombre = plan.get('clima_snapshot')
    if plan.get('usar_clima') and nombre and datos.get('clima'):
        opciones = {s['carpeta']: s for s in plan['opciones']['snapshots'] if 'error' not in s}
        if nombre not in opciones:
            raise ValueError(f'Snapshot de clima {nombre!r} no disponible.')
        datos['clima']['snapshot'] = str(Path(plan['opciones']['carpeta_snapshots'])/nombre)
        # Un snapshot de otro año (reanálisis) entra como análogo de las mismas fechas.
        datos['clima']['desplazar_anios'] = opciones[nombre]['desplazar_anios_analogo']


def validar_plan(plan, solidos):
    extras = {'caso', 'paso_z_m', 'usar_clima', 'proteccion', 'clima_snapshot', 'opciones',
              'inicio_simulacion', 'modo_ambiente', 'ciclo_diario'}
    _validar_basico({k:v for k,v in plan.items() if k not in extras}, solidos)
    if 'proteccion' in plan:
        esperadas = {'moldaje', 'R_moldaje_yaml', 'retiro_moldaje_h', 'aislacion', 'aislacion_caras',
                     'aislacion_desde', 'aislacion_hasta_h'}
        if not isinstance(plan['proteccion'], dict) or set(plan['proteccion']) != esperadas:
            raise ValueError(f'proteccion: campos {sorted(esperadas)}.')
        if 'opciones' not in plan:
            raise ValueError('proteccion requiere las opciones del servidor.')
    if 'paso_z_m' in plan:
        _numero(plan['paso_z_m'], 'paso_z_m', positivo=True)
    if 'usar_clima' in plan and type(plan['usar_clima']) is not bool:
        raise ValueError('usar_clima debe ser booleano.')
    return plan


# [MAPA:visor-adaptador] controles del visor E08 -> mismo YAML y mismo motor que la CLI
def configurar_caso(plan):
    """Traduce controles del visor a la misma configuración usada por la CLI."""
    from .caso.config import leer_config
    if 'caso' in plan:
        datos = _normalizar_caso(plan['caso'])
        datos['malla'].update(paso_m=plan['paso_m'], paso_z_m=plan['paso_z_m'])
        if plan.get('inicio_simulacion'):
            try:
                inicio = datetime.fromisoformat(plan['inicio_simulacion'])
            except (TypeError, ValueError) as exc:
                raise ValueError('Inicio de obra: fecha y hora inválidas.') from exc
            if inicio.tzinfo is not None:
                raise ValueError('Inicio de obra: usar hora local sin offset.')
            datos['simulacion']['inicio'] = inicio.isoformat(timespec='seconds')
        _aplicar_controles_e10(datos, plan)
        modo = plan.get('modo_ambiente', 'snapshot') if plan['usar_clima'] else 'constante'
        if modo not in ('snapshot', 'constante', 'ciclo_diario'):
            raise ValueError('Modo de ambiente desconocido.')
        if modo == 'ciclo_diario':
            inicio = datetime.fromisoformat(datos['simulacion']['inicio'])
            tabla = plan['opciones']['noviembre']
            valores = tabla['valores'].get(str(inicio.year))
            if valores is None:
                raise ValueError(f'No hay promedios de noviembre para {inicio.year}.')
            c = plan.get('ciclo_diario', {})
            if not isinstance(c, dict) or set(c) != {'hora_min', 'hora_max'}:
                raise ValueError('ciclo_diario: definir hora_min y hora_max.')
            fuente = f"{tabla['fuente']}; año {inicio.year}; SHA-256 {tabla['huellas']}"
            datos.pop('clima', None)
            datos['ambiente'] = dict(h_W_m2K=plan['h_W_m2_K'],
                ciclo_diario=dict(**valores, **c, fuente=fuente))
        elif modo == 'constante':
            datos.pop('clima', None)
            datos['ambiente'] = dict(T_C=plan['ambiente_C'], h_W_m2K=plan['h_W_m2_K'])
    else:
        props, hid, material = cargar_hormigon(plan['material'])
        datos = dict(malla=dict(paso_m=plan['paso_m'], margen_lateral_m=plan['paso_m'],
                               margen_superior_m=plan['paso_m'], corregir_area=False),
                     simulacion={},ambiente=dict(T_C=plan['ambiente_C'],h_W_m2K=plan['h_W_m2_K']),
                     base=dict(tipo='adiabatico'), suelo=dict(espesor_m=0),
                     hormigones={material['material']:dict(k_W_mK=props.k,rho_kg_m3=props.rho,cp_J_kgK=props.cp,
                         hidratacion=dict(modelo='exponencial',theta_inf_C=hid.incremento_K,tau_h=hid.escala_s/3600,Ea_J_mol=0))},vertidas={})
    datos['ifc'] = plan['ifc']
    datos['simulacion'].update(duracion_h=plan['final_h'],dt_max_h=plan['dt_s']/3600,
                               guardar_cada_h=plan['guardar_cada_h'],guardar_campos=True,
                               guardar_campos_cada_h=plan['guardar_cada_h'])
    for v in plan['vertidas']:
        propia = datos.setdefault('vertidas',{}).setdefault(v['id'],{})
        propia.pop('inicio',None)
        propia.update(inicio_h=v['inicio_h'],T_colocacion_C=v['temperatura_C'])
    return leer_config(datos, Path(plan['ifc']).parent)


class Pipeline:
    """Adaptador del motor compartido a los datos del visor y VTK."""
    def __init__(self):
        self._grillas = {}
        self._pesos = {}

    def ejecutar(self, plan, salida, progreso=lambda mensaje: None, convergencia=True):
        from .bim.mallas_ifc import extraer_vertidas
        from .bim.voxelizador import definir_grilla, voxelizar_solidos, pesos_area
        from .caso.config import resolver_plan
        from .thermal.etapas import DominioVoxel, SimuladorEtapas
        from .visualizacion import activo_en
        plan = json.loads(json.dumps(plan, allow_nan=False))
        salida = Path(salida)
        sha_ifc = hashlib.sha256(Path(plan['ifc']).read_bytes()).hexdigest()
        progreso('Extrayendo geometría IFC')
        solidos = extraer_vertidas(plan['ifc'])
        validar_plan(plan, solidos)
        config = configurar_caso(plan)
        if {s.propiedades['TipoHormigon'] for s in solidos} - set(config.hormigones):
            raise ValueError('TipoHormigon del IFC incompatible con la configuración.')
        planes = resolver_plan(config, [(s.vertida_id,s.nombre,s.propiedades) for s in solidos])
        m = config.malla

        def grilla(dx):
            d = (dx, dx, m.pasos[2] if 'paso_z_m' in plan else dx)
            margen = max(m.margen_lateral_m,dx)
            superior = max(m.margen_superior_m,d[2])
            definicion = definir_grilla(solidos,d,margen,superior,m.espesor_suelo_m)
            if math.prod(definicion.forma) > MAX_CELDAS:
                raise ValueError(f'Grilla demasiado grande; aumentar Δx/Δz (máximo {MAX_CELDAS:,} celdas).')
            clave = (sha_ifc,d,margen,superior,m.espesor_suelo_m)
            if clave not in self._grillas:
                progreso(f'Voxelizando Δx={dx:g} m, Δz={d[2]:g} m')
                nueva = voxelizar_solidos(solidos,definicion)
                if nueva.voxeles_solapados:
                    raise ValueError('Solape entre vertidas del IFC.')
                if len(self._grillas) >= 6:
                    vieja = next(iter(self._grillas))
                    self._grillas.pop(vieja)
                    self._pesos.pop(vieja,None)
                self._grillas[clave] = nueva
            return self._grillas[clave],clave

        volumenes = []
        for dx in sorted(set([plan['paso_m']]+(plan['pasos_convergencia_m'] if convergencia else [])),reverse=True):
            g,_ = grilla(dx)
            filas = [(s.vertida_id,s.volumen,g.volumen(s.vertida_id)) for s in solidos]
            filas.append(('total',sum(s.volumen for s in solidos),float(np.count_nonzero(g.vertida_id))*g.volumen_voxel))
            for vid,vref,vh in filas:
                volumenes.append(dict(paso_m=dx,paso_z_m=g.paso[2],vertida_id=vid,ifc_m3=vref,voxel_m3=vh,error_relativo=abs(vh-vref)/vref))
        g,clave = grilla(plan['paso_m'])
        if np.prod(g.forma)*(plan['final_h']/plan['guardar_cada_h']+len(planes)+2)>40_000_000:
            raise ValueError('Demasiados campos 3D en memoria; aumentar guardar_cada_h o el paso de malla.')
        if m.corregir_area and clave not in self._pesos:
            progreso('Corrigiendo el área exterior desde las normales IFC')
            self._pesos[clave] = pesos_area(solidos,g)
        simu = SimuladorEtapas(DominioVoxel(g.vertida_id,g.es_suelo,g.paso,self._pesos.get(clave) if m.corregir_area else None),
                    planes,config.hormigones,config.ambiente,config.base,config.tiempo,config.suelo,
                    config.T_suelo_inicial_C,True,config.criterios.profundidad_superficie_m,config.campos_cada_s,
                    progreso=lambda t,fin: progreso(f'Simulando {t/3600:g} / {fin/3600:g} h')).ejecutar()
        salida.mkdir(parents=True,exist_ok=True)
        mascara = g.vertida_id>0
        fotogramas=[]
        coleccion=ET.Element('VTKFile',type='Collection',version='0.1',byte_order='LittleEndian')
        datasets=ET.SubElement(coleccion,'Collection')
        proxy=SimpleNamespace(vertida_id=g.vertida_id,es_suelo=g.es_suelo,origen=g.definicion.origen,paso=g.paso)
        for n,(t,T) in enumerate(sorted(simu.campos.items())):
            activos=activo_en(g,planes,t)
            temperaturas=np.where(activos,T,np.nan)
            valores=temperaturas[activos]
            fotogramas.append(dict(tiempo_h=t/3600,T_f32=codificar_f32(temperaturas[mascara]),
                                   fecha_hora=None if config.inicio is None else (config.inicio+timedelta(seconds=t)).isoformat(timespec='minutes'),
                                   ambiente_C=config.ambiente.temperatura(t),
                                   Tmax_C=float(valores.max()) if valores.size else None,
                                   Tmin_C=float(valores.min()) if valores.size else None,
                                   volumen_activo_m3=float(activos.sum())*g.volumen_voxel))
            edades=np.full(g.forma,np.nan)
            for p in planes:
                edades[activos & (g.vertida_id==p.vertida_id)]=t-p.inicio_s
            Tvtk=np.where(activos|g.es_suelo,T,np.nan)
            archivo=f'temperatura_{n:04d}.vti'
            exportar_vti(salida/archivo,proxy,SimpleNamespace(T=Tvtk,edad_s=edades,activos=activos))
            ET.SubElement(datasets,'DataSet',timestep=str(t),group='',part='0',file=archivo)
        ET.ElementTree(coleccion).write(salida/'temperaturas.pvd',encoding='utf-8',xml_declaration=True)
        b=simu.balance
        balances=[dict(tiempo_h=plan['final_h'],energia_J=b['E_final_J'],inicial_J=b['E_inicial_J'],
                        hidratacion_J=b['hidratacion_J'],borde_J=b['ambiente_J']+b['base_J']-b['fuga_vacio_J'],
                        colocacion_J=b['colocacion_J'],residuo_J=b['residuo_J'])]
        def git(*args):
            try:
                r=subprocess.run(['git',*args],cwd=Path(__file__).resolve().parents[3],capture_output=True,text=True,timeout=5)
                return r.stdout.strip() if r.returncode==0 else None
            except (OSError,subprocess.TimeoutExpired):
                return None
        mallas=[dict(id=s.vertida_id,guid=s.guid,vertices=s.triangulos.reshape(-1,3).tolist(),
                      triangulos=np.arange(s.triangulos.size//3).reshape(-1,3).tolist()) for s in solidos]
        if 'caso' in plan:
            plan['caso']=config.datos
        material=dict(material=', '.join(config.hormigones),estado='parámetros docentes y supuestos; sin calibración experimental')
        # [MAPA:visor-moldaje] horarios resueltos del moldaje para la reproducción 3D
        resultado=dict(plan=plan,caso_ejecutado=config.datos,ifc_sha256=sha_ifc,commit=git('rev-parse','HEAD'),
                        codigo_modificado=bool(git('status','--porcelain')),material=material,
                        origen_m=list(g.definicion.origen),forma=list(g.forma),paso_m=plan['paso_m'],pasos_m=list(g.paso),
                        indices=np.argwhere(mascara).tolist(),vertida_id=g.vertida_id[mascara].tolist(),
                        volumenes=volumenes,balances=balances,fotogramas=fotogramas,mallas=mallas,
                        moldajes=[dict(vertida_id=p.vertida_id,inicio_h=p.inicio_s/3600,
                            retiro_h=None if math.isinf(p.retiro_moldaje_s) else (p.inicio_s+p.retiro_moldaje_s)/3600,
                            R=p.R_lateral) for p in planes if p.visible and p.R_lateral>0],
                        advertencias=simu.advertencias,nota_clima=config.nota_clima,
                        suelo_incluido=bool(g.es_suelo.any()),motor='SimuladorEtapas')
        (salida/'plan_ejecutado.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        (salida/'caso_ejecutado.yaml').write_text(yaml.safe_dump(config.datos,allow_unicode=True,sort_keys=False),encoding='utf-8')
        (salida/'resultado.json').write_text(json.dumps(resultado,ensure_ascii=False,allow_nan=False),encoding='utf-8')
        progreso('Completado')
        return resultado
