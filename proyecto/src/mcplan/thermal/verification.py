"""Casos reproducibles E04/E05; parámetros de verificación, no calibración real."""
import numpy as np
from .boundaries import CondicionBorde
from .solver_nd import MallaTermica


def sinusoidal(dim=2, n=16, longitudes=None, tiempo=21600., k=2.22,
               rho=2400., cp=970., amplitud=50., base=20., seguridad=0.6, dt=None):
    longitudes = tuple(longitudes or [1.]*dim)
    bordes = {(a,s): CondicionBorde('dirichlet',base) for a in range(dim) for s in (0,1)}
    m = MallaTermica((n,)*dim,longitudes,k,rho,cp,bordes)
    perfil = np.ones(m.forma)
    for X,L in zip(m.coordenadas(),longitudes):
        perfil *= np.sin(np.pi*X/L)
    exacta = base + amplitud*perfil*np.exp(-k/(rho*cp)*sum((np.pi/L)**2 for L in longitudes)*tiempo)
    r = m.resolver(base+amplitud*perfil,tiempo,seguridad=seguridad,dt=dt)
    return m,r,exacta
