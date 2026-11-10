"""Indicadores a partir de campos conocidos: no ejecuta una simulación nueva."""
import json
from types import SimpleNamespace

import numpy as np
import pytest

from mcplan.indicadores import crear_indicadores, elegir_sondas


def caso(inicio_segunda=24):
    ids=np.zeros((6,4,4),dtype=int)
    ids[1:5,1:3,1]=1
    ids[1:5,1:3,2]=2
    g=SimpleNamespace(vertida_id=ids,es_suelo=np.zeros_like(ids,dtype=bool),
        paso=(.5,.5,.05),definicion=SimpleNamespace(origen=(-1,-1,0)))
    planes=[SimpleNamespace(vertida_id=1,visible=True,inicio_s=0),
            SimpleNamespace(vertida_id=2,visible=True,inicio_s=inicio_segunda*3600)]
    campos={}
    for t,a,b in [(0,18,10),(24,40,18),(48,35,45)]:
        T=np.full(ids.shape,10.0);T[ids==1]=a;T[ids==2]=b;campos[t*3600]=T
    sim=SimpleNamespace(tiempos_s=[0,24*3600,48*3600],T_max_C=[18,40,45],
        T_max_vertida_C={1:[18,40,35],2:[np.nan,18,45]},
        T_sup_min_vertida_C={1:[18,20,19],2:[np.nan,18,25]},campos=campos)
    config=SimpleNamespace(tiempo=SimpleNamespace(duracion_s=48*3600),
        criterios=SimpleNamespace(T_max_C=70,delta_T_C=20,profundidad_superficie_m=.025))
    return sim,g,planes,config


def test_resumen_picos_y_diferencial_dentro_de_la_misma_vertida():
    a=crear_indicadores(*caso())
    assert a['resumen']['pico']==dict(valor_C=45,tiempo_h=48,vertida_id=2)
    assert a['resumen']['diferencial_maximo']==dict(valor_C=20,tiempo_h=24,vertida_id=1)
    assert a['series']['por_vertida'][1]['maxima_C'][0] is None
    assert a['series']['por_vertida'][0]['delta_C']==[0,20,16]
    assert a['criterios']['profundidad_superficie_m']==.025
    json.dumps(a,allow_nan=False)


def test_temperatura_previa_e_interfaz_y_ventana_de_colocacion():
    a=crear_indicadores(*caso());e=a['colocaciones'][1]
    assert e['intervalo_h']==24 and e['anterior_id']==1
    assert e['previa_media_C']==40 and e['previa_maxima_C']==40 and e['previa_nucleo_C']==40
    assert e['interfaz_media_C']==40 and e['contactos'][0]['vertida_id']==1
    assert a['resumen']['ventana_colocaciones_h']==24
    assert a['resumen']['observacion_ultima_vertida_h']==24
    assert 'No evaluadas mecánicamente' in a['juntas']


def test_sondas_son_fijas_y_no_se_inventa_temperatura_antes_del_vertido():
    sim,g,planes,config=caso();sondas=elegir_sondas(g,planes)
    assert len(sondas)==4
    for s in sondas:
        assert g.vertida_id[tuple(s['indice'])]==s['vertida_id']
        assert np.allclose(s['centro_m'],np.array(g.definicion.origen)+(np.array(s['indice'])+.5)*g.paso)
    a=crear_indicadores(sim,g,planes,config)
    s=next(s for s in a['sondas'] if s['vertida_id']==2 and s['tipo']=='nucleo')
    assert s['temperatura_C']==[None,18,45]


def test_sin_superficie_no_inventa_delta_y_vertida_fuera_del_horizonte():
    sim,g,planes,config=caso(72)
    sim.T_sup_min_vertida_C[2]=[np.nan]*3
    a=crear_indicadores(sim,g,planes,config)
    assert a['series']['por_vertida'][1]['diferencial_maximo']['valor_C'] is None
    assert not a['colocaciones'][1]['incluida_en_horizonte']
    assert a['colocaciones'][1]['previa_media_C'] is None
    assert a['resumen']['observacion_ultima_vertida_h']==0


def test_vertidas_simultaneas_no_se_presentan_como_sucesivas():
    a=crear_indicadores(*caso(0))
    assert a['colocaciones'][1]['intervalo_h']==0
    assert a['colocaciones'][1]['previa_media_C'] is None
    assert a['colocaciones'][1]['contactos']==[]
