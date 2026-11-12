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
from .bordes import (  # noqa: F401  (Ambiente, CondicionBase y SIGMA se reexportan)
    SIGMA,
    Ambiente,
    CapaProteccion,
    CondicionBase,
    orientacion,
    resistencia_proteccion,
)
from .hidratacion import ModeloHidratacion
from .tuberias import Tuberia
from .voxel import MallaVoxel, SolverVoxel, adiabatico

# [MAPA:vacio] voxel aún no vertido: k despreciable, T del aire
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
    R_lateral: float = 0.0  # m²K/W, moldaje en caras laterales e inferiores hasta el retiro
    R_superior: float = 0.0  # m²K/W, protección permanente de la cara superior
    retiro_moldaje_s: float = math.inf  # tras inicio + retiro, R_lateral -> 0
    nombre: str = ""
    origen: Mapping[str, str] = field(default_factory=dict, compare=False)  # trazabilidad
    capas: tuple[CapaProteccion, ...] = ()  # aislación u otras capas con su propio período

    def __post_init__(self) -> None:
        if not math.isfinite(self.inicio_s) or self.inicio_s < 0.0:
            raise ValueError(f"Vertida {self.vertida_id}: inicio no negativo y finito.")
        if not math.isfinite(self.T_colocacion_C):
            raise ValueError(f"Vertida {self.vertida_id}: T_colocacion finita.")
        if min(self.R_lateral, self.R_superior) < 0.0:
            raise ValueError(f"Vertida {self.vertida_id}: resistencias no negativas.")
        if not self.retiro_moldaje_s > 0.0:
            raise ValueError(f"Vertida {self.vertida_id}: retiro de moldaje positivo.")

    def capas_efectivas(self) -> tuple[CapaProteccion, ...]:
        """Moldaje (R_lateral hasta el retiro), protección superior permanente y capas extra."""
        base = []
        if self.R_lateral > 0.0:
            base.append(CapaProteccion("moldaje", self.R_lateral, frozenset({"lateral", "inferior"}),
                                       0.0, self.retiro_moldaje_s))
        if self.R_superior > 0.0:
            base.append(CapaProteccion("superior", self.R_superior, frozenset({"superior"})))
        return (*base, *self.capas)

    def resistencia(self, t_s: float, orientacion_cara: str) -> float:
        """R de protección [m²K/W] de esta vertida en el instante absoluto ``t_s``."""
        return resistencia_proteccion(self.capas_efectivas(), t_s - self.inicio_s, orientacion_cara)


