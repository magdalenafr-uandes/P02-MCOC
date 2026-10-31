"""Configuración externa del caso (YAML o dict) y su combinación con el IFC.

Regla de diseño: ningún parámetro del caso vive en el solver. Δx, márgenes,
inicio y temperatura de colocación de cada vertida, visibilidad, moldaje,
ambiente, suelo e hidratación se declaran aquí y llegan al simulador como
objetos ya resueltos (``PlanVertida``, ``Hormigon``...).

Prioridad para cada dato de una vertida: ``vertidas.<id>`` > ``vertidas.defecto``
> pset del IFC (``Inicio_h``, ``TemperaturaColocacion_C``, ``TipoHormigon``,
``RetiroMoldaje_h``). Si no está en ninguno, es un error: no se inventan
valores. Cada plan registra de dónde salió cada dato (``origen``).

Las claves desconocidas son error, para que un error de tipeo en el YAML no
se ignore en silencio.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..thermal.etapas import (
    Ambiente,
    CondicionBase,
    Hormigon,
    Material,
    ParametrosTiempo,
    PlanVertida,
)
from ..thermal.hidratacion import HORA, ModeloHidratacion

_ESQUEMA: dict[str, Any] = {
    "ifc": str,
    "malla": {"paso_m": float, "margen_lateral_m": float, "margen_superior_m": float, "corregir_area": bool},
    "simulacion": {
        "duracion_h": float, "fraccion_dt": float, "dt_max_h": float,
        "guardar_cada_h": float, "guardar_campos": bool,
    },
    "ambiente": {"T_C": float, "h_W_m2K": float, "serie": list},
    "base": {"tipo": str, "T_C": float},
    "suelo": {"espesor_m": float, "k_W_mK": float, "rho_kg_m3": float, "cp_J_kgK": float, "T_inicial_C": float},
    "hormigones": dict,
    "vertidas": dict,
}
_HORMIGON = {"k_W_mK": float, "rho_kg_m3": float, "cp_J_kgK": float, "hidratacion": dict}
_HIDRATACION = {"modelo": str, "theta_inf_C": float, "tau_h": float, "beta": float, "Ea_J_mol": float, "T_ref_C": float}
_VERTIDA = {
    "inicio_h": float, "T_colocacion_C": float, "hormigon": str, "visible": bool,
    "R_lateral_m2K_W": float, "R_superior_m2K_W": float, "retiro_moldaje_h": float,
}
_REQUERIDAS = ("ifc", "malla", "simulacion", "ambiente", "base", "hormigones")

# pset del IFC -> campo del plan (solo los que el IFC puede aportar)
_DESDE_IFC = {
    "inicio_h": "Inicio_h",
    "T_colocacion_C": "TemperaturaColocacion_C",
    "hormigon": "TipoHormigon",
    "retiro_moldaje_h": "RetiroMoldaje_h",
}


class ErrorConfiguracion(ValueError):
    """Configuración inválida o incompleta."""


@dataclass(frozen=True)
class ConfigMalla:
    paso_m: float
    margen_lateral_m: float
    margen_superior_m: float
    espesor_suelo_m: float
    corregir_area: bool = False  # convección con área real (w = 1/||n||₁) en vez de staircase


@dataclass(frozen=True)
class ConfigCaso:
    """Configuración validada. ``datos`` conserva el dict original (trazabilidad)."""

    ruta_ifc: Path
    malla: ConfigMalla
    tiempo: ParametrosTiempo
    ambiente: Ambiente
    base: CondicionBase
    suelo: Material | None
    T_suelo_inicial_C: float | None
    hormigones: dict[str, Hormigon]
    guardar_campos: bool
    datos: dict[str, Any]


# --- lectura y sobrescritura ----------------------------------------------------

def leer_config(fuente: str | Path | Mapping[str, Any], base_rutas: Path | None = None) -> ConfigCaso:
    """Lee la configuración desde un YAML o un dict y la valida.

    Las rutas relativas (``ifc``) se resuelven respecto del YAML, o de
    ``base_rutas`` si se entrega un dict.
    """
    if isinstance(fuente, Mapping):
        datos = copy.deepcopy(dict(fuente))
        carpeta = Path(base_rutas or Path.cwd())
    else:
        ruta = Path(fuente)
        if not ruta.is_file():
            raise FileNotFoundError(f"No se encontró la configuración: {ruta}")
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
        carpeta = ruta.parent
    return validar_config(datos, carpeta)


def aplicar_sobrescrituras(datos: Mapping[str, Any], asignaciones: Sequence[str]) -> dict[str, Any]:
    """Aplica ``clave.subclave=valor`` (p. ej. ``vertidas.2.inicio_h=12``).

    El valor se interpreta como YAML (``0.2`` -> float, ``true`` -> bool). Los
    segmentos numéricos se usan como enteros (ids de vertida).
    """
    datos = copy.deepcopy(dict(datos))
    for asignacion in asignaciones:
        if "=" not in asignacion:
            raise ErrorConfiguracion(f"Sobrescritura sin '=': {asignacion!r}.")
        clave, valor = asignacion.split("=", 1)
        partes = [int(p) if p.isdigit() else p for p in clave.strip().split(".")]
        nodo = datos
        for p in partes[:-1]:
            if not isinstance(nodo.get(p), dict):
                nodo[p] = {}
            nodo = nodo[p]
        nodo[partes[-1]] = yaml.safe_load(valor)
    return datos


# --- validación -------------------------------------------------------------------

def _numero(valor: Any, donde: str, positivo: bool = False, no_negativo: bool = False) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ErrorConfiguracion(f"{donde}: se esperaba un número, se leyó {valor!r}.")
    valor = float(valor)
    if not math.isfinite(valor):
        raise ErrorConfiguracion(f"{donde}: debe ser finito.")
    if positivo and valor <= 0.0:
        raise ErrorConfiguracion(f"{donde}: debe ser positivo.")
    if no_negativo and valor < 0.0:
        raise ErrorConfiguracion(f"{donde}: no puede ser negativo.")
    return valor


def _booleano(valor: Any, donde: str) -> bool:
    if not isinstance(valor, bool):
        raise ErrorConfiguracion(f"{donde}: se esperaba true o false, se leyó {valor!r}.")
    return valor


def _claves(seccion: Any, permitidas: Mapping[str, Any], donde: str) -> dict[str, Any]:
    if not isinstance(seccion, Mapping):
        raise ErrorConfiguracion(f"{donde}: se esperaba un diccionario.")
    desconocidas = set(seccion) - set(permitidas)
    if desconocidas:
        raise ErrorConfiguracion(
            f"{donde}: claves desconocidas {sorted(map(str, desconocidas))}; permitidas {sorted(permitidas)}."
        )
    return dict(seccion)


def _requerir(seccion: Mapping[str, Any], clave: str, donde: str) -> Any:
    if clave not in seccion:
        raise ErrorConfiguracion(f"{donde}: falta '{clave}'.")
    return seccion[clave]


def _hormigon(nombre: str, d: Any) -> Hormigon:
    donde = f"hormigones.{nombre}"
    d = _claves(d, _HORMIGON, donde)
    mat = Material(
        _numero(_requerir(d, "k_W_mK", donde), f"{donde}.k_W_mK", positivo=True),
        _numero(_requerir(d, "rho_kg_m3", donde), f"{donde}.rho_kg_m3", positivo=True),
        _numero(_requerir(d, "cp_J_kgK", donde), f"{donde}.cp_J_kgK", positivo=True),
    )
    hid = None
    if d.get("hidratacion") is not None:
        dh = _claves(d["hidratacion"], _HIDRATACION, f"{donde}.hidratacion")
        try:
            hid = ModeloHidratacion(
                modelo=str(_requerir(dh, "modelo", f"{donde}.hidratacion")),
                theta_inf_C=_numero(_requerir(dh, "theta_inf_C", f"{donde}.hidratacion"), "theta_inf_C"),
                tau_h=_numero(_requerir(dh, "tau_h", f"{donde}.hidratacion"), "tau_h"),
                rho=mat.rho,
                cp=mat.cp,
                beta=_numero(dh.get("beta", 1.0), "beta"),
                Ea_J_mol=_numero(dh.get("Ea_J_mol", 0.0), "Ea_J_mol"),
                T_ref_C=_numero(dh.get("T_ref_C", 20.0), "T_ref_C"),
            )
        except ValueError as exc:
            raise ErrorConfiguracion(f"{donde}.hidratacion: {exc}") from exc
    return Hormigon(mat, hid)


def validar_config(datos: Mapping[str, Any], carpeta: Path) -> ConfigCaso:
    datos = _claves(datos, _ESQUEMA, "config")
    for clave in _REQUERIDAS:
        _requerir(datos, clave, "config")

    m = _claves(datos["malla"], _ESQUEMA["malla"], "malla")
    s = _claves(datos["simulacion"], _ESQUEMA["simulacion"], "simulacion")
    a = _claves(datos["ambiente"], _ESQUEMA["ambiente"], "ambiente")
    b = _claves(datos["base"], _ESQUEMA["base"], "base")
    su = _claves(datos.get("suelo") or {"espesor_m": 0.0}, _ESQUEMA["suelo"], "suelo")

    espesor = _numero(su.get("espesor_m", 0.0), "suelo.espesor_m", no_negativo=True)
    malla = ConfigMalla(
        _numero(_requerir(m, "paso_m", "malla"), "malla.paso_m", positivo=True),
        _numero(_requerir(m, "margen_lateral_m", "malla"), "malla.margen_lateral_m", no_negativo=True),
        _numero(_requerir(m, "margen_superior_m", "malla"), "malla.margen_superior_m", no_negativo=True),
        espesor,
        _booleano(m.get("corregir_area", False), "malla.corregir_area"),
    )
    dt_max_s = math.inf
    if "dt_max_h" in s:
        dt_max_s = _numero(s["dt_max_h"], "simulacion.dt_max_h", positivo=True) * HORA
    try:
        tiempo = ParametrosTiempo(
            duracion_s=_numero(_requerir(s, "duracion_h", "simulacion"), "simulacion.duracion_h", positivo=True) * HORA,
            fraccion_dt=_numero(s.get("fraccion_dt", 0.8), "simulacion.fraccion_dt", positivo=True),
            dt_max_s=dt_max_s,
            guardar_cada_s=_numero(s.get("guardar_cada_h", 1.0), "simulacion.guardar_cada_h", positivo=True) * HORA,
        )
        serie = a.get("serie") or []
        if not all(isinstance(p, (list, tuple)) and len(p) == 2 for p in serie):
            raise ErrorConfiguracion("ambiente.serie: lista de pares [t_h, T_C].")
        ambiente = Ambiente(
            T_C=_numero(_requerir(a, "T_C", "ambiente"), "ambiente.T_C"),
            h=_numero(_requerir(a, "h_W_m2K", "ambiente"), "ambiente.h_W_m2K", no_negativo=True),
            serie_t_s=tuple(_numero(p[0], "ambiente.serie t_h") * HORA for p in serie),
            serie_T_C=tuple(_numero(p[1], "ambiente.serie T_C") for p in serie),
        )
        base = CondicionBase(
            str(_requerir(b, "tipo", "base")),
            _numero(b["T_C"], "base.T_C") if "T_C" in b else math.nan,
        )
    except ErrorConfiguracion:
        raise
    except ValueError as exc:
        raise ErrorConfiguracion(str(exc)) from exc

    suelo = None
    T_suelo = None
    if espesor > 0.0:
        suelo = Material(
            _numero(_requerir(su, "k_W_mK", "suelo"), "suelo.k_W_mK", positivo=True),
            _numero(_requerir(su, "rho_kg_m3", "suelo"), "suelo.rho_kg_m3", positivo=True),
            _numero(_requerir(su, "cp_J_kgK", "suelo"), "suelo.cp_J_kgK", positivo=True),
        )
        T_suelo = _numero(_requerir(su, "T_inicial_C", "suelo"), "suelo.T_inicial_C")

    if not isinstance(datos["hormigones"], Mapping) or not datos["hormigones"]:
        raise ErrorConfiguracion("hormigones: definir al menos un tipo.")
    hormigones = {str(n): _hormigon(str(n), d) for n, d in datos["hormigones"].items()}

    vertidas = datos.get("vertidas") or {}
    if not isinstance(vertidas, Mapping):
        raise ErrorConfiguracion("vertidas: se esperaba un diccionario {id: {...}}.")
    for clave, v in vertidas.items():
        if clave != "defecto" and (isinstance(clave, bool) or not isinstance(clave, int)):
            raise ErrorConfiguracion(f"vertidas: clave {clave!r} debe ser un VertidaID entero o 'defecto'.")
        _claves(v or {}, _VERTIDA, f"vertidas.{clave}")

    ruta_ifc = Path(str(datos["ifc"]))
    if not ruta_ifc.is_absolute():
        ruta_ifc = (carpeta / ruta_ifc).resolve()

    return ConfigCaso(
        ruta_ifc, malla, tiempo, ambiente, base, suelo, T_suelo, hormigones,
        bool(s.get("guardar_campos", False)), dict(datos),
    )


# --- combinación con el IFC ----------------------------------------------------------

def resolver_plan(config: ConfigCaso, vertidas_ifc: Sequence[tuple[int, str, Mapping[str, Any]]]) -> list[PlanVertida]:
    """Combina config e IFC en un ``PlanVertida`` por vertida del modelo.

    ``vertidas_ifc``: (vertida_id, nombre, pset) de cada vertida leída del IFC.
    """
    tabla = config.datos.get("vertidas") or {}
    defecto = dict(tabla.get("defecto") or {})
    ids_ifc = {vid for vid, _, _ in vertidas_ifc}
    sobran = {k for k in tabla if k != "defecto"} - ids_ifc
    if sobran:
        raise ErrorConfiguracion(f"vertidas: ids {sorted(sobran)} no existen en el IFC ({sorted(ids_ifc)}).")

    planes = []
    for vid, nombre, pset in vertidas_ifc:
        propia = dict(tabla.get(vid) or {})
        valores: dict[str, Any] = {}
        origen: dict[str, str] = {}
        for campo in _VERTIDA:
            if campo in propia:
                valores[campo], origen[campo] = propia[campo], f"vertidas.{vid}"
            elif campo in defecto:
                valores[campo], origen[campo] = defecto[campo], "vertidas.defecto"
            elif campo in _DESDE_IFC and _es_valido(pset.get(_DESDE_IFC[campo])):
                valores[campo], origen[campo] = pset[_DESDE_IFC[campo]], f"IFC:{_DESDE_IFC[campo]}"
        donde = f"vertida {vid} ({nombre})"
        for campo in ("inicio_h", "T_colocacion_C", "hormigon"):
            if campo not in valores:
                raise ErrorConfiguracion(f"{donde}: falta '{campo}' en la config y en el IFC.")
        hormigon = str(valores["hormigon"])
        if hormigon not in config.hormigones:
            raise ErrorConfiguracion(f"{donde}: hormigón {hormigon!r} no está en 'hormigones'.")
        retiro = valores.get("retiro_moldaje_h")
        try:
            plan = PlanVertida(
                vertida_id=vid,
                inicio_s=_numero(valores["inicio_h"], f"{donde}.inicio_h", no_negativo=True) * HORA,
                T_colocacion_C=_numero(valores["T_colocacion_C"], f"{donde}.T_colocacion_C"),
                hormigon=hormigon,
                visible=bool(valores.get("visible", True)),
                R_lateral=_numero(valores.get("R_lateral_m2K_W", 0.0), f"{donde}.R_lateral", no_negativo=True),
                R_superior=_numero(valores.get("R_superior_m2K_W", 0.0), f"{donde}.R_superior", no_negativo=True),
                retiro_moldaje_s=math.inf if retiro is None
                else _numero(retiro, f"{donde}.retiro_moldaje_h", positivo=True) * HORA,
                nombre=nombre,
                origen=origen,
            )
        except ErrorConfiguracion:
            raise
        except ValueError as exc:
            raise ErrorConfiguracion(f"{donde}: {exc}") from exc
        planes.append(plan)
    return planes


def _es_valido(valor: Any) -> bool:
    """Un valor del pset sirve si existe y no es un marcador tipo 'TBD'."""
    if valor is None:
        return False
    if isinstance(valor, str):
        return valor.strip().upper() not in ("", "TBD", "N/A", "NA")
    return True
