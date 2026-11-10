"""Regresiones de la integración del motor compartido con el visor E08."""
import base64
import json
from pathlib import Path
import numpy as np
import pytest
import shutil
import subprocess

from mcplan.thermal.etapas import (DominioVoxel,PlanVertida,Material,Hormigon,
    Ambiente,CondicionBase,ParametrosTiempo,SimuladorEtapas)
from mcplan.pipeline import cargar_plan,configurar_caso,Pipeline
from mcplan.caso.pipeline import ejecutar_pipeline
from mcplan.caso.config import leer_config,resolver_plan,ErrorConfiguracion

RAIZ=Path(__file__).resolve().parents[1]


def motor(final, inicio=10., intervalo=14.):
    ids=np.array([1,2],dtype=np.int16).reshape(2,1,1)
    return SimuladorEtapas(DominioVoxel(ids,np.zeros_like(ids,bool),1.),
        [PlanVertida(1,0.,20.,'M1'),PlanVertida(2,inicio,50.,'M1')],
        {'M1':Hormigon(Material(2.22,2400.,970.))},Ambiente(20.,0.),CondicionBase('adiabatico'),
        ParametrosTiempo(final,dt_max_s=7.,guardar_cada_s=intervalo),guardar_campos=True,
        campos_cada_s=intervalo).ejecutar()


def test_activacion_al_final_coherente_con_temperatura_energia_y_campos():
    r=motor(10.)
    assert r.activo_final.ravel().tolist()==[True,True]
    assert r.T_final[1,0,0]==50.
    assert r.edad_equivalente_final_s[1,0,0]==0.
    assert r.campos[10.][1,0,0]==50.
    assert abs(r.balance['residuo_J'])<1e-6


def test_campos_en_eventos_y_tiempos_exactos_sin_temperaturas_previas():
    r=motor(30.)
    assert sorted(r.campos)==[0.,10.,14.,28.,30.]
    assert r.campos[10.][1,0,0]==50.
    # El evento coincide con el guardado: se conserva el estado posterior.
    r=motor(30.,inicio=14.)
    assert r.campos[14.][1,0,0]==50.


def perfil_corto():
    p=cargar_plan(RAIZ/'configs/e08_demo.yaml')
    p.update(paso_m=.5,paso_z_m=.275,final_h=.02,guardar_cada_h=.01,dt_s=20.)
    p['caso']['suelo']['espesor_m']=.55
    p['vertidas'][1]['inicio_h']=.005
    return p


def test_perfil_usa_fuente_compartida_clima_suelo_y_malla_anisotropica():
    p=perfil_corto()
    c=configurar_caso(json.loads(json.dumps(p)))
    assert c.malla.pasos==(.5,.5,.275)
    assert c.suelo is not None
    assert c.ambiente.h_viento is not None
    assert 'ANÁLOGO' in c.nota_clima
    assert c.hormigones['M1'].hidratacion.Ea_J_mol==40000
    p['usar_clima']=False
    c=configurar_caso(p)
    assert c.ambiente.h_viento is None
    assert c.ambiente.serie_t_s==()
    assert c.ambiente.emisividad==0.


def test_visor_y_cli_ejecutan_el_mismo_motor_y_plan(tmp_path):
    p=perfil_corto()
    referencia=ejecutar_pipeline(configurar_caso(p))
    r=Pipeline().ejecutar(p,tmp_path,convergencia=False)
    assert r['motor']=='SimuladorEtapas'
    assert r['suelo_incluido']
    assert r['pasos_m']==[.5,.5,.275]
    indices=tuple(np.array(r['indices']).T)
    T=np.frombuffer(base64.b64decode(r['fotogramas'][-1]['T_f32']),dtype='<f4')
    activos=referencia.simulacion.activo_final[indices]
    np.testing.assert_allclose(T[activos],referencia.simulacion.T_final[indices][activos],rtol=1e-6)
    assert np.isnan(T[~activos]).all()
    b=r['balances'][-1]
    assert abs(b['residuo_J'])/max(abs(b['energia_J']),1)<1e-12
    ejecutado=leer_config(tmp_path/'caso_ejecutado.yaml')
    planes=resolver_plan(ejecutado,[(s.vertida_id,s.nombre,s.propiedades) for s in referencia.solidos])
    assert planes[1].inicio_s==.005*3600


def test_visible_de_config_no_acepta_texto_false_como_booleano():
    p=perfil_corto()
    p['caso']['vertidas'].setdefault(2,{})['visible']='false'
    c=configurar_caso(p)
    with pytest.raises(ErrorConfiguracion,match='true o false'):
        resolver_plan(c,[(vid,f'V{vid}',dict(Inicio_h=0,TemperaturaColocacion_C=18,TipoHormigon='M1')) for vid in range(1,6)])


def test_geometria_del_renderer_anisotropica_y_filtros_sin_navegador(tmp_path):
    node=shutil.which('node')
    if not node:
        pytest.skip('Node no instalado: prueba del renderer JS puro opcional.')
    html=(RAIZ/'visor_e08/index.html').read_text(encoding='utf-8')
    fuente=html[html.index('function caras()'):html.index('function prepararCanvas')]
    script=tmp_path/'renderer.cjs'
    script.write_text('''const vm=require('node:vm'),assert=require('node:assert/strict');
const controls={modo:'temperatura',corte:'10',tiempo:'0'};
const c={facesCache:null,visibles:()=>new Set([1,2]),
 resultado:{paso_m:.5,pasos_m:[.5,.5,.05],origen_m:[0,0,0],forma:[2,1,1],indices:[[0,0,0],[1,0,0]],vertida_id:[1,2]},
 frames:[new Float32Array([20,25])],$:id=>({value:controls[id],getAttribute:()=> 'false'}),
 colorT:()=>[255,0,0],rgb:()=>[255,0,0],colores:['#ffffff'],base:{vertidas:[{id:1},{id:2}]}};
'''+'const source='+json.dumps(fuente)+';\n'+'''
function render(){c.facesCache=null;vm.runInNewContext(source+';globalThis.f=caras();',c);return c.f;}
let f=render();assert.equal(f.length,10);
let points=f.flatMap(face=>face.v);assert(points.flat().every(Number.isFinite));
assert.equal(Math.max(...points.map(p=>p[0])),1);
assert.equal(Math.max(...points.map(p=>p[1])),.5);
assert.equal(Math.max(...points.map(p=>p[2])),.05);
c.visibles=()=>new Set([1]);assert.equal(render().length,6);
controls.corte='.01';assert.equal(render().length,0);
controls.corte='10';c.frames=[new Float32Array([NaN,25])];assert.equal(render().length,0);
''',encoding='utf-8')
    r=subprocess.run([node,str(script)],capture_output=True,text=True,timeout=15)
    assert r.returncode==0,r.stderr
