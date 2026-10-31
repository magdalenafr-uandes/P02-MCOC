"""Simulación térmica por etapas de vertida sobre una grilla voxelizada.

Recibe todo ya resuelto (grilla, plan de vertidas, materiales, ambiente): no
lee YAML ni IFC y no contiene parámetros del caso. Cambiar Δx, el inicio o la
temperatura de colocación de una vertida es cambiar la configuración, no este
módulo.

Modelo (balance de voxel, ``voxel.py``)::

    C_i dT_i/dt = sum_j G_ij (T_j - T_i) + (qdot_h,i + qdot_ext,i) V

- Conducción interna: ``SolverVoxel`` (media armónica en interfaces).
- ``qdot_h``: hidratación, función de la edad equivalente y de T (``hidratacion.py``).
- ``qdot_ext``: intercambio por las caras expuestas, como el Robin del motor:
  ``G = 1/((Δx/2)/(kA) + R/A + 1/(hA))`` hacia el ambiente, más la base de la
  caja (Dirichlet a ``T_base`` o adiabática). Las caras de la caja son
  adiabáticas en el motor; todo intercambio externo pasa por este término.
  Con ``DominioVoxel.peso_area``, A pasa a ser el área real ``w·A`` (la
  escalera sobrestima ~30 % el área de caras inclinadas).

Etapas: los instantes de inicio de cada vertida y de retiro de moldaje cortan
el tiempo en etapas. Al comenzar una etapa se activan las vertidas que
corresponden: sus voxeles pasan de vacío a hormigón a ``T_colocacion`` con
edad equivalente 0, y se recalculan conductancias y caras expuestas. Un voxel
aún no vertido es **vacío**: conductividad despreciable y temperatura del
aire; no participa como hormigón (guía G04).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np

from ..bim.voxelizador import area_cara, caras_expuestas, pasos
from .hidratacion import CERO_ABSOLUTO_C, ModeloHidratacion
from .voxel import MallaVoxel, SolverVoxel, adiabatico

_K_VACIO_RELATIVO = 1e-9  # k del vacío / k mínima del sólido (aislamiento numérico)


@dataclass(frozen=True)
class Material:
    k: float  # W/(m·K)
    rho: float  # kg/m³
    cp: float  # J/(kg·K)

    def __post_init__(self) -> None:
        for nombre in ("k", "rho", "cp"):
            valor = getattr(self, nombre)
            if not math.isfinite(valor) or valor <= 0.0:
                raise ValueError(f"{nombre} debe ser positivo y finito.")


@dataclass(frozen=True)
class Hormigon:
    material: Material
    hidratacion: ModeloHidratacion | None = None


@dataclass(frozen=True)
class PlanVertida:
    """Parámetros de una vertida ya resueltos (config externa > IFC)."""

    vertida_id: int
    inicio_s: float
    T_colocacion_C: float
    hormigon: str
    visible: bool = True
    R_lateral: float = 0.0  # m²K/W, moldaje/aislación en caras laterales e inferiores
    R_superior: float = 0.0  # m²K/W, aislación de la cara superior
    retiro_moldaje_s: float = math.inf  # tras inicio + retiro, R_lateral -> 0
    nombre: str = ""
    origen: Mapping[str, str] = field(default_factory=dict, compare=False)  # trazabilidad

    def __post_init__(self) -> None:
        if not math.isfinite(self.inicio_s) or self.inicio_s < 0.0:
            raise ValueError(f"Vertida {self.vertida_id}: inicio no negativo y finito.")
        if not math.isfinite(self.T_colocacion_C):
            raise ValueError(f"Vertida {self.vertida_id}: T_colocacion finita.")
        if min(self.R_lateral, self.R_superior) < 0.0:
            raise ValueError(f"Vertida {self.vertida_id}: resistencias no negativas.")
        if not self.retiro_moldaje_s > 0.0:
            raise ValueError(f"Vertida {self.vertida_id}: retiro de moldaje positivo.")


SIGMA = 5.670374419e-8  # Stefan-Boltzmann [W/(m²·K⁴)]


@dataclass(frozen=True)
class Ambiente:
    """Intercambio de las caras expuestas con el exterior.

    Temperatura **sol-aire**: cada cara ve un ambiente equivalente

        h_tot = h_c + h_r
        T_eq  = (h_c·T_aire + h_r·T_rad + α·G·f) / h_tot

    - h_c: convección, constante (``h``) o ``a + b·v`` con el viento v [m/s].
    - h_r = 4·ε·σ·T_m³: onda larga linealizada hacia T_rad. La cara superior ve
      el cielo, T_cielo = 0,0552·T_aire^1,5 [K] (Swinbank); las laterales ven
      mitad cielo y mitad entorno: T_rad = (T_cielo + T_aire)/2.
    - α·G·f: radiación solar absorbida; f = 1 en la cara superior,
      ``factor_solar_lateral`` en las laterales y 0 en las inferiores.

    La radiación se absorbe y emite en la cara exterior (moldaje o aislación);
    después atraviesa R y la media celda como el resto del flujo. Series en
    segundos desde el inicio de la simulación, interpoladas linealmente.
    """

    T_C: float
    h: float  # W/(m²·K) si no hay modelo de viento; 0 y sin radiación = adiabático
    serie_t_s: tuple[float, ...] = ()
    serie_T_C: tuple[float, ...] = ()
    serie_viento_m_s: tuple[float, ...] = ()
    serie_G_W_m2: tuple[float, ...] = ()
    h_viento: tuple[float, float] | None = None  # (a, b): h_c = a + b·v
    absortividad: float = 0.0
    emisividad: float = 0.0
    factor_solar_lateral: float = 0.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.T_C) or not math.isfinite(self.h) or self.h < 0.0:
            raise ValueError("Ambiente: T finita y h >= 0.")
        n = len(self.serie_t_s)
        if len(self.serie_T_C) != n:
            raise ValueError("Ambiente: la serie necesita igual número de tiempos y temperaturas.")
        for nombre in ("serie_viento_m_s", "serie_G_W_m2"):
            serie = getattr(self, nombre)
            if serie and len(serie) != n:
                raise ValueError(f"Ambiente: {nombre} debe tener un valor por tiempo de la serie.")
            if serie and (not np.all(np.isfinite(serie)) or min(serie) < 0.0):
                raise ValueError(f"Ambiente: {nombre} finita y no negativa.")
        if self.serie_t_s and np.any(np.diff(self.serie_t_s) <= 0.0):
            raise ValueError("Ambiente: tiempos de la serie estrictamente crecientes.")
        if self.h_viento is not None:
            if not self.serie_viento_m_s:
                raise ValueError("Ambiente: h dependiente del viento requiere la serie de viento.")
            if min(self.h_viento) < 0.0 or not all(map(math.isfinite, self.h_viento)):
                raise ValueError("Ambiente: coeficientes de viento finitos y no negativos.")
        if self.absortividad > 0.0 and not self.serie_G_W_m2:
            raise ValueError("Ambiente: absortividad > 0 requiere la serie de radiación solar.")
        for nombre in ("absortividad", "emisividad", "factor_solar_lateral"):
            if not 0.0 <= getattr(self, nombre) <= 1.0:
                raise ValueError(f"Ambiente: {nombre} en [0, 1].")

    def _serie(self, t: float, serie: tuple[float, ...]) -> float:
        return float(np.interp(t, self.serie_t_s, serie))

    def temperatura(self, t: float) -> float:
        if not self.serie_t_s:
            return self.T_C
        return self._serie(t, self.serie_T_C)

    def h_conveccion(self, t: float) -> float:
        if self.h_viento is None:
            return self.h
        a, b = self.h_viento
        return a + b * self._serie(t, self.serie_viento_m_s)

    def condiciones(self, t: float) -> tuple[float, dict[str, float]]:
        """(h_tot, T_eq por orientación 'superior' | 'lateral' | 'inferior')."""
        T_a = self.temperatura(t)
        h_c = self.h_conveccion(t)
        G = self._serie(t, self.serie_G_W_m2) if self.serie_G_W_m2 else 0.0
        h_r = 0.0
        T_cielo = T_a
        if self.emisividad > 0.0:
            T_a_K = T_a - CERO_ABSOLUTO_C
            T_cielo = 0.0552 * T_a_K**1.5 + CERO_ABSOLUTO_C
            T_m_K = 0.5 * (T_a + T_cielo) - CERO_ABSOLUTO_C
            h_r = 4.0 * self.emisividad * SIGMA * T_m_K**3
        h_tot = h_c + h_r
        if h_tot <= 0.0:
            return 0.0, {"superior": T_a, "lateral": T_a, "inferior": T_a}
        solar = self.absortividad * G
        T_rad = {"superior": T_cielo, "lateral": 0.5 * (T_cielo + T_a), "inferior": T_a}
        f = {"superior": 1.0, "lateral": self.factor_solar_lateral, "inferior": 0.0}
        return h_tot, {o: (h_c * T_a + h_r * T_rad[o] + solar * f[o]) / h_tot for o in T_rad}

    @property
    def sin_intercambio(self) -> bool:
        """Caras expuestas adiabáticas: sin convección ni radiación."""
        return self.h == 0.0 and self.h_viento is None and self.emisividad == 0.0 and self.absortividad == 0.0

    def h_max(self, t0: float, t1: float) -> float:
        """Máximo de h_tot en [t0, t1] (para el paso estable)."""
        instantes = [t0, t1] + [t for t in self.serie_t_s if t0 < t < t1]
        return max(self.condiciones(t)[0] for t in instantes)


def orientacion(cara: str) -> str:
    return {"z+": "superior", "z-": "inferior"}.get(cara, "lateral")


@dataclass(frozen=True)
class CondicionBase:
    """Cara inferior de la caja (bajo el suelo, o bajo el hormigón si no hay suelo)."""

    tipo: str  # "dirichlet" | "adiabatico"
    T_C: float = math.nan

    def __post_init__(self) -> None:
        if self.tipo not in ("dirichlet", "adiabatico"):
            raise ValueError("Base: tipo 'dirichlet' o 'adiabatico'.")
        if self.tipo == "dirichlet" and not math.isfinite(self.T_C):
            raise ValueError("Base Dirichlet necesita T_C finita.")


@dataclass(frozen=True)
class ParametrosTiempo:
    duracion_s: float
    fraccion_dt: float = 0.8  # dt = fraccion · límite monótono
    dt_max_s: float = math.inf  # tope por precisión (cinética de hidratación)
    guardar_cada_s: float = 3600.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.duracion_s) or self.duracion_s <= 0.0:
            raise ValueError("duracion positiva y finita.")
        if not 0.0 < self.fraccion_dt <= 1.0:
            raise ValueError("fraccion_dt en (0, 1].")
        if not self.dt_max_s > 0.0 or not self.guardar_cada_s > 0.0:
            raise ValueError("dt_max y guardar_cada positivos.")


@dataclass(frozen=True)
class DominioVoxel:
    """Lo único que el simulador necesita de la voxelización."""

    vertida_id: np.ndarray  # (nx, ny, nz) int, 0 = sin hormigón
    es_suelo: np.ndarray  # (nx, ny, nz) bool
    paso: float | tuple[float, float, float]  # escalar (cúbico) o (Δx, Δy, Δz) [m]
    # w = A_real/A_staircase por cara ("x-"... "z+"); None = área staircase (w = 1)
    peso_area: Mapping[str, np.ndarray] | None = None

    @property
    def pasos(self) -> tuple[float, float, float]:
        return pasos(self.paso)


@dataclass
class ResultadoEtapas:
    tiempos_s: list[float] = field(default_factory=list)
    T_max_C: list[float] = field(default_factory=list)  # hormigón activo
    T_min_C: list[float] = field(default_factory=list)  # hormigón activo
    T_sup_min_C: list[float] = field(default_factory=list)  # hormigón expuesto, a la profundidad del criterio
    T_max_vertida_C: dict[int, list[float]] = field(default_factory=dict)  # nan si inactiva
    T_sup_min_vertida_C: dict[int, list[float]] = field(default_factory=dict)  # nan sin cara expuesta
    etapas: list[dict] = field(default_factory=list)
    balance: dict[str, float] = field(default_factory=dict)
    T_final: np.ndarray | None = None
    edad_equivalente_final_s: np.ndarray | None = None
    activo_final: np.ndarray | None = None
    campos: dict[float, np.ndarray] = field(default_factory=dict)

    @property
    def delta_T_C(self) -> np.ndarray:
        """T_max - T_sup_min: diferencial núcleo-superficie.

        T_sup es la temperatura a ``profundidad_superficie_m`` bajo la cara del
        sólido (0 = la cara misma, antes de moldaje o aislación), interpolada
        entre la cara y el centro del voxel superficial, que está Δ/2 adentro.
        """
        return np.asarray(self.T_max_C) - np.asarray(self.T_sup_min_C)

    def delta_T_vertida_C(self, vid: int) -> np.ndarray:
        """Diferencial núcleo-superficie **dentro de una vertida**: su T máxima
        menos la T mínima de sus propias caras expuestas.

        Es el criterio de la misma pieza. El global (``delta_T_C``) compara el
        núcleo de una vertida con la superficie de otra, p. ej. hormigón recién
        colocado a T de colocación junto a una vertida antigua caliente: es una
        cota conservadora, no un diferencial de sección.
        """
        return np.asarray(self.T_max_vertida_C[vid]) - np.asarray(self.T_sup_min_vertida_C[vid])

    def delta_T_max_por_vertida(self) -> tuple[float, int, float]:
        """(ΔT máx [°C], vertida, tiempo [s]) del diferencial dentro de cada vertida."""
        mejor = (math.nan, 0, math.nan)
        for vid in self.T_max_vertida_C:
            serie = self.delta_T_vertida_C(vid)
            if np.all(np.isnan(serie)):
                continue
            i = int(np.nanargmax(serie))
            if math.isnan(mejor[0]) or serie[i] > mejor[0]:
                mejor = (float(serie[i]), vid, self.tiempos_s[i])
        return mejor

    def pico(self, vid: int) -> tuple[float, float]:
        """(T_max [°C], tiempo del pico [s]) de una vertida."""
        serie = np.asarray(self.T_max_vertida_C[vid], dtype=float)
        if np.all(np.isnan(serie)):
            return math.nan, math.nan
        i = int(np.nanargmax(serie))
        return float(serie[i]), self.tiempos_s[i]


@dataclass(frozen=True)
class _CaraExpuesta:
    """Caras de una dirección expuestas al aire en una etapa (índices planos)."""

    cara: str
    orientacion: str  # superior | lateral | inferior
    idx: np.ndarray
    area: np.ndarray  # A·w [m²]
    media_m: float  # Δ/2 normal a la cara [m]
    r_media: np.ndarray  # (Δ/2)/k [m²K/W]
    R: np.ndarray  # moldaje o aislación [m²K/W]
    hormigon: np.ndarray  # bool: la celda es hormigón activo (no suelo)

    def conductancia(self, h_tot: float) -> np.ndarray:
        """G = A/(r_media + R + 1/h) [W/K]: resistencias en serie."""
        if h_tot <= 0.0:
            return np.zeros(self.idx.shape)
        return self.area / (self.r_media + self.R + 1.0 / h_tot)


class SimuladorEtapas:
    """Integra las etapas de vertida con el motor ``SolverVoxel``."""

    def __init__(
        self,
        dominio: DominioVoxel,
        plan: Sequence[PlanVertida],
        hormigones: Mapping[str, Hormigon],
        ambiente: Ambiente,
        base: CondicionBase,
        tiempo: ParametrosTiempo,
        suelo: Material | None = None,
        T_suelo_inicial_C: float | None = None,
        guardar_campos: bool = False,
        profundidad_superficie_m: float = 0.0,
    ) -> None:
        if not math.isfinite(profundidad_superficie_m) or profundidad_superficie_m < 0.0:
            raise ValueError("profundidad_superficie_m no negativa y finita.")
        self.profundidad_superficie_m = profundidad_superficie_m
        self.dominio = dominio
        self.plan = {p.vertida_id: p for p in plan}
        if len(self.plan) != len(plan):
            raise ValueError("vertida_id repetido en el plan.")
        ids_grilla = {int(v) for v in np.unique(dominio.vertida_id) if v != 0}
        faltan = ids_grilla - set(self.plan)
        if faltan:
            raise ValueError(f"Vertidas en la grilla sin plan: {sorted(faltan)}.")
        for p in plan:
            if p.hormigon not in hormigones:
                raise ValueError(f"Vertida {p.vertida_id}: hormigón {p.hormigon!r} no definido.")
        if np.any(dominio.es_suelo):
            if suelo is None or T_suelo_inicial_C is None or not math.isfinite(T_suelo_inicial_C):
                raise ValueError("La grilla tiene suelo: definir su material y T inicial.")
        self.hormigones = dict(hormigones)
        self.ambiente = ambiente
        self.base = base
        self.tiempo = tiempo
        self.suelo = suelo
        self.T_suelo_inicial_C = T_suelo_inicial_C
        self.guardar_campos = guardar_campos
        self._q = np.zeros(dominio.vertida_id.shape)

    # --- eventos -----------------------------------------------------------
    def eventos(self) -> list[float]:
        """Cortes de etapa: 0, inicios, retiros de moldaje y fin."""
        T = self.tiempo.duracion_s
        cortes = {0.0, T}
        for p in self.plan.values():
            if not p.visible:
                continue
            if p.inicio_s < T:
                cortes.add(p.inicio_s)
            fin_moldaje = p.inicio_s + p.retiro_moldaje_s
            if fin_moldaje < T:
                cortes.add(fin_moldaje)
        return sorted(cortes)

    # --- propiedades por etapa ----------------------------------------------
    def _propiedades(self, activo: np.ndarray, solido: np.ndarray):
        forma = activo.shape
        k = np.empty(forma)
        rho = np.ones(forma)
        cp = np.ones(forma)
        ids = self.dominio.vertida_id
        k_solidos = []
        if self.suelo is not None and np.any(self.dominio.es_suelo):
            s = self.dominio.es_suelo
            k[s], rho[s], cp[s] = self.suelo.k, self.suelo.rho, self.suelo.cp
            k_solidos.append(self.suelo.k)
        for vid, p in self.plan.items():
            m = activo & (ids == vid)
            if m.any():
                mat = self.hormigones[p.hormigon].material
                k[m], rho[m], cp[m] = mat.k, mat.rho, mat.cp
                k_solidos.append(mat.k)
        k_ref = min(k_solidos) if k_solidos else 1.0
        k[~solido] = _K_VACIO_RELATIVO * k_ref
        return k, rho, cp

    def _caras_etapa(self, t: float, activo: np.ndarray, solido: np.ndarray, k: np.ndarray) -> list[_CaraExpuesta]:
        """Caras expuestas al aire en esta etapa, como índices planos (dispersos).

        Por cara: r_media = (Δ/2)/k (media celda de sólido) y R (moldaje o
        aislación) [m²K/W]; la película 1/h se agrega en cada paso porque h
        cambia con el viento y la radiación.
        """
        if self.ambiente.sin_intercambio:
            return []
        d = self.dominio.pasos
        ids = self.dominio.vertida_id
        R_lat = np.zeros(activo.shape)
        R_sup = np.zeros(activo.shape)
        for vid, p in self.plan.items():
            m = activo & (ids == vid)
            if m.any():
                R_lat[m] = p.R_lateral if t < p.inicio_s + p.retiro_moldaje_s else 0.0
                R_sup[m] = p.R_superior
        caras = []
        for cara, mascara in caras_expuestas(solido).items():
            idx = np.flatnonzero(mascara)
            if not idx.size:
                continue
            eje = "xyz".index(cara[0])
            A = area_cara(d, eje)
            if self.dominio.peso_area is not None:
                A = A * self.dominio.peso_area[cara].ravel()[idx]  # A_real = w·A
            caras.append(_CaraExpuesta(
                cara=cara,
                orientacion=orientacion(cara),
                idx=idx,
                area=np.broadcast_to(A, idx.shape),
                media_m=d[eje] / 2.0,
                r_media=(d[eje] / 2.0) / k.ravel()[idx],
                R=(R_sup if cara == "z+" else R_lat).ravel()[idx],
                hormigon=activo.ravel()[idx],
            ))
        return caras

    def _conductancias_externas(self, t: float, activo: np.ndarray, solido: np.ndarray, k: np.ndarray,
                                h_tot: float | None = None):
        """G hacia el exterior (densa, a h_tot o al h de t) y G de la base [W/K]."""
        d = self.dominio.pasos
        if h_tot is None:
            h_tot = self.ambiente.condiciones(t)[0]
        G_amb = np.zeros(activo.size)
        if h_tot > 0.0:
            for c in self._caras_etapa(t, activo, solido, k):
                G_amb[c.idx] += c.conductancia(h_tot)
        G_base = np.zeros(activo.shape)
        if self.base.tipo == "dirichlet":
            capa = solido[:, :, 0]
            G_base[:, :, 0] = np.where(capa, k[:, :, 0] * area_cara(d, 2) / (d[2] / 2.0), 0.0)
        return G_amb.reshape(activo.shape), G_base

    # --- integración ----------------------------------------------------------
    def ejecutar(self) -> ResultadoEtapas:
        dom = self.dominio
        forma = dom.vertida_id.shape
        d = dom.pasos
        V = float(np.prod(d))
        ids = dom.vertida_id
        res = ResultadoEtapas(T_max_vertida_C={vid: [] for vid in sorted(self.plan)})

        activo = np.zeros(forma, dtype=bool)  # hormigón activo
        T = np.full(forma, self.ambiente.temperatura(0.0))
        if np.any(dom.es_suelo):
            T[dom.es_suelo] = self.T_suelo_inicial_C
        te = np.zeros(forma)
        activadas: set[int] = set()

        E = dict.fromkeys(("colocacion", "hidratacion", "ambiente", "base", "fuga_vacio"), 0.0)
        E_inicial = None
        proximo_guardado = 0.0
        cortes = self.eventos()
        t = 0.0

        for t0, t1 in zip(cortes[:-1], cortes[1:]):
            # activar vertidas que comienzan en esta etapa
            nuevas = [
                vid for vid, p in self.plan.items()
                if p.visible and vid not in activadas and p.inicio_s <= t0 and np.any(ids == vid)
            ]
            for vid in nuevas:
                m = ids == vid
                activo |= m
                T[m] = self.plan[vid].T_colocacion_C
                te[m] = 0.0
                activadas.add(vid)
            solido = activo | dom.es_suelo
            k, rho, cp = self._propiedades(activo, solido)
            C = rho * cp * V
            if E_inicial is None:
                E_inicial = float(np.sum((C * T)[solido & ~activo]))  # suelo inicial
            for vid in nuevas:
                m = ids == vid
                E["colocacion"] += float(np.sum(C[m] * T[m]))

            malla = MallaVoxel(forma, d, k, rho, cp)
            solver = SolverVoxel(malla, {c: adiabatico() for c in malla.caras}, lambda _t: self._q)
            caras = self._caras_etapa(t0, activo, solido, k)
            h_max = self.ambiente.h_max(t0, t1) if caras else 0.0
            G_amb_max = np.zeros(T.size)
            for c in caras:
                G_amb_max[c.idx] += c.conductancia(h_max)
            _, G_base = self._conductancias_externas(t0, activo, solido, k, h_tot=0.0)
            grupos = []
            for nombre, h in self.hormigones.items():
                if h.hidratacion is None:
                    continue
                vids = [vid for vid, p in self.plan.items() if p.hormigon == nombre]
                m = activo & np.isin(ids, vids)
                if m.any():
                    grupos.append((m, h.hidratacion))

            if solido.any():
                G_ext = G_amb_max.reshape(forma) + G_base  # h máximo de la etapa: paso estable siempre
                limite = float(np.min((C / (solver.suma_G + G_ext))[solido]))
            else:
                limite = math.inf
            dt_obj = min(self.tiempo.fraccion_dt * limite, self.tiempo.dt_max_s, t1 - t0)
            n_pasos = max(1, int(math.ceil((t1 - t0) / dt_obj - 1e-9)))
            dt = (t1 - t0) / n_pasos
            res.etapas.append({
                "t0_s": t0, "t1_s": t1, "activas": sorted(activadas), "nuevas": nuevas,
                "dt_s": dt, "dt_limite_s": limite, "pasos": n_pasos,
            })

            vacio = ~solido
            T_base = self.base.T_C if self.base.tipo == "dirichlet" else 0.0
            for paso in range(n_pasos):
                t = t0 + paso * dt
                if t >= proximo_guardado - 1e-9:
                    self._registrar(res, t, T, activo, caras, ids)
                    while proximo_guardado <= t + 1e-9:
                        proximo_guardado += self.tiempo.guardar_cada_s
                q_h = np.zeros(forma)
                for m, modelo in grupos:
                    q_h[m] = modelo.potencia(te[m], T[m])
                P_amb = np.zeros(T.size)
                h_tot, T_eq = self.ambiente.condiciones(t) if caras else (0.0, {})
                if h_tot > 0.0:
                    T_plano = T.ravel()
                    for c in caras:  # idx único dentro de cada dirección
                        P_amb[c.idx] += c.conductancia(h_tot) * (T_eq[c.orientacion] - T_plano[c.idx])
                P_amb = P_amb.reshape(forma)
                P_base = G_base * (T_base - T)
                self._q = q_h + (P_amb + P_base) / V
                T_nuevo = T + dt * solver.tasa_calor(T, t) / C
                E["hidratacion"] += dt * float(np.sum(q_h)) * V
                E["ambiente"] += dt * float(np.sum(P_amb))
                E["base"] += dt * float(np.sum(P_base))
                E["fuga_vacio"] += float(np.sum((C * (T_nuevo - T))[vacio]))
                for m, modelo in grupos:
                    te[m] += dt * modelo.factor_arrhenius(T[m])
                T = T_nuevo
                T[vacio] = self.ambiente.temperatura(t + dt)
            t = t1

        self._registrar(res, t, T, activo, caras, ids)
        solido = activo | dom.es_suelo
        E_final = float(np.sum((C * T)[solido]))
        aportes = E["colocacion"] + E["hidratacion"] + E["ambiente"] + E["base"] - E["fuga_vacio"]
        res.balance = {
            "E_inicial_J": E_inicial or 0.0,
            "E_final_J": E_final,
            **{f"{k}_J": v for k, v in E.items()},
            "residuo_J": E_final - (E_inicial or 0.0) - aportes,
        }
        res.T_final = T
        res.edad_equivalente_final_s = te
        res.activo_final = activo
        return res

    def _registrar(self, res, t, T, activo, caras, ids) -> None:
        if res.tiempos_s and abs(res.tiempos_s[-1] - t) < 1e-9:
            return
        res.tiempos_s.append(t)
        if activo.any():
            Ta = T[activo]
            res.T_max_C.append(float(Ta.max()))
            res.T_min_C.append(float(Ta.min()))
            # Cara del sólido: el mismo flujo cruza la media celda y el exterior en
            # serie, así que Ts = Ti + phi·(T_eq - Ti), phi = r_media/(r_media + R + 1/h).
            # A la profundidad p del criterio, el perfil entre la cara y el centro
            # (a Δ/2) es lineal: T(p) = Ts + (Ti - Ts)·min(p/(Δ/2), 1).
            h_tot, T_eq = self.ambiente.condiciones(t)
            sup_vertida = np.full(int(ids.max()) + 1, np.inf)
            if h_tot > 0.0:
                T_plano = T.ravel()
                ids_plano = ids.ravel()
                for c in caras:
                    if c.hormigon.any():
                        Ti = T_plano[c.idx][c.hormigon]
                        phi = c.r_media[c.hormigon] / (c.r_media[c.hormigon] + c.R[c.hormigon] + 1.0 / h_tot)
                        hacia_cara = 1.0 - min(self.profundidad_superficie_m / c.media_m, 1.0)
                        Ts = Ti + phi * hacia_cara * (T_eq[c.orientacion] - Ti)
                        np.minimum.at(sup_vertida, ids_plano[c.idx][c.hormigon], Ts)
            minimo = float(sup_vertida.min())
            res.T_sup_min_C.append(minimo if math.isfinite(minimo) else math.nan)
        else:
            res.T_max_C.append(math.nan)
            res.T_min_C.append(math.nan)
            res.T_sup_min_C.append(math.nan)
            sup_vertida = np.full(int(ids.max()) + 1, np.inf)
        for vid in res.T_max_vertida_C:
            m = activo & (ids == vid)
            res.T_max_vertida_C[vid].append(float(T[m].max()) if m.any() else math.nan)
            s = sup_vertida[vid] if vid < len(sup_vertida) else np.inf
            res.T_sup_min_vertida_C.setdefault(vid, []).append(float(s) if math.isfinite(s) else math.nan)
        if self.guardar_campos:
            res.campos[t] = T.copy()
