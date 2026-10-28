"""Batería física: referencias analíticas y balances independientes."""
import numpy as np
import pytest
from mcplan.thermal.boundaries import CondicionBorde as BC, PropiedadesTermicas
from mcplan.thermal.solver_nd import MallaTermica
from mcplan.thermal.solver1d import resolver_1d, energia_1d
from mcplan.thermal.verification import sinusoidal


@pytest.mark.parametrize('dim',[1,2,3])
def test_sinusoidal_y_convergencia(dim):
    errores = []
    for n in (8,16,32):
        _,r,exacta = sinusoidal(dim,n,longitudes=[1.,1.3,.8][:dim])
        errores.append(float(np.max(abs(r.T-exacta))))
    orden = np.log2(errores[-2]/errores[-1])
    print(f'\nsinusoidal {dim}D: errores={errores}, orden={orden:.3f}')
    assert errores[2] < errores[1] < errores[0]
    assert 1.7 < orden < 2.3
    assert errores[-1] < 0.04  # °C para A=50, malla 32 y dt proporcional a dx²


@pytest.mark.parametrize('dim',[1,2,3])
def test_adiabatico_conserva_energia_no_uniforme(dim):
    forma = (7,)*dim
    # Capacidades y conductividades variables: no solo material homogéneo.
    rng = np.random.default_rng(42)
    m = MallaTermica(forma,[1.]*dim,1+rng.random(forma),2+rng.random(forma),3.)
    T = 20+30*rng.random(forma)
    r = m.resolver(T,0.15)
    assert np.max(abs(r.T-T)) > 0.01
    assert abs(r.energia_final-r.energia_inicial) < 1e-12*abs(r.energia_inicial)


@pytest.mark.parametrize('dim',[1,2,3])
def test_fuente_uniforme_y_energia(dim):
    m = MallaTermica((6,)*dim,[1.2]*dim,2.22,2400.,970.)
    r = m.resolver(20.,3600.,fuente=1000.)
    esperado = 20+1000*3600/(2400*970)
    np.testing.assert_allclose(r.T,esperado,atol=1e-10,rtol=0)
    aporte = 1000*1.2**dim*3600
    assert r.energia_final-r.energia_inicial == pytest.approx(aporte,rel=1e-10)


@pytest.mark.parametrize('dim',[1,2,3])
@pytest.mark.parametrize('flujo',[-12.,12.])
def test_neumann_no_nulo_balance_y_signo(dim,flujo):
    lados = [1.,1.3,.8][:dim]
    m = MallaTermica((6,)*dim,lados,2.,3.,4.,{(0,1):BC('neumann',flujo)})
    r = m.resolver(20.,.1)
    perdida = flujo*float(np.prod(lados[1:]))*.1
    assert r.energia_final-r.energia_inicial == pytest.approx(-perdida,abs=1e-10)
    assert np.sign(np.mean(r.T)-20) == -np.sign(flujo)


def test_neumann_legacy_1d_no_nulo():
    p = PropiedadesTermicas(2.,3.,4.)
    r = resolver_1d(np.full(11,20.),p,.1,.001,20,BC('neumann',-3.),BC('neumann',7.))
    cambio = energia_1d(r.T,p,.1)-energia_1d(np.full(11,20.),p,.1)
    assert cambio == pytest.approx(-(7.-3.)*.02,abs=1e-11)


@pytest.mark.parametrize('dim',[1,2,3])
def test_robin_estacionario_analitico(dim):
    # Tizq=80, Tinf=20; q=(80-20)/(L/k+1/h), T(x)=80-q*x/k.
    k,h,L = 2.,5.,1.
    q = 60/(L/k+1/h)
    m = MallaTermica((8,)*dim,[L]*dim,k,3.,4.,
                     {(0,0):BC('dirichlet',80.),(0,1):BC('robin',20.,h)})
    exacta = 80-q*m.coordenadas()[0]/k
    P,Q = m.potencia(exacta)
    np.testing.assert_allclose(P,0.,atol=1e-11)
    assert Q == pytest.approx(0.,abs=1e-11)
    r = m.resolver(exacta,1.)
    np.testing.assert_allclose(r.T,exacta,atol=1e-10)


def test_robin_transitorio_balance_y_equilibrio():
    m = MallaTermica((12,),[1.],2.,3.,4.,
                     {(0,0):BC('dirichlet',80.),(0,1):BC('robin',20.,5.)})
    r = m.resolver(20.,40.)
    q = 60/(1/2+1/5)
    exacta = 80-q*m.coordenadas()[0]/2
    np.testing.assert_allclose(r.T,exacta,atol=.002,rtol=0)
    assert r.energia_final-r.energia_inicial == pytest.approx(-r.energia_saliente,abs=1e-9)


def test_dos_materiales_resistencias_en_serie():
    n = 20
    k = np.r_[np.full(n//2,2.),np.full(n//2,5.)]
    m = MallaTermica((n,),[1.],k,3.,4.,
                     {(0,0):BC('dirichlet',80.),(0,1):BC('dirichlet',20.)})
    x = m.coordenadas()[0]
    q = 60/(.5/2+.5/5)
    exacta = 80-q*(np.minimum(x,.5)/2+np.maximum(x-.5,0)/5)
    P,_ = m.potencia(exacta)
    np.testing.assert_allclose(P,0.,atol=2e-11)
    for izq,der,G in m.enlaces:
        np.testing.assert_allclose(G*(exacta[izq]-exacta[der]),q,atol=1e-11)
    r = m.resolver(20.,25.)
    np.testing.assert_allclose(r.T,exacta,atol=.002,rtol=0)


def test_balance_combinado_bordes_fuente_esquinas():
    m = MallaTermica((5,7,4),[1.,2.,.7],2.,3.,4.,
                     {(0,0):BC('dirichlet',40.),(1,1):BC('robin',10.,6.),
                      (2,0):BC('neumann',-3.)})
    r = m.resolver(20.,.2,fuente=17.)
    assert r.energia_final-r.energia_inicial == pytest.approx(
        r.energia_fuente-r.energia_saliente,abs=1e-10)


def test_estabilidad_y_validaciones():
    m = MallaTermica((10,8),[1.,2.],2.,3.,4.)
    assert m.dt_max == pytest.approx(1/(2*(2/12)*sum(1/m.dx**2)))
    robin = MallaTermica((10,),[1.],2.,3.,4.,{(0,0):BC('robin',20.,100.)})
    aislado = MallaTermica((10,),[1.],2.,3.,4.)
    assert robin.dt_max < aislado.dt_max
    with pytest.raises(ValueError,match='inestable'):
        m.resolver(20.,1.,dt=m.dt_max*1.01)
    for dato in (-1.,np.nan,np.inf):
        with pytest.raises(ValueError):
            MallaTermica((5,),[1.],dato,3.,4.)
    with pytest.raises(ValueError):
        m.resolver(np.nan,1.)
    with pytest.raises(ValueError):
        m.resolver(20.,1.,fuente=np.inf)
    with pytest.raises(ValueError):
        MallaTermica((5,),[1.],2.,3.,4.,{(2,0):BC('neumann')})
