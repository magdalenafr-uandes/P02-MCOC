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

from ..bim.voxelizador import caras_expuestas
from .hidratacion import ModeloHidratacion
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


@dataclass(frozen=True)
class Ambiente:
    """Aire exterior: T constante o serie (t [s], T [°C]) interpolada linealmente."""

    T_C: float
    h: float  # W/(m²·K); 0 = caras expuestas adiabáticas
    serie_t_s: tuple[float, ...] = ()
    serie_T_C: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if not math.isfinite(self.T_C) or not math.isfinite(self.h) or self.h < 0.0:
            raise ValueError("Ambiente: T finita y h >= 0.")
        if len(self.serie_t_s) != len(self.serie_T_C):
            raise ValueError("Ambiente: la serie necesita igual número de tiempos y temperaturas.")
        if self.serie_t_s and np.any(np.diff(self.serie_t_s) <= 0.0):
            raise ValueError("Ambiente: tiempos de la serie estrictamente crecientes.")

    def temperatura(self, t: float) -> float:
        if not self.serie_t_s:
            return self.T_C
        return float(np.interp(t, self.serie_t_s, self.serie_T_C))


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
    paso: float
    # w = A_real/A_staircase por cara ("x-"... "z+"); None = área staircase (w = 1)
    peso_area: Mapping[str, np.ndarray] | None = None


@dataclass
class ResultadoEtapas:
    tiempos_s: list[float] = field(default_factory=list)
    T_max_C: list[float] = field(default_factory=list)  # hormigón activo
    T_min_C: list[float] = field(default_factory=list)  # hormigón activo
    T_sup_min_C: list[float] = field(default_factory=list)  # voxeles con cara expuesta
    T_max_vertida_C: dict[int, list[float]] = field(default_factory=dict)  # nan si inactiva
    etapas: list[dict] = field(default_factory=list)
    balance: dict[str, float] = field(default_factory=dict)
    T_final: np.ndarray | None = None
    edad_equivalente_final_s: np.ndarray | None = None
    activo_final: np.ndarray | None = None
    campos: dict[float, np.ndarray] = field(default_factory=dict)

    @property
    def delta_T_C(self) -> np.ndarray:
        """T_max - T_sup_min: diferencial núcleo-superficie (centros de celda)."""
        return np.asarray(self.T_max_C) - np.asarray(self.T_sup_min_C)

    def pico(self, vid: int) -> tuple[float, float]:
        """(T_max [°C], tiempo del pico [s]) de una vertida."""
        serie = np.asarray(self.T_max_vertida_C[vid], dtype=float)
        if np.all(np.isnan(serie)):
            return math.nan, math.nan
        i = int(np.nanargmax(serie))
        return float(serie[i]), self.tiempos_s[i]


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
    ) -> None:
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

    def _conductancias_externas(self, t: float, activo: np.ndarray, solido: np.ndarray, k: np.ndarray):
        d = self.dominio.paso
        A = d * d
        ids = self.dominio.vertida_id
        R_lat = np.zeros(activo.shape)
        R_sup = np.zeros(activo.shape)
        for vid, p in self.plan.items():
            m = activo & (ids == vid)
            if m.any():
                R_lat[m] = p.R_lateral if t < p.inicio_s + p.retiro_moldaje_s else 0.0
                R_sup[m] = p.R_superior
        G_amb = np.zeros(activo.shape)
        if self.ambiente.h > 0.0:
            expuestas = caras_expuestas(solido)
            for cara, mascara in expuestas.items():
                R = R_sup if cara == "z+" else R_lat
                G = 1.0 / ((d / 2.0) / (k * A) + R / A + 1.0 / (self.ambiente.h * A))
                if self.dominio.peso_area is not None:
                    G = G * self.dominio.peso_area[cara]  # A_real = w·A en las tres resistencias
                G_amb += np.where(mascara, G, 0.0)
        G_base = np.zeros(activo.shape)
        if self.base.tipo == "dirichlet":
            capa = solido[:, :, 0]
            G_base[:, :, 0] = np.where(capa, k[:, :, 0] * A / (d / 2.0), 0.0)
        return G_amb, G_base

    # --- integración ----------------------------------------------------------
    def ejecutar(self) -> ResultadoEtapas:
        dom = self.dominio
        forma = dom.vertida_id.shape
        d = dom.paso
        V = d**3
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

            malla = MallaVoxel(forma, (d, d, d), k, rho, cp)
            solver = SolverVoxel(malla, {c: adiabatico() for c in malla.caras}, lambda _t: self._q)
            G_amb, G_base = self._conductancias_externas(t0, activo, solido, k)
            expuesto = G_amb > 0.0
            grupos = []
            for nombre, h in self.hormigones.items():
                if h.hidratacion is None:
                    continue
                vids = [vid for vid, p in self.plan.items() if p.hormigon == nombre]
                m = activo & np.isin(ids, vids)
                if m.any():
                    grupos.append((m, h.hidratacion))

            if solido.any():
                limite = float(np.min((C / (solver.suma_G + G_amb + G_base))[solido]))
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
                    self._registrar(res, t, T, activo, expuesto, ids)
                    while proximo_guardado <= t + 1e-9:
                        proximo_guardado += self.tiempo.guardar_cada_s
                T_amb = self.ambiente.temperatura(t)
                q_h = np.zeros(forma)
                for m, modelo in grupos:
                    q_h[m] = modelo.potencia(te[m], T[m])
                P_amb = G_amb * (T_amb - T)
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

        self._registrar(res, t, T, activo, expuesto, ids)
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

    def _registrar(self, res, t, T, activo, expuesto, ids) -> None:
        if res.tiempos_s and abs(res.tiempos_s[-1] - t) < 1e-9:
            return
        res.tiempos_s.append(t)
        if activo.any():
            Ta = T[activo]
            res.T_max_C.append(float(Ta.max()))
            res.T_min_C.append(float(Ta.min()))
            sup = activo & expuesto
            res.T_sup_min_C.append(float(T[sup].min()) if sup.any() else math.nan)
        else:
            res.T_max_C.append(math.nan)
            res.T_min_C.append(math.nan)
            res.T_sup_min_C.append(math.nan)
        for vid in res.T_max_vertida_C:
            m = activo & (ids == vid)
            res.T_max_vertida_C[vid].append(float(T[m].max()) if m.any() else math.nan)
        if self.guardar_campos:
            res.campos[t] = T.copy()
