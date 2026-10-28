"""Regresiones de los puntos corregidos durante la revisión E04/E05."""
import numpy as np
import pytest
from mcplan.thermal import (MallaVoxel,SolverVoxel,PropiedadesTermicas,
                            adiabatico,dirichlet,neumann,robin)


def todos(m,b):
    return {c:b for c in m.caras}


@pytest.mark.parametrize('dim',[1,2,3])
def test_superficie_dirichlet_es_valor_impuesto_no_centro(dim):
    m=MallaVoxel.uniforme((4,)*dim,(.1,)*dim,PropiedadesTermicas(2.,3.,4.))
    s=SolverVoxel(m,todos(m,dirichlet(20.)))
    T=np.full(m.forma,22.8)
    for Ts in s.temperatura_superficie(T).values():
        np.testing.assert_allclose(Ts,20.,rtol=0,atol=0)


@pytest.mark.parametrize('R',[0.,.3])
def test_superficie_robin_cierra_resistencias_y_ley_convectiva(R):
    m=MallaVoxel.uniforme((4,5),(.1,.2),PropiedadesTermicas(2.,3.,4.))
    s=SolverVoxel(m,todos(m,robin(20.,10.,R)))
    T=np.full(m.forma,40.)
    superficie=s.temperatura_superficie(T)
    for cara,Ts in superficie.items():
        eje='xyz'.index(cara[0])
        q=(20.-40.)/(m.paso[eje]/(2*2.)+R+1/10.)  # positivo entrando
        np.testing.assert_allclose(Ts,40.+q*m.paso[eje]/(2*2.))
        np.testing.assert_allclose(q,(20.-Ts)/(R+1/10.))
        assert np.all((20.<Ts)&(Ts<40.))


def test_superficie_neumann_usa_normal_entrante_en_ambos_lados():
    m=MallaVoxel.uniforme((4,),(.1,),PropiedadesTermicas(2.,3.,4.))
    s=SolverVoxel(m,{'x-':neumann(10.),'x+':neumann(-10.)})
    Ts=s.temperatura_superficie(np.full(4,20.))
    assert Ts['x-']==pytest.approx(20.25)
    assert Ts['x+']==pytest.approx(19.75)


def test_limite_monotono_no_es_limite_espectral_dirichlet():
    m=MallaVoxel.uniforme((4,4),(.1,.1),PropiedadesTermicas(1.,1.,1.))
    s=SolverVoxel(m,todos(m,dirichlet(0.)))
    N=int(np.prod(m.forma))
    base=np.eye(N)
    A=np.column_stack([s.tasa_calor(e.reshape(m.forma)).ravel()/m.capacidad.ravel() for e in base])
    eig=np.linalg.eigvalsh(A)
    dt_espectral=2/abs(eig[0])
    assert s.dt_max()==pytest.approx(.1**2/6)
    assert dt_espectral==pytest.approx(.1**2/4)
    assert s.dt_max()<dt_espectral
    assert np.max(abs(1+dt_espectral*eig))<=1+1e-12
    assert np.max(abs(1+dt_espectral*1.1*eig))>1


def test_fuente_temporal_se_evalua_una_vez_por_paso():
    m=MallaVoxel.uniforme((3,3),(.1,.1),PropiedadesTermicas(1.,2.,3.))
    llamadas=[]
    def fuente(t):
        llamadas.append(t)
        return 10.+t
    s=SolverVoxel(m,todos(m,adiabatico()),fuente)
    dt=.5*s.dt_max()
    r=s.resolver(20.,dt,10)
    assert llamadas==pytest.approx([i*dt for i in range(10)])
    E=sum(10+i*dt for i in range(10))*dt*np.prod(m.forma)*m.volumen_celda
    assert r.calor_fuente_acumulado==pytest.approx(E)
    assert r.energia[-1]-r.energia[0]==pytest.approx(E)


def test_rechaza_dimensiones_y_pasos_no_enteros():
    with pytest.raises(ValueError,match='entero'):
        MallaVoxel((3.5,4),(.1,.1),1.,1.,1.)
    m=MallaVoxel.uniforme((3,3),(.1,.1),PropiedadesTermicas(1.,1.,1.))
    s=SolverVoxel(m,todos(m,adiabatico()))
    with pytest.raises(ValueError,match='entero'):
        s.resolver(20.,s.dt_max(),1.5)
