"""Indicadores para comparar escenarios térmicos, sin evaluación mecánica de juntas."""
from __future__ import annotations

import math
import base64
import copy
import hashlib
from pathlib import Path

import numpy as np

from .bim.voxelizador import caras_expuestas


def _numero(valor):
    return float(valor) if math.isfinite(float(valor)) else None


def _serie(valores):
    return [_numero(v) for v in valores]


def _pico(valores, tiempos):
    a = np.asarray(valores, dtype=float)
    if not np.isfinite(a).any():
        return dict(valor_C=None, tiempo_h=None)
    i = int(np.nanargmax(a))
    return dict(valor_C=float(a[i]), tiempo_h=float(tiempos[i]))


def elegir_sondas(grilla, planes):
    """Sondas geométricas fijas por pieza: centro aproximado y borde lateral.

    El núcleo es la celda más próxima al centroide de la vertida, no el máximo
    térmico móvil. El borde se elige entre caras expuestas de la geometría final,
    a la cota más próxima al núcleo; si no hay laterales, se usa otra cara expuesta.
    """
    ids = grilla.vertida_id
    incluidos = {p.vertida_id for p in planes if p.visible}
    hormigon = np.isin(ids, list(incluidos))
    caras = caras_expuestas(hormigon | grilla.es_suelo)
    lateral = np.logical_or.reduce([caras[k] for k in ('x-', 'x+', 'y-', 'y+')])
    exterior = np.logical_or.reduce(list(caras.values()))
    paso = np.asarray(grilla.paso)
    if paso.ndim == 0:
        paso = np.repeat(paso, 3)
    origen = np.asarray(grilla.definicion.origen)
    sondas = []
    for vid in sorted(incluidos):
        indices = np.argwhere(ids == vid)
        if not len(indices):
            continue
        xyz = origen + (indices + .5) * paso
        centro = xyz.mean(axis=0)
        nucleo = indices[int(np.argmin(np.sum((xyz - centro)**2, axis=1)))]
        candidatos = np.argwhere((ids == vid) & lateral)
        if not len(candidatos):
            candidatos = np.argwhere((ids == vid) & exterior)
        for tipo, indice in [('nucleo', nucleo)]:
            sondas.append(dict(vertida_id=vid, tipo=tipo, indice=indice.tolist(),
                               centro_m=(origen + (indice + .5)*paso).tolist()))
        if len(candidatos):
            dz = np.abs(candidatos[:, 2] - nucleo[2])
            candidatos = candidatos[dz == dz.min()]
            puntos = origen + (candidatos + .5)*paso
            borde = candidatos[int(np.argmax(np.sum((puntos[:, :2]-centro[:2])**2, axis=1)))]
            sondas.append(dict(vertida_id=vid, tipo='borde', indice=borde.tolist(),
                               centro_m=(origen + (borde + .5)*paso).tolist()))
    return sondas


def _adyacentes(mascara):
    resultado = np.zeros_like(mascara)
    for eje in range(3):
        a, b = [slice(None)]*3, [slice(None)]*3
        a[eje], b[eje] = slice(None, -1), slice(1, None)
        resultado[tuple(a)] |= mascara[tuple(b)]
        resultado[tuple(b)] |= mascara[tuple(a)]
    return resultado


