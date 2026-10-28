"""Adaptador de la API local al único motor SolverVoxel del equipo.

Esta API conserva Neumann SALIENTE positivo y caras (eje, lado).
El motor voxel.py usa Neumann ENTRANTE positivo y caras x-/x+/...;
la traducción se hace aquí una sola vez. No hay otro bucle de integración.
"""
from dataclasses import dataclass
import numpy as np
from .boundaries import CondicionBorde
from .voxel import MallaVoxel, SolverVoxel, adiabatico, dirichlet, neumann, robin


@dataclass
class ResultadoND:
    T: np.ndarray
    tiempo: float
    pasos: int
    dt: float
    dt_max: float
    energia_inicial: float
    energia_final: float
    energia_fuente: float
    energia_saliente: float


class MallaTermica:
    """Compatibilidad de las demostraciones locales con el motor del equipo."""
    def __init__(self, forma, longitudes, k, rho, cp, bordes=None):
        self.forma = tuple(forma)
        self.longitudes = tuple(longitudes)
        if not 1 <= len(self.forma) <= 3 or len(self.longitudes) != len(self.forma):
            raise ValueError('Se requieren 1 a 3 dimensiones compatibles.')
        if any(isinstance(n, bool) or not isinstance(n, (int,np.integer)) or n < 2 for n in self.forma):
            raise ValueError('Cada eje necesita al menos dos celdas enteras.')
        if any(not np.isfinite(L) or L <= 0 for L in self.longitudes):
            raise ValueError('Longitudes positivas y finitas.')
        self.dx = np.array(self.longitudes)/self.forma
        self.volumen = float(np.prod(self.dx))
        self.bordes = dict(bordes or {})
        validas = {(a,s) for a in range(len(self.forma)) for s in (0,1)}
        if set(self.bordes)-validas:
            raise ValueError('Cara desconocida: usar (eje, lado), lado 0 o 1.')
        m = MallaVoxel(self.forma,tuple(self.dx),k,rho,cp)
        self.k,self.capacidad = m.k,m.capacidad
        bc_motor = {}
        for a,s in validas:
            bc = self.bordes.get((a,s),CondicionBorde('neumann'))
            if not isinstance(bc,CondicionBorde):
                raise ValueError('Borde debe ser CondicionBorde.')
            if bc.tipo == 'dirichlet':
                convertido = dirichlet(bc.valor)
            elif bc.tipo == 'neumann':
                convertido = neumann(-bc.valor)
            else:
                convertido = robin(bc.valor,bc.h) if bc.h > 0 else adiabatico()
            bc_motor['xyz'[a]+('-' if s == 0 else '+')] = convertido
        self._solver = SolverVoxel(m,bc_motor)
        self.dt_max = self._solver.dt_max()
        # Acceso de diagnóstico a los enlaces del motor; no recalcula conductancias.
        self.enlaces = []
        for a,G in enumerate(self._solver.G_int):
            izq,der = [slice(None)]*len(self.forma),[slice(None)]*len(self.forma)
            izq[a],der[a] = slice(None,-1),slice(1,None)
            self.enlaces.append((tuple(izq),tuple(der),G))

    def campo(self, valor, positivo=False):
        try:
            out = np.broadcast_to(np.asarray(valor,dtype=float),self.forma).copy()
        except ValueError as exc:
            raise ValueError('Campo incompatible con la malla.') from exc
        if not np.all(np.isfinite(out)) or (positivo and np.any(out <= 0)):
            raise ValueError('Campos finitos; propiedades estrictamente positivas.')
        return out

    def coordenadas(self):
        return self._solver.malla.malla_centros()

    def energia(self,T,referencia=0.):
        return self._solver.energia(self.campo(T)-referencia)

    def potencia(self,T,fuente=0.):
        # Nueva instancia comparte la malla pero evita mutar la fuente de otra corrida.
        solver = SolverVoxel(self._solver.malla,self._solver.bordes,self.campo(fuente))
        T = self.campo(T)
        return solver.tasa_calor(T),-sum(solver.calor_borde(T).values())

    def resolver(self,inicial,tiempo,fuente=0.,dt=None,seguridad=.8):
        if not np.isfinite(tiempo) or tiempo < 0:
            raise ValueError('Tiempo finito no negativo.')
        if not np.isfinite(seguridad) or not 0 < seguridad <= 1:
            raise ValueError('Seguridad debe estar en (0,1].')
        solicitado = seguridad*self.dt_max if dt is None else dt
        if not np.isfinite(solicitado) or solicitado <= 0:
            raise ValueError('dt positivo y finito.')
        if solicitado > self.dt_max*(1+1e-12):
            raise ValueError(f'Paso inestable según criterio conservador: dt={solicitado:g}, dt_max={self.dt_max:g} s')
        pasos = int(np.ceil(tiempo/solicitado))
        efectivo = tiempo/pasos if pasos else solicitado
        solver = SolverVoxel(self._solver.malla,self._solver.bordes,self.campo(fuente))
        r = solver.resolver(self.campo(inicial),efectivo,pasos)
        return ResultadoND(r.T,tiempo,pasos,efectivo if pasos else 0.,self.dt_max,
                           r.energia[0],r.energia[-1],r.calor_fuente_acumulado,
                           -sum(r.calor_borde_acumulado.values()))
