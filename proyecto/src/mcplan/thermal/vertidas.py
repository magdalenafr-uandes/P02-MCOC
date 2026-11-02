"""Balance 3D con dominio activo y eventos de colocación.

Mismo balance por caras que SolverVoxel, especializado en grillas IFC con
vacíos. Material homogéneo; contacto perfecto entre vertidas activas.
Todas las caras expuestas usan un Robin uniforme (h=0: adiabático).
No representa aún suelo, moldajes ni aislación diferenciados.
"""
from dataclasses import dataclass
import numpy as np

from ..bim.voxelizacion import GrillaVertidas
from ..bim.voxel_ifc import SolidoIFC, caras_expuestas
from .boundaries import PropiedadesTermicas
from .hidratacion import HidratacionAdiabatica


@dataclass
class EstadoVertidas:
    tiempo_s: float
    T: np.ndarray  # NaN fuera del hormigón activo
    activos: np.ndarray
    edad_s: np.ndarray  # NaN fuera del hormigón activo
    energia_J: float
    hidratacion_J: float
    borde_J: float
    colocacion_J: float  # energía incorporada, referencia 0 °C

    @property
    def residuo_energia_J(self) -> float:
        return self.energia_J-self.colocacion_J-self.hidratacion_J-self.borde_J


class SimuladorVertidas:
    def __init__(self, grilla: GrillaVertidas, solidos: list[SolidoIFC], propiedades: PropiedadesTermicas,
                 hidratacion: HidratacionAdiabatica, ambiente_C: float = 20., h: float = 0.):
        if not np.isfinite([ambiente_C, h]).all() or h < 0:
            raise ValueError('Ambiente finito y h no negativo finito.')
        if grilla.vertida_id.ndim != 3 or any(n == 0 for n in grilla.vertida_id.shape) or not np.isfinite(grilla.paso) or grilla.paso <= 0:
            raise ValueError('Se requiere grilla 3D y paso positivo finito.')
        if not np.issubdtype(grilla.vertida_id.dtype, np.integer) or np.any(grilla.vertida_id < 0):
            raise ValueError('vertida_id debe contener enteros no negativos.')
        conocidos = {s.vertida_id for s in solidos}
        presentes = set(np.unique(grilla.vertida_id)) - {0}
        if not conocidos or any(i <= 0 for i in conocidos) or len(conocidos) != len(solidos) or presentes != conocidos:
            raise ValueError('IDs ausentes o duplicados en programación de vertidas.')
        if len({s.tipo_hormigon for s in solidos}) != 1:
            raise ValueError('Este simulador homogéneo requiere el mismo TipoHormigon en todas las vertidas.')
        self.grilla = GrillaVertidas(grilla.vertida_id.copy(), grilla.origen, grilla.paso)
        self.propiedades, self.hidratacion = propiedades, hidratacion
        self.ambiente_C, self.h = ambiente_C, h
        self.inicios = np.full(grilla.vertida_id.shape, np.inf)
        self.colocacion = np.zeros(grilla.vertida_id.shape)
        for s in solidos:
            if not np.isfinite([s.inicio_s, s.temperatura_C]).all() or s.inicio_s < 0:
                raise ValueError('Programación de vertida inválida.')
            m = grilla.vertida_id == s.vertida_id
            self.inicios[m], self.colocacion[m] = s.inicio_s, s.temperatura_C
        self.eventos = sorted({s.inicio_s for s in solidos})
        self.t = 0.
        self.T = np.full(grilla.vertida_id.shape, np.nan)
        self.activos = np.zeros(grilla.vertida_id.shape, dtype=bool)
        self.calor_h = self.calor_b = self.calor_col = 0.
        self._activar()

    @property
    def capacidad(self):
        return self.propiedades.rho*self.propiedades.cp*self.grilla.paso**3

    def _activar(self):
        nuevos = (~self.activos) & (self.inicios <= self.t)
        self.T[nuevos] = self.colocacion[nuevos]
        self.calor_col += self.capacidad * float(self.T[nuevos].sum())
        self.activos |= nuevos

    def estado(self) -> EstadoVertidas:
        edades = np.full(self.T.shape, np.nan)
        edades[self.activos] = self.t-self.inicios[self.activos]
        return EstadoVertidas(self.t, self.T.copy(), self.activos.copy(), edades,
                              self.capacidad*float(self.T[self.activos].sum()),
                              self.calor_h, self.calor_b, self.calor_col)

    def avanzar(self, hasta_s: float, dt_s: float) -> EstadoVertidas:
        """Corta pasos en cada evento, en el final y en el límite C/sum(G)."""
        if not np.isfinite([hasta_s, dt_s]).all() or hasta_s < self.t or dt_s <= 0:
            raise ValueError('Final >= tiempo actual y paso positivo, ambos finitos.')
        dx, k = self.grilla.paso, self.propiedades.k
        G = k*dx
        Gb = 0. if self.h == 0 else dx**2/(dx/(2*k) + 1/self.h)
        while self.t < hasta_s:
            self._activar()
            futuro = next((e for e in self.eventos if e > self.t), hasta_s)
            paso = min(dt_s, hasta_s-self.t, futuro-self.t)
            if not self.activos.any():
                self.t += paso
                continue
            expuestas = caras_expuestas(self.grilla.vertida_id, self.activos)
            Q = np.zeros(self.T.shape)
            suma_G = np.zeros(self.T.shape)
            for eje in range(3):
                a, b = [slice(None)]*3, [slice(None)]*3
                a[eje], b[eje] = slice(None, -1), slice(1, None)
                a, b = tuple(a), tuple(b)
                comun = self.activos[a] & self.activos[b]
                flujo = np.zeros(comun.shape)
                flujo[comun] = G*(self.T[b][comun]-self.T[a][comun])
                Q[a] += flujo
                Q[b] -= flujo
                suma_G[a] += G*comun
                suma_G[b] += G*comun
            Qb = np.zeros(self.T.shape)
            for m in expuestas.values():
                Qb[m] += Gb*(self.ambiente_C-self.T[m])
                suma_G[m] += Gb
            positivos = suma_G > 0
            if positivos.any():
                paso = min(paso, .9*self.capacidad/float(suma_G[positivos].max()))
            edad = self.t-self.inicios[self.activos]
            dT_h = self.hidratacion.incremento_paso(edad, paso)
            self.T[self.activos] += paso*(Q[self.activos]+Qb[self.activos])/self.capacidad + dT_h
            self.calor_h += self.capacidad*float(dT_h.sum())
            self.calor_b += paso*float(Qb.sum())
            nuevo_t = self.t + paso
            if nuevo_t <= self.t:
                raise ValueError('Paso demasiado pequeño para representar el avance temporal.')
            self.t = nuevo_t
        self._activar()
        return self.estado()