@dataclass(frozen=True)
class ParametrosTiempo:
    duracion_s: float
    fraccion_dt: float = 0.8  # dt = fraccion · límite monótono
    dt_max_s: float = math.inf  # tope por precisión (cinética de hidratación)
    guardar_cada_s: float = 3600.0
    # tope de elevación adiabática liberada por paso [K]: resuelve la cinética cuando Arrhenius la acelera
    dtheta_max_K: float = math.inf

    def __post_init__(self) -> None:
        if not math.isfinite(self.duracion_s) or self.duracion_s <= 0.0:
            raise ValueError("duracion positiva y finita.")
        if not 0.0 < self.fraccion_dt <= 1.0:
            raise ValueError("fraccion_dt en (0, 1].")
        if not self.dt_max_s > 0.0 or not self.guardar_cada_s > 0.0:
            raise ValueError("dt_max y guardar_cada positivos.")
        if not self.dtheta_max_K > 0.0:
            raise ValueError("dtheta_max_K positivo.")


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
    potencia_tuberias_W: list[float] = field(default_factory=list)  # extraída por el agua en cada registro
    energia_por_tuberia_J: dict[str, float] = field(default_factory=dict)
    T_sup_min_vertida_C: dict[int, list[float]] = field(default_factory=dict)  # nan sin cara expuesta
    # [MAPA:ubicacion-maximos] dónde ocurre cada máximo: índice plano de la celda (-1 = no hay) y cara
    idx_max_vertida: dict[int, list[int]] = field(default_factory=dict)  # celda más caliente de la vertida
    idx_sup_vertida: dict[int, list[int]] = field(default_factory=dict)  # celda bajo la cara más fría
    cara_sup_vertida: dict[int, list[str]] = field(default_factory=dict)  # 'x-' ... 'z+' de esa cara
    etapas: list[dict] = field(default_factory=list)
    balance: dict[str, float] = field(default_factory=dict)
    advertencias: list[str] = field(default_factory=list)
    T_final: np.ndarray | None = None
    edad_equivalente_final_s: np.ndarray | None = None
    activo_final: np.ndarray | None = None
    campos: dict[float, np.ndarray] = field(default_factory=dict)

    @property
    # [MAPA:criterio-deltaT] diferencial núcleo - superficie (criterio 20 °C)
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

    # [MAPA:robin-caso] cara expuesta: media celda + moldaje/aislación + película 1/h
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
        campos_cada_s: float | None = None,
        progreso=None,
        tuberias: Sequence[Tuberia] = (),
    ) -> None:
        if campos_cada_s is not None and not campos_cada_s > 0.0:
            raise ValueError("campos_cada_s debe ser positivo.")
        self.tuberias = tuple(tuberias)
        for tub in self.tuberias:
            if tub.vertida_id not in {p.vertida_id for p in plan}:
                raise ValueError(f"Tubería {tub.nombre}: la vertida {tub.vertida_id} no está en el plan.")
        self._P_tub_W = 0.0  # potencia extraída en el último paso (para el registro)
        self.campos_cada_s = campos_cada_s  # None: un campo por registro
        self.progreso = progreso
        self._proximo_campo = 0.0
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

    # --- coherencia constructiva -------------------------------------------
    def advertencias_apoyo(self) -> list[str]:
        """Vertidas que quedarían sin apoyo: la de abajo está oculta o se vierte después.

        No detiene la simulación (ocultar o reordenar vertidas es parte del
        laboratorio), pero el plan resultante no es construible tal cual.
        """
        ids = self.dominio.vertida_id
        abajo = np.zeros_like(ids)
        abajo[:, :, 1:] = ids[:, :, :-1]
        avisos = []
        for vid, p in sorted(self.plan.items()):
            if not p.visible:
                continue
            base_propia = (ids == vid) & (abajo != vid)
            for soporte in sorted(int(s) for s in np.unique(abajo[base_propia]) if s not in (0, vid)):
                q = self.plan.get(soporte)
                if q is None:
                    continue
                if not q.visible:
                    avisos.append(f"Vertida {vid} se apoya en la vertida {soporte}, que está oculta.")
                elif q.inicio_s > p.inicio_s:
                    avisos.append(
                        f"Vertida {vid} (inicio {p.inicio_s / 3600:g} h) se apoya en la vertida {soporte}, "
                        f"que se vierte después ({q.inicio_s / 3600:g} h): queda sin apoyo."
                    )
        return avisos

    # --- eventos -----------------------------------------------------------
    def eventos(self) -> list[float]:
        """Cortes de etapa: 0, inicios, colocación y retiro de cada capa (desmolde) y fin."""
        T = self.tiempo.duracion_s
        cortes = {0.0, T}
        for p in self.plan.values():
            if not p.visible:
                continue
            if p.inicio_s < T:
                cortes.add(p.inicio_s)
            for capa in p.capas_efectivas():
                for borde in (capa.desde_s, capa.hasta_s):
                    t = p.inicio_s + borde
                    if 0.0 < t < T:
                        cortes.add(t)
        for tub in self.tuberias:  # encendido y apagado de cada circuito
            p = self.plan[tub.vertida_id]
            if p.visible:
                for borde in (tub.desde_s, tub.hasta_s):
                    t = p.inicio_s + borde
                    if 0.0 < t < T:
                        cortes.add(t)
        return sorted(cortes)

    def _tuberias_etapa(self, t: float, activo: np.ndarray):
        """(G total por celda [W/K], Σ G·T_agua por celda, circuitos activos) en esta etapa."""
        G = np.zeros(activo.size)
        GT = np.zeros(activo.size)
        activos = []
        plano = activo.ravel()
        for tub in self.tuberias:
            p = self.plan[tub.vertida_id]
            if p.visible and tub.activa(t, p.inicio_s) and plano[tub.idx].all():
                np.add.at(G, tub.idx, tub.G)
                np.add.at(GT, tub.idx, tub.G * tub.T_agua_C)
                activos.append(tub)
        return G, GT, activos

    # --- propiedades por etapa ----------------------------------------------
    # [MAPA:propiedades-por-voxel] k, rho, cp de hormigón, suelo y vacío en cada etapa
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
        R_por_orientacion = {o: np.zeros(activo.shape) for o in ("superior", "lateral", "inferior")}
        for vid, p in self.plan.items():
            m = activo & (ids == vid)
            if m.any():
                for o, R in R_por_orientacion.items():
                    R[m] = p.resistencia(t, o)  # moldaje/aislación activos en esta etapa
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
                R=R_por_orientacion[orientacion(cara)].ravel()[idx],
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
        # [MAPA:base-suelo] cara inferior de la caja: Dirichlet T_base o adiabática
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
        res.advertencias = self.advertencias_apoyo()

        activo = np.zeros(forma, dtype=bool)  # hormigón activo
        T = np.full(forma, self.ambiente.temperatura(0.0))
        if np.any(dom.es_suelo):
            T[dom.es_suelo] = self.T_suelo_inicial_C
        te = np.zeros(forma)
        activadas: set[int] = set()

        # [MAPA:balance-energia] contabilidad de energía: colocación, hidratación, ambiente, base
        E = dict.fromkeys(("colocacion", "hidratacion", "ambiente", "base", "fuga_vacio", "tuberias"), 0.0)
        res.energia_por_tuberia_J = {tub.nombre: 0.0 for tub in self.tuberias}
        E_inicial = None
        proximo_guardado = 0.0
        cortes = self.eventos()
        t = 0.0

        for t0, t1 in zip(cortes[:-1], cortes[1:]):
            # [MAPA:activacion-vertidas] vacío -> hormigón a T_colocacion, edad 0
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
            self._registrar(res, t0, T, activo, caras, ids, forzar_campo=True)
            h_max = self.ambiente.h_max(t0, t1) if caras else 0.0
            G_amb_max = np.zeros(T.size)
            for c in caras:
                G_amb_max[c.idx] += c.conductancia(h_max)
            _, G_base = self._conductancias_externas(t0, activo, solido, k, h_tot=0.0)
            G_tub, GT_tub, tubos_activos = self._tuberias_etapa(t0, activo)
            grupos = []
            for nombre, h in self.hormigones.items():
                if h.hidratacion is None:
                    continue
                vids = [vid for vid, p in self.plan.items() if p.hormigon == nombre]
                m = activo & np.isin(ids, vids)
                if m.any():
                    grupos.append((m, h.hidratacion))

            if solido.any():
                # h máximo de la etapa y tuberías activas: paso estable siempre
                G_ext = G_amb_max.reshape(forma) + G_base + G_tub.reshape(forma)
                limite = float(np.min((C / (solver.suma_G + G_ext))[solido]))
            else:
                limite = math.inf
            # [MAPA:estabilidad-caso] dt = fraccion_dt · C/ΣG con el h máximo de la etapa
            dt_obj = min(self.tiempo.fraccion_dt * limite, self.tiempo.dt_max_s, t1 - t0)
            n_pasos = max(1, int(math.ceil((t1 - t0) / dt_obj - 1e-9)))
            dt = (t1 - t0) / n_pasos
            res.etapas.append({
                "t0_s": t0, "t1_s": t1, "activas": sorted(activadas), "nuevas": nuevas,
                "dt_s": dt, "dt_limite_s": limite, "pasos": n_pasos,
            })

            vacio = ~solido
            T_base = self.base.T_C if self.base.tipo == "dirichlet" else 0.0
            dt_etapa = dt
            pasos_reales = 0
            t = t0
            while t < t1 - 1e-9:
                if t >= proximo_guardado - 1e-9:
                    self._registrar(res, t, T, activo, caras, ids)
                    while proximo_guardado <= t + 1e-9:
                        proximo_guardado += self.tiempo.guardar_cada_s
                # Los registros y campos se guardan en el instante pedido,
                # no en el primer paso posterior (importante al comparar planes).
                dt = min(dt_etapa, t1-t, proximo_guardado-t)
                if self.guardar_campos and self.campos_cada_s is not None and self._proximo_campo > t+1e-9:
                    dt = min(dt, self._proximo_campo-t)
                # [MAPA:paso-hidratacion] ningún voxel libera más de dtheta_max_K en un paso: con Arrhenius
                # (hormigón fresco sobre una vertida caliente) la curva entera podría caber en un solo paso
                if math.isfinite(self.tiempo.dtheta_max_K) and grupos:
                    tasa = max(float(np.max(modelo.tasa_elevacion(te[m]) * modelo.factor_arrhenius(T[m])))
                               for m, modelo in grupos)
                    if tasa > 0.0:
                        dt = min(dt, self.tiempo.dtheta_max_K / tasa)
                if dt <= 0 or t+dt <= t:
                    raise ValueError('Paso temporal demasiado pequeño para avanzar.')
                q_h = np.zeros(forma)
                te_fin = []
                for m, modelo in grupos:
                    # [MAPA:hidratacion-fuente] q''' de hidratación en cada voxel activo (acotado por θ∞)
                    q_h[m], te_nueva = modelo.calor_en_paso(te[m], T[m], dt)
                    te_fin.append((m, te_nueva))
                P_amb = np.zeros(T.size)
                h_tot, T_eq = self.ambiente.condiciones(t) if caras else (0.0, {})
                if h_tot > 0.0:
                    T_plano = T.ravel()
                    for c in caras:  # idx único dentro de cada dirección
                        # [MAPA:flujo-ambiente] Q = G (T_eq - T_cara) en caras expuestas
                        P_amb[c.idx] += c.conductancia(h_tot) * (T_eq[c.orientacion] - T_plano[c.idx])
                P_amb = P_amb.reshape(forma)
                P_base = G_base * (T_base - T)
                # [MAPA:tuberia-energia] calor que el agua extrae: Σ G (T_celda − T_agua); varía con T
                P_tub = (G_tub * T.ravel() - GT_tub).reshape(forma)
                self._q = q_h + (P_amb + P_base - P_tub) / V
                T_nuevo = T + dt * solver.tasa_calor(T, t) / C
                E["hidratacion"] += dt * float(np.sum(q_h)) * V
                E["ambiente"] += dt * float(np.sum(P_amb))
                E["base"] += dt * float(np.sum(P_base))
                self._P_tub_W = float(np.sum(P_tub))
                E["tuberias"] += dt * self._P_tub_W
                T_plano = T.ravel()
                for tub in tubos_activos:
                    res.energia_por_tuberia_J[tub.nombre] += dt * float(np.sum(tub.G * (T_plano[tub.idx] - tub.T_agua_C)))
                E["fuga_vacio"] += float(np.sum((C * (T_nuevo - T))[vacio]))
                for m, te_nueva in te_fin:
                    # [MAPA:edad-equivalente] madurez: la hidratación se acelera con T (Arrhenius)
                    te[m] = te_nueva
                T = T_nuevo
                T[vacio] = self.ambiente.temperatura(t + dt)
                t += dt
                pasos_reales += 1
                if self.guardar_campos and self.campos_cada_s is not None and t < t1-1e-9 and t >= self._proximo_campo-1e-9:
                    self._registrar(res, t, T, activo, caras, ids)
            t = t1
            res.etapas[-1]['pasos'] = pasos_reales

        # Un evento en el extremo final también incorpora material y energía.
        nuevas_final = [vid for vid,p in self.plan.items() if p.visible and vid not in activadas
                        and p.inicio_s <= t and np.any(ids == vid)]
        for vid in nuevas_final:
            m = ids == vid
            activo |= m
            T[m] = self.plan[vid].T_colocacion_C
            te[m] = 0.0
            mat = self.hormigones[self.plan[vid].hormigon].material
            C[m] = mat.rho*mat.cp*V
            E['colocacion'] += float(np.sum(C[m]*T[m]))
            activadas.add(vid)
        if nuevas_final:
            solido = activo | dom.es_suelo
            k, _, _ = self._propiedades(activo, solido)
            caras = self._caras_etapa(t, activo, solido, k)
            res.etapas.append(dict(t0_s=t,t1_s=t,activas=sorted(activadas),nuevas=nuevas_final,
                                   dt_s=0.,dt_limite_s=math.inf,pasos=0))
        self._registrar(res, t, T, activo, caras, ids)
        solido = activo | dom.es_suelo
        E_final = float(np.sum((C * T)[solido]))
        aportes = (E["colocacion"] + E["hidratacion"] + E["ambiente"] + E["base"] - E["fuga_vacio"]
                   - E["tuberias"])
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

    def _registrar(self, res, t, T, activo, caras, ids, forzar_campo=False) -> None:
        if res.tiempos_s and abs(res.tiempos_s[-1] - t) < 1e-9:
            return
        res.tiempos_s.append(t)
        res.potencia_tuberias_W.append(self._P_tub_W)
        if activo.any():
            Ta = T[activo]
            res.T_max_C.append(float(Ta.max()))
            res.T_min_C.append(float(Ta.min()))
            # Cara del sólido: el mismo flujo cruza la media celda y el exterior en
            # serie, así que Ts = Ti + phi·(T_eq - Ti), phi = r_media/(r_media + R + 1/h).
            # [MAPA:superficie-25mm] T 'superficial' a profundidad_superficie_m bajo la cara
            # A la profundidad p del criterio, el perfil entre la cara y el centro
            # (a Δ/2) es lineal: T(p) = Ts + (Ti - Ts)·min(p/(Δ/2), 1).
            h_tot, T_eq = self.ambiente.condiciones(t)
            sup_vertida = np.full(int(ids.max()) + 1, np.inf)
            sup_idx = np.full(sup_vertida.shape, -1, dtype=np.int64)
            sup_cara = [""] * len(sup_vertida)
            if h_tot > 0.0:
                T_plano = T.ravel()
                ids_plano = ids.ravel()
                for c in caras:
                    if c.hormigon.any():
                        Ti = T_plano[c.idx][c.hormigon]
                        phi = c.r_media[c.hormigon] / (c.r_media[c.hormigon] + c.R[c.hormigon] + 1.0 / h_tot)
                        hacia_cara = 1.0 - min(self.profundidad_superficie_m / c.media_m, 1.0)
                        Ts = Ti + phi * hacia_cara * (T_eq[c.orientacion] - Ti)
                        celdas = c.idx[c.hormigon]
                        vids = ids_plano[celdas]
                        for vid in np.unique(vids):  # ubicación del mínimo de esta cara en cada vertida
                            m = vids == vid
                            j = int(np.argmin(Ts[m]))
                            if Ts[m][j] < sup_vertida[vid]:
                                sup_vertida[vid], sup_idx[vid], sup_cara[vid] = Ts[m][j], celdas[m][j], c.cara
            minimo = float(sup_vertida.min())
            res.T_sup_min_C.append(minimo if math.isfinite(minimo) else math.nan)
        else:
            res.T_max_C.append(math.nan)
            res.T_min_C.append(math.nan)
            res.T_sup_min_C.append(math.nan)
            sup_vertida = np.full(int(ids.max()) + 1, np.inf)
            sup_idx = np.full(sup_vertida.shape, -1, dtype=np.int64)
            sup_cara = [""] * len(sup_vertida)
        for vid in res.T_max_vertida_C:
            m = activo & (ids == vid)
            if m.any():
                celdas = np.flatnonzero(m)
                j = int(np.argmax(T.ravel()[celdas]))
                res.T_max_vertida_C[vid].append(float(T.ravel()[celdas[j]]))
                res.idx_max_vertida.setdefault(vid, []).append(int(celdas[j]))
            else:
                res.T_max_vertida_C[vid].append(math.nan)
                res.idx_max_vertida.setdefault(vid, []).append(-1)
            dentro = vid < len(sup_vertida)
            s = sup_vertida[vid] if dentro else np.inf
            res.T_sup_min_vertida_C.setdefault(vid, []).append(float(s) if math.isfinite(s) else math.nan)
            res.idx_sup_vertida.setdefault(vid, []).append(int(sup_idx[vid]) if dentro and math.isfinite(s) else -1)
            res.cara_sup_vertida.setdefault(vid, []).append(sup_cara[vid] if dentro and math.isfinite(s) else "")
        if self.guardar_campos:
            final = t >= self.tiempo.duracion_s - 1e-9
            if self.campos_cada_s is None or t >= self._proximo_campo - 1e-9 or final or forzar_campo:
                res.campos[t] = T.astype(np.float32)  # campos 3D: float32 basta y usa la mitad de memoria
                while self.campos_cada_s is not None and self._proximo_campo <= t + 1e-9:
                    self._proximo_campo += self.campos_cada_s
        if self.progreso is not None:
            self.progreso(t, self.tiempo.duracion_s)