# [MAPA:indicadores-visor] series, sondas fijas, temperaturas antes de vertidas y criterios docentes
def crear_indicadores(simulacion, grilla, planes, config):
    activos = sorted((p for p in planes if p.visible), key=lambda p: (p.inicio_s, p.vertida_id))
    tiempos_h = [float(t/3600) for t in simulacion.tiempos_s]
    por_vertida = []
    for p in activos:
        vid = p.vertida_id
        maxima = simulacion.T_max_vertida_C.get(vid, [math.nan]*len(tiempos_h))
        superficie = simulacion.T_sup_min_vertida_C.get(vid, [math.nan]*len(tiempos_h))
        delta = np.asarray(maxima)-np.asarray(superficie)
        por_vertida.append(dict(vertida_id=vid, inicio_h=p.inicio_s/3600,
            maxima_C=_serie(maxima), superficie_min_C=_serie(superficie), delta_C=_serie(delta),
            pico=_pico(maxima, tiempos_h), diferencial_maximo=_pico(delta, tiempos_h)))
    pico = _pico(simulacion.T_max_C, tiempos_h)
    pico['vertida_id'] = next((v['vertida_id'] for v in por_vertida
        if v['pico']['valor_C'] == pico['valor_C'] and v['pico']['tiempo_h'] == pico['tiempo_h']), None)
    diferenciales = [v for v in por_vertida if v['diferencial_maximo']['valor_C'] is not None]
    peor = max(diferenciales, key=lambda v: v['diferencial_maximo']['valor_C']) if diferenciales else None
    diferencial = dict(valor_C=None, tiempo_h=None, vertida_id=None)
    if peor:
        diferencial.update(peor['diferencial_maximo'], vertida_id=peor['vertida_id'])
    campos = sorted(simulacion.campos.items())
    inicios = {p.vertida_id: p.inicio_s for p in activos}
    sondas = elegir_sondas(grilla, activos)
    for sonda in sondas:
        indice = tuple(sonda['indice'])
        valores = [float(T[indice]) if t >= inicios[sonda['vertida_id']]-1e-8 else math.nan for t,T in campos]
        th = [t/3600 for t,_ in campos]
        sonda.update(tiempos_h=th, temperatura_C=_serie(valores), pico=_pico(valores, th))
    ids = grilla.vertida_id
    colocaciones = []
    for n, p in enumerate(activos):
        previo = activos[n-1] if n else None
        T = simulacion.campos.get(p.inicio_s)
        fila = dict(vertida_id=p.vertida_id, inicio_h=p.inicio_s/3600,
            incluida_en_horizonte=p.inicio_s<=config.tiempo.duracion_s,
            anterior_id=previo.vertida_id if previo else None,
            intervalo_h=(p.inicio_s-previo.inicio_s)/3600 if previo else None,
            previa_media_C=None, previa_maxima_C=None, previa_nucleo_C=None,
            interfaz_media_C=None, contactos=[])
        # Si dos vertidas son simultáneas no se inventa un estado anterior entre ellas.
        if previo and previo.inicio_s < p.inicio_s and T is not None:
            m = ids == previo.vertida_id
            if m.any():
                fila.update(previa_media_C=float(np.mean(T[m])), previa_maxima_C=float(np.max(T[m])))
            sonda = next((s for s in sondas if s['vertida_id']==previo.vertida_id and s['tipo']=='nucleo'), None)
            if sonda:
                fila['previa_nucleo_C'] = float(T[tuple(sonda['indice'])])
        if T is not None:
            vecinos = _adyacentes(ids == p.vertida_id)
            for q in activos:
                if q.inicio_s >= p.inicio_s:
                    continue
                interfaz = vecinos & (ids == q.vertida_id)
                if interfaz.any():
                    fila['contactos'].append(dict(vertida_id=q.vertida_id,
                        media_C=float(np.mean(T[interfaz])), maxima_C=float(np.max(T[interfaz]))))
            valores = [T[vecinos & (ids==q.vertida_id)] for q in activos if q.inicio_s<p.inicio_s]
            valores = [a for a in valores if a.size]
            if valores:
                fila['interfaz_media_C'] = float(np.mean(np.concatenate(valores)))
        colocaciones.append(fila)
    inicio = min((p.inicio_s for p in activos), default=0)
    ultimo = max((p.inicio_s for p in activos), default=0)
    criterio = config.criterios
    return dict(version=1,
        resumen=dict(pico=pico, diferencial_maximo=diferencial,
            numero_vertidas=len(activos), ventana_colocaciones_h=(ultimo-inicio)/3600,
            ultima_colocacion_h=ultimo/3600, duracion_h=config.tiempo.duracion_s/3600,
            observacion_ultima_vertida_h=max(0,(config.tiempo.duracion_s-ultimo)/3600)),
        criterios=dict(T_max_C=criterio.T_max_C if criterio else None,
            delta_T_C=criterio.delta_T_C if criterio else None,
            profundidad_superficie_m=criterio.profundidad_superficie_m if criterio else None,
            alcance='Criterios docentes configurados; no certifican seguridad estructural.'),
        series=dict(tiempos_h=tiempos_h, maxima_global_C=_serie(simulacion.T_max_C), por_vertida=por_vertida),
        sondas=sondas, colocaciones=colocaciones,
        juntas='No evaluadas mecánicamente. Contacto térmico perfecto; las juntas y los intervalos requieren revisión estructural.',
        definicion_sondas='Núcleo geométrico aproximado y borde lateral expuesto de la geometría final; posiciones fijas, no máximos móviles.',
        muestreo='Picos y diferenciales: registros del motor. Sondas: campos guardados; no es una búsqueda entre pasos temporales.')


