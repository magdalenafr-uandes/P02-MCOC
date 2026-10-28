"""Solver térmico 2D/3D por balance de voxel (volumen finito cartesiano).

Cada celda (voxel) ``i`` cumple el balance de energía

    C_i dT_i/dt = sum_j G_ij (T_j - T_i) + qdot_i V_i + Q_borde,i

con

    C_i  = rho_i cp_i V_i                 capacidad térmica        [J/K]
    G_ij = k_ij A_ij / d_ij               conductancia entre celdas [W/K]
    k_ij = 2 k_i k_j / (k_i + k_j)        media armónica (resistencias en serie)
    qdot_i                                fuente volumétrica       [W/m³]
    Q_borde,i                             calor que entra por el borde [W]

Convención de signos: todo calor que **entra** a la celda es positivo.
Así, ``G (T_j - T_i) > 0`` cuando el vecino está más caliente.

Las temperaturas son de **centro de celda** (malla "cell-centered"); las caras
del dominio están a ``d/2`` del centro de la celda de borde. Esto es lo que
produce una voxelización de una geometría BIM.

Condiciones de borde (por cara del dominio: ``x-``, ``x+``, ``y-``, ``y+``,
``z-``, ``z+``):

- Dirichlet: T de la superficie impuesta, ``Q = G_b (T_b - T_i)`` con
  ``G_b = k A / (d/2)``.
- Neumann: flujo impuesto ``q''`` [W/m²] (positivo entrando),
  ``Q = q'' A``. Adiabático: ``q'' = 0``.
- Robin: convección hacia un fluido a ``T_inf``; resistencias en serie
  (media celda + resistencia extra de moldaje/aislación + película)::

      G_b = 1 / ( (d/2)/(k A) + R''_extra/A + 1/(h A) ),  Q = G_b (T_inf - T_i)

Integración explícita (Euler hacia adelante)::

      T_i^{n+1} = T_i^n + dt/C_i [ sum_j G_ij (T_j^n - T_i^n) + qdot_i V_i + Q_b ]

Monotonía: imponer coeficientes no negativos proporciona un criterio suficiente
conservador de estabilidad. No es necesariamente el máximo límite espectral:

      dt <= dt_max = min_i C_i / (sum_j G_ij + G_b,i).

Para una malla uniforme e isotrópica sin bordes Dirichlet/Robin esto es
``dt <= dx²/(2 d alpha)`` (1/4 en 2D, 1/6 en 3D con Fo = alpha dt/dx²).

Unidades: m, s, °C (diferencias = K), W, J.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from math import isfinite
from typing import Literal, Union

import numpy as np

from .boundaries import PropiedadesTermicas

TipoBordeCara = Literal["dirichlet", "neumann", "robin"]
CARAS_1D = ("x-", "x+")
CARAS_2D = CARAS_1D + ("y-", "y+")
CARAS_3D = CARAS_2D + ("z-", "z+")
_EJE = {"x": 0, "y": 1, "z": 2}

Fuente = Union[float, np.ndarray, Callable[[float], Union[float, np.ndarray]]]


@dataclass(frozen=True)
class BordeCara:
    """Condición de borde aplicada a una cara completa del dominio.

    - ``dirichlet``: ``T`` = temperatura de superficie impuesta [°C].
    - ``neumann``: ``q`` = flujo impuesto [W/m²], positivo **entrando** al
      sólido (por ejemplo radiación solar absorbida). ``q = 0`` es adiabático.
    - ``robin``: ``T`` = temperatura del fluido T_inf [°C], ``h`` = coeficiente
      convectivo [W/(m²·K)], ``R_extra`` = resistencia por unidad de área de
      moldaje/aislación [m²·K/W].
    """

    tipo: TipoBordeCara
    T: float = 0.0
    q: float = 0.0
    h: float = 0.0
    R_extra: float = 0.0

    def __post_init__(self) -> None:
        if self.tipo not in ("dirichlet", "neumann", "robin"):
            raise ValueError(f"Tipo de borde no soportado: {self.tipo!r}.")
        for nombre in ("T", "q", "h", "R_extra"):
            if not isfinite(getattr(self, nombre)):
                raise ValueError(f"{nombre} debe ser finito.")
        if self.tipo == "robin":
            if self.h <= 0.0:
                raise ValueError("Robin requiere h > 0 [W/(m²·K)].")
            if self.R_extra < 0.0:
                raise ValueError("R_extra no puede ser negativa.")


def dirichlet(T: float) -> BordeCara:
    """Temperatura de superficie impuesta [°C]."""
    return BordeCara("dirichlet", T=T)


def neumann(q: float) -> BordeCara:
    """Flujo impuesto [W/m²], positivo entrando al sólido."""
    return BordeCara("neumann", q=q)


def adiabatico() -> BordeCara:
    """Superficie adiabática (simetría o aislación perfecta): q'' = 0."""
    return BordeCara("neumann", q=0.0)


def robin(T_inf: float, h: float, R_extra: float = 0.0) -> BordeCara:
    """Convección a un fluido a ``T_inf`` con coeficiente ``h``."""
    return BordeCara("robin", T=T_inf, h=h, R_extra=R_extra)


@dataclass
class MallaVoxel:
    """Malla cartesiana regular 1D, 2D o 3D con propiedades por celda.

    ``k``, ``rho`` y ``cp`` son arreglos de forma ``forma`` (se permiten
    escalares, que se expanden). Esto permite dos o más materiales.
    """

    forma: tuple[int, ...]
    paso: tuple[float, ...]
    k: np.ndarray
    rho: np.ndarray
    cp: np.ndarray

    def __post_init__(self) -> None:
        if any(isinstance(n, (bool, np.bool_)) or not isinstance(n, (int, np.integer))
               for n in self.forma):
            raise ValueError("El número de celdas debe ser entero.")
        self.forma = tuple(int(n) for n in self.forma)
        self.paso = tuple(float(d) for d in self.paso)
        if len(self.forma) not in (1, 2, 3) or len(self.paso) != len(self.forma):
            raise ValueError("forma y paso deben tener 1, 2 o 3 componentes compatibles.")
        if any(n < 1 for n in self.forma):
            raise ValueError("Cada dimensión debe tener al menos 1 celda.")
        if any(not isfinite(d) or d <= 0.0 for d in self.paso):
            raise ValueError("Los pasos de malla deben ser positivos.")
        for nombre in ("k", "rho", "cp"):
            arr = np.broadcast_to(
                np.asarray(getattr(self, nombre), dtype=float), self.forma
            ).copy()
            if not np.all(np.isfinite(arr)) or np.any(arr <= 0.0):
                raise ValueError(f"{nombre} debe ser positivo y finito en toda celda.")
            setattr(self, nombre, arr)

    # --- constructores -------------------------------------------------
    @classmethod
    def uniforme(
        cls,
        forma: tuple[int, ...],
        paso: tuple[float, ...],
        propiedades: PropiedadesTermicas,
    ) -> "MallaVoxel":
        """Malla de un solo material."""
        return cls(forma, paso, propiedades.k, propiedades.rho, propiedades.cp)

    @classmethod
    def desde_materiales(
        cls,
        paso: tuple[float, ...],
        material_id: np.ndarray,
        materiales: dict[int, PropiedadesTermicas],
    ) -> "MallaVoxel":
        """Malla con varios materiales a partir de un mapa ``material_id``."""
        material_id = np.asarray(material_id)
        faltan = set(np.unique(material_id).tolist()) - set(materiales)
        if faltan:
            raise ValueError(f"material_id sin propiedades: {sorted(faltan)}.")
        k = np.empty(material_id.shape)
        rho = np.empty(material_id.shape)
        cp = np.empty(material_id.shape)
        for mid, props in materiales.items():
            m = material_id == mid
            k[m], rho[m], cp[m] = props.k, props.rho, props.cp
        return cls(material_id.shape, paso, k, rho, cp)

    # --- geometría -----------------------------------------------------
    @property
    def dim(self) -> int:
        return len(self.forma)

    @property
    def caras(self) -> tuple[str, ...]:
        return (CARAS_1D, CARAS_2D, CARAS_3D)[self.dim - 1]

    @property
    def volumen_celda(self) -> float:
        """Volumen de un voxel [m³] (en 2D: m² por metro de profundidad)."""
        return float(np.prod(self.paso))

    def area_cara(self, eje: int) -> float:
        """Área de una cara normal al eje ``eje`` [m²] (2D: por metro)."""
        return float(np.prod([d for i, d in enumerate(self.paso) if i != eje]))

    def centros(self, eje: int) -> np.ndarray:
        """Coordenadas de los centros de celda en el eje ``eje`` [m]."""
        d = self.paso[eje]
        return (np.arange(self.forma[eje]) + 0.5) * d

    def malla_centros(self) -> tuple[np.ndarray, ...]:
        """Coordenadas de centros como arreglos ``meshgrid(indexing='ij')``."""
        return np.meshgrid(
            *[self.centros(e) for e in range(self.dim)], indexing="ij"
        )

    @property
    def capacidad(self) -> np.ndarray:
        """C_i = rho cp V [J/K]."""
        return self.rho * self.cp * self.volumen_celda


def _rebanada(dim: int, eje: int, sl: slice | int) -> tuple:
    s: list = [slice(None)] * dim
    s[eje] = sl
    return tuple(s)


@dataclass
class ResultadoVoxel:
    """Resultado de una integración en el tiempo."""

    T: np.ndarray
    tiempos: list[float]
    energia: list[float]
    calor_borde_acumulado: dict[str, float]
    calor_fuente_acumulado: float
    instantaneas: dict[float, np.ndarray] = field(default_factory=dict)


class SolverVoxel:
    """Integrador explícito del balance de voxel en 1D, 2D o 3D."""

    def __init__(
        self,
        malla: MallaVoxel,
        bordes: dict[str, BordeCara],
        fuente: Fuente = 0.0,
    ) -> None:
        faltan = set(malla.caras) - set(bordes)
        sobran = set(bordes) - set(malla.caras)
        if faltan or sobran:
            raise ValueError(
                "Debe definirse exactamente una condición por cara "
                f"{malla.caras}; faltan {sorted(faltan)}, sobran {sorted(sobran)}."
            )
        self.malla = malla
        self.bordes = dict(bordes)
        if not all(isinstance(b, BordeCara) for b in self.bordes.values()):
            raise ValueError("Cada borde debe ser BordeCara.")
        self.fuente = fuente
        self._preparar_conductancias()

    # --- conductancias -------------------------------------------------
    def _preparar_conductancias(self) -> None:
        m = self.malla
        self.G_int: list[np.ndarray] = []
        suma_G = np.zeros(m.forma)
        for eje in range(m.dim):
            A = m.area_cara(eje)
            d = m.paso[eje]
            k_a = m.k[_rebanada(m.dim, eje, slice(None, -1))]
            k_b = m.k[_rebanada(m.dim, eje, slice(1, None))]
            k_cara = 2.0 * k_a * k_b / (k_a + k_b)  # media armónica
            G = k_cara * A / d
            self.G_int.append(G)
            suma_G[_rebanada(m.dim, eje, slice(None, -1))] += G
            suma_G[_rebanada(m.dim, eje, slice(1, None))] += G

        self.G_borde: dict[str, np.ndarray | None] = {}
        for cara in m.caras:
            eje = _EJE[cara[0]]
            idx = 0 if cara[1] == "-" else -1
            borde = self.bordes[cara]
            A = m.area_cara(eje)
            media = m.paso[eje] / 2.0
            k_b = m.k[_rebanada(m.dim, eje, idx)]
            if borde.tipo == "dirichlet":
                G = k_b * A / media
            elif borde.tipo == "robin":
                G = 1.0 / (
                    media / (k_b * A) + borde.R_extra / A + 1.0 / (borde.h * A)
                )
            else:
                G = None
            self.G_borde[cara] = G
            if G is not None:
                suma_G[_rebanada(m.dim, eje, idx)] += G
        self.suma_G = suma_G

    def dt_max(self) -> float:
        """Límite suficiente de monotonía: min_i C_i / sum G_i [s].

        Se conserva el nombre por compatibilidad; no es el límite espectral exacto.
        """
        with np.errstate(divide="ignore"):
            cociente = np.where(
                self.suma_G > 0.0, self.malla.capacidad / self.suma_G, np.inf
            )
        return float(np.min(cociente))

    # --- balance -------------------------------------------------------
    def _fuente_en(self, t: float) -> np.ndarray:
        q = self.fuente(t) if callable(self.fuente) else self.fuente
        q = np.broadcast_to(np.asarray(q, dtype=float), self.malla.forma)
        if not np.all(np.isfinite(q)):
            raise ValueError("La fuente volumétrica contiene valores no finitos.")
        return q

    def calor_borde(self, T: np.ndarray) -> dict[str, float]:
        """Calor neto que entra por cada cara [W] (positivo = entra)."""
        return {c: float(np.sum(q)) for c, q in self._flujos_borde(T).items()}

    def temperatura_superficie(self, T: np.ndarray) -> dict[str, np.ndarray]:
        """Temperatura de la cara del sólido, distinta del centro vecino.

        Q es positivo entrando: Ts = Ti + (Q/A)*d/(2k).
        En Robin con aislación, Ts es la superficie del sólido antes de R_extra.
        """
        m = self.malla
        T = np.broadcast_to(np.asarray(T, dtype=float), m.forma)
        if not np.all(np.isfinite(T)):
            raise ValueError("T contiene valores no finitos.")
        flujos = self._flujos_borde(T)
        resultado = {}
        for cara in m.caras:
            eje = _EJE[cara[0]]
            sl = _rebanada(m.dim, eje, 0 if cara[1] == "-" else -1)
            bc = self.bordes[cara]
            if bc.tipo == "dirichlet":
                resultado[cara] = np.full_like(T[sl], bc.T)
            else:
                resultado[cara] = T[sl] + flujos[cara] * m.paso[eje] / (2*m.k[sl]*m.area_cara(eje))
        return resultado

    def _flujos_borde(self, T: np.ndarray) -> dict[str, np.ndarray]:
        m = self.malla
        salida = {}
        for cara in m.caras:
            eje = _EJE[cara[0]]
            idx = 0 if cara[1] == "-" else -1
            borde = self.bordes[cara]
            T_b = T[_rebanada(m.dim, eje, idx)]
            if borde.tipo == "neumann":
                salida[cara] = np.full(T_b.shape, borde.q * m.area_cara(eje))
            else:
                salida[cara] = self.G_borde[cara] * (borde.T - T_b)
        return salida

    def tasa_calor(self, T: np.ndarray, t: float = 0.0) -> np.ndarray:
        """Lado derecho del balance de cada voxel: C_i dT_i/dt [W]."""
        T = np.broadcast_to(np.asarray(T, dtype=float), self.malla.forma)
        if not np.all(np.isfinite(T)):
            raise ValueError("T contiene valores no finitos.")
        return self._balance(T, self._fuente_en(t), self._flujos_borde(T))

    def _balance(self, T, fuente, flujos_borde):
        """Balance con fuente y bordes ya evaluados en el mismo instante."""
        m = self.malla
        Q = np.zeros(m.forma)
        for eje, G in enumerate(self.G_int):
            if G.size == 0:
                continue
            a = _rebanada(m.dim, eje, slice(None, -1))
            b = _rebanada(m.dim, eje, slice(1, None))
            flujo = G * (T[b] - T[a])  # calor que va de la celda b a la a
            Q[a] += flujo
            Q[b] -= flujo
        for cara, q in flujos_borde.items():
            eje = _EJE[cara[0]]
            idx = 0 if cara[1] == "-" else -1
            Q[_rebanada(m.dim, eje, idx)] += q
        Q += fuente * m.volumen_celda
        return Q

    def energia(self, T: np.ndarray) -> float:
        """Energía térmica relativa a 0 °C: sum C_i T_i [J]."""
        return float(np.sum(self.malla.capacidad * T))

    # --- integración ---------------------------------------------------
    def resolver(
        self,
        T_inicial: np.ndarray | float,
        dt: float,
        n_pasos: int,
        t0: float = 0.0,
        guardar_cada: int | None = None,
        verificar_estabilidad: bool = True,
    ) -> ResultadoVoxel:
        """Integra ``n_pasos`` pasos de tamaño ``dt`` [s] con Euler explícito.

        ``verificar_estabilidad=False`` permite demostrar la inestabilidad
        (solo con fines didácticos).
        """
        m = self.malla
        T = np.broadcast_to(np.asarray(T_inicial, dtype=float), m.forma).copy()
        if not np.all(np.isfinite(T)):
            raise ValueError("T_inicial contiene valores no finitos.")
        if not isfinite(dt) or dt <= 0.0:
            raise ValueError("dt debe ser positivo.")
        if isinstance(n_pasos, (bool, np.bool_)) or not isinstance(n_pasos, (int, np.integer)) or n_pasos < 0:
            raise ValueError("n_pasos debe ser un entero no negativo.")
        if not isfinite(t0):
            raise ValueError("t0 debe ser finito.")
        if guardar_cada is not None and (isinstance(guardar_cada, bool) or
                not isinstance(guardar_cada, (int, np.integer)) or guardar_cada <= 0):
            raise ValueError("guardar_cada debe ser un entero positivo.")
        dt_lim = self.dt_max()
        if verificar_estabilidad and dt > dt_lim * (1.0 + 1e-12):
            raise ValueError(
                f"Paso temporal inestable según criterio conservador: dt={dt:.6e} s > dt_max={dt_lim:.6e} s."
            )

        C = m.capacidad
        t = t0
        tiempos = [t]
        energia = [self.energia(T)]
        acumulado = {c: 0.0 for c in m.caras}
        fuente_acum = 0.0
        instantaneas = {t: T.copy()} if guardar_cada else {}

        for paso in range(1, n_pasos + 1):
            flujos_b = self._flujos_borde(T)
            fuente = self._fuente_en(t)
            Q = self._balance(T, fuente, flujos_b)
            for c, q in flujos_b.items():
                acumulado[c] += dt * float(np.sum(q))
            fuente_acum += dt * float(np.sum(fuente)) * m.volumen_celda
            T = T + dt * Q / C
            t = t0 + paso * dt
            tiempos.append(t)
            energia.append(self.energia(T))
            if guardar_cada and paso % guardar_cada == 0:
                instantaneas[t] = T.copy()

        return ResultadoVoxel(
            T=T,
            tiempos=tiempos,
            energia=energia,
            calor_borde_acumulado=acumulado,
            calor_fuente_acumulado=fuente_acum,
            instantaneas=instantaneas,
        )