def reconstruir_indicadores(resultado):
    """Postprocesa resultados antiguos sin avanzar tiempo ni resolver difusión.

    El clima y las superficies se evalúan sobre los campos de hormigón guardados.
    Se conserva explícitamente que el muestreo es el de esos fotogramas.
    """
    from .caso import leer_config, ejecutar_pipeline
    from .bim.voxelizador import pesos_area
    from .thermal.etapas import DominioVoxel, ResultadoEtapas, SimuladorEtapas
    datos=copy.deepcopy(resultado['caso_ejecutado'])
    datos['vertidas']={int(k) if str(k).isdigit() else k:v for k,v in datos.get('vertidas',{}).items()}
    config=leer_config(datos,Path(datos['ifc']).parent)
    if hashlib.sha256(config.ruta_ifc.read_bytes()).hexdigest()!=resultado['ifc_sha256']:
        raise ValueError('El IFC actual no coincide con el resultado guardado.')
    geometria=ejecutar_pipeline(config,simular=False)
    g=geometria.grilla; mascara=g.vertida_id>0
    if not np.array_equal(np.argwhere(mascara),np.asarray(resultado['indices'])):
        raise ValueError('La grilla guardada no coincide con el caso ejecutado.')
    pesos=pesos_area(geometria.solidos,g) if config.malla.corregir_area else None
    lector=SimuladorEtapas(DominioVoxel(g.vertida_id,g.es_suelo,g.paso,pesos),geometria.plan,
        config.hormigones,config.ambiente,config.base,config.tiempo,config.suelo,
        config.T_suelo_inicial_C,False,config.criterios.profundidad_superficie_m if config.criterios else 0)
    res=ResultadoEtapas(T_max_vertida_C={p.vertida_id:[] for p in geometria.plan if p.visible})
    for f in resultado['fotogramas']:
        t=f['tiempo_h']*3600
        valores=np.frombuffer(base64.b64decode(f['T_f32']),dtype='<f4')
        if len(valores)!=int(mascara.sum()):
            raise ValueError('Campo térmico guardado con tamaño inválido.')
        T=np.full(g.vertida_id.shape,config.ambiente.temperatura(t),dtype=np.float32)
        T[mascara]=np.where(np.isfinite(valores),valores,config.ambiente.temperatura(t))
        activo=np.zeros_like(mascara);activo[mascara]=np.isfinite(valores)
        solido=activo|g.es_suelo;k,_,_=lector._propiedades(activo,solido)
        caras=lector._caras_etapa(t,activo,solido,k)
        lector._registrar(res,t,T,activo,caras,g.vertida_id)
        res.campos[t]=T
    indicadores=crear_indicadores(res,g,geometria.plan,config)
    indicadores['muestreo']='Reconstruido de los fotogramas guardados, sin nueva simulación; los picos y sondas se limitan a ese muestreo.'
    return indicadores
