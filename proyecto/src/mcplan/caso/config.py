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
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from ..thermal.bordes import Ambiente, CapaProteccion, CondicionBase, factor_viento_log
from ..thermal.etapas import Hormigon, Material, ParametrosTiempo, PlanVertida
from ..thermal.hidratacion import HORA, ModeloHidratacion, theta_inf_desde_dosificacion
from .clima import VAR_G, VAR_VIENTO, leer_snapshot, series_para_simulacion
from .fuente_calor import elevacion_adiabatica, leer_fuente

_ESQUEMA: dict[str, Any] = {
    "ifc": str,
    "malla": {
        "paso_m": float, "paso_z_m": float, "margen_lateral_m": float, "margen_superior_m": float,
        "corregir_area": bool,
    },
    "simulacion": {
        "duracion_h": float, "fraccion_dt": float, "dt_max_h": float,
        "guardar_cada_h": float, "guardar_campos": bool, "guardar_campos_cada_h": float, "inicio": str,
    },
    "ambiente": {
        "T_C": float, "h_W_m2K": float, "serie": list, "conveccion_viento": dict,
        "absortividad_solar": float, "emisividad": float, "factor_solar_lateral": float,
        "ciclo_diario": dict,
    },
    "clima": {"snapshot": str, "completar": str, "desplazar_anios": int, "respaldo": dict},
    "criterios": {"T_max_C": float, "delta_T_C": float, "profundidad_superficie_m": float},
    "base": {"tipo": str, "T_C": float},
    "suelo": {"espesor_m": float, "k_W_mK": float, "rho_kg_m3": float, "cp_J_kgK": float, "T_inicial_C": float},
    "hormigones": dict,
    "vertidas": dict,
    "protecciones": dict,
    "tuberias": list,
}
_HORMIGON = {"k_W_mK": float, "rho_kg_m3": float, "cp_J_kgK": float, "hidratacion": dict}
_HIDRATACION = {
    "modelo": str, "theta_inf_C": float, "tau_h": float, "beta": float, "Ea_J_mol": float, "T_ref_C": float,
    "tabla": list, "cemento_kg_m3": float, "calor_cemento_J_kg": float, "grado_hidratacion_ultimo": float,
    "archivo": str, "curva": str, "paso_h": float,
}
_DOSIFICACION = ("cemento_kg_m3", "calor_cemento_J_kg")
_CONVECCION_VIENTO = {
    "a_W_m2K": float, "b_J_m3K": float, "incluye_radiacion": bool,
    "altura_medicion_m": float, "altura_superficie_m": float, "rugosidad_m": float,
}
_VERTIDA = {
    "inicio_h": float, "inicio": str, "T_colocacion_C": float, "hormigon": str, "visible": bool,
    "R_lateral_m2K_W": float, "R_superior_m2K_W": float, "retiro_moldaje_h": float,
    "moldaje": str, "aislacion": str, "aislacion_caras": list, "aislacion_desde_h": float,
    "aislacion_hasta_h": float,
}
_PROTECCION = {"espesor_m": float, "k_W_mK": float}
_REQUERIDAS = ("ifc", "malla", "simulacion", "ambiente", "base", "hormigones")

# pset del IFC -> campo del plan (solo los que el IFC puede aportar)
_DESDE_IFC = {
    "inicio_h": "Inicio_h",
    "T_colocacion_C": "TemperaturaColocacion_C",
    "hormigon": "TipoHormigon",
    "retiro_moldaje_h": "RetiroMoldaje_h",
    "moldaje": "Moldaje",  # nombre en el catálogo 'protecciones' (TBD en el IFC actual)
    "aislacion": "Aislacion",
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
    paso_z_m: float | None = None  # Δz propio; None = paso_m (voxel cúbico)

    @property
    def pasos(self) -> tuple[float, float, float]:
        dz = self.paso_m if self.paso_z_m is None else self.paso_z_m
        return (self.paso_m, self.paso_m, dz)


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
    inicio: datetime | None = None  # fecha-hora local de t = 0
    nota_clima: str = ""  # fuente, modelo, descarga y completado del clima
    criterios: Criterios | None = None
    campos_cada_s: float | None = None  # campos 3D para visualizar (None: cada registro)
    tuberias: tuple[ConfigTuberia, ...] = ()


_TUBERIA = {
    "nombre": str, "vertida": int, "cota_m": float, "direccion": str, "separacion_m": float,
    "diametro_m": float, "T_agua_C": float, "desde_h": float, "hasta_h": float, "recubrimiento_m": float,
}


@dataclass(frozen=True)
class ConfigTuberia:
    """Un circuito de enfriamiento declarado en el YAML (se traza sobre la grilla en el pipeline)."""

    nombre: str
    vertida: int
    cota_m: float
    direccion: str
    separacion_m: float
    diametro_m: float
    T_agua_C: float
    desde_h: float = 0.0
    hasta_h: float = math.inf
    recubrimiento_m: float = 0.5


# [MAPA:config-tuberias] circuitos de enfriamiento del YAML: cota, dirección, separación, diámetro, T del agua
def _tuberias(lista: Any) -> tuple[ConfigTuberia, ...]:
    if lista is None:
        return ()
    if not isinstance(lista, list):
        raise ErrorConfiguracion("tuberias: lista de circuitos.")
    circuitos, nombres = [], set()
    for n, item in enumerate(lista):
        donde = f"tuberias[{n}]"
        d = _claves(item, _TUBERIA, donde)
        nombre = str(d.get("nombre", f"circuito_{n + 1}"))
        if nombre in nombres:
            raise ErrorConfiguracion(f"{donde}: nombre {nombre!r} repetido.")
        nombres.add(nombre)
        vertida = _requerir(d, "vertida", donde)
        if isinstance(vertida, bool) or not isinstance(vertida, int):
            raise ErrorConfiguracion(f"{donde}.vertida: VertidaID entero.")
        direccion = str(d.get("direccion", "x"))
        if direccion not in ("x", "y"):
            raise ErrorConfiguracion(f"{donde}.direccion: 'x' o 'y'.")
        hasta = d.get("hasta_h")
        circuitos.append(ConfigTuberia(
            nombre=nombre, vertida=vertida,
            cota_m=_numero(_requerir(d, "cota_m", donde), f"{donde}.cota_m"),
            direccion=direccion,
            separacion_m=_numero(_requerir(d, "separacion_m", donde), f"{donde}.separacion_m", positivo=True),
            diametro_m=_numero(_requerir(d, "diametro_m", donde), f"{donde}.diametro_m", positivo=True),
            T_agua_C=_numero(_requerir(d, "T_agua_C", donde), f"{donde}.T_agua_C"),
            desde_h=_numero(d.get("desde_h", 0.0), f"{donde}.desde_h", no_negativo=True),
            hasta_h=math.inf if hasta is None else _numero(hasta, f"{donde}.hasta_h", positivo=True),
            recubrimiento_m=_numero(d.get("recubrimiento_m", 0.5), f"{donde}.recubrimiento_m", no_negativo=True),
        ))
    return tuple(circuitos)


@dataclass(frozen=True)
class Criterios:
    """Criterios docentes de la hoja de ruta (no normativos)."""

    T_max_C: float = 70.0
    delta_T_C: float = 20.0
    profundidad_superficie_m: float = 0.025  # "superficie" ~25 mm bajo la cara exterior


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


# [MAPA:sobrescrituras] --set / --variante: cambia una clave del YAML sin editar el archivo
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
            if isinstance(nodo, list):  # p. ej. tuberias.0.T_agua_C: índice de la lista
                if not isinstance(p, int) or not 0 <= p < len(nodo):
                    raise ErrorConfiguracion(f"{clave}: índice {p!r} fuera de la lista (0..{len(nodo) - 1}).")
            elif not isinstance(nodo.get(p), (dict, list)):
                nodo[p] = {}
            nodo = nodo[p]
        if isinstance(nodo, list):
            p = partes[-1]
            if not isinstance(p, int) or not 0 <= p < len(nodo):
                raise ErrorConfiguracion(f"{clave}: índice {p!r} fuera de la lista (0..{len(nodo) - 1}).")
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


# [MAPA:config-hormigon] lee k, rho, cp e hidratación del YAML
def _hormigon(nombre: str, d: Any, carpeta: Path | None = None) -> Hormigon:
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
        dondeh = f"{donde}.hidratacion"
        try:
            modelo = str(_requerir(dh, "modelo", dondeh))
            tabla_t: tuple[float, ...] = ()
            tabla_th: tuple[float, ...] = ()
            if modelo == "fuente_Q":
                # Q(t) medido [W/m³] (archivo del profesor) -> θ(t) = ∫Q dt/(ρ cp) -> modelo tabla.
                for clave in ("theta_inf_C", "tau_h", "beta", "tabla", *_DOSIFICACION):
                    if clave in dh:
                        raise ErrorConfiguracion(f"{dondeh}: con modelo fuente_Q sobra '{clave}'.")
                ruta = Path(str(_requerir(dh, "archivo", dondeh)))
                if not ruta.is_absolute():
                    ruta = (Path(carpeta or Path.cwd()) / ruta).resolve()
                if not ruta.is_file():
                    raise ErrorConfiguracion(f"{dondeh}.archivo: no existe {ruta}.")
                serie = leer_fuente(ruta)
                tabla_t, tabla_th = elevacion_adiabatica(
                    serie.t_h, serie.curva(str(_requerir(dh, "curva", dondeh))), mat.rho * mat.cp,
                    _numero(dh.get("paso_h", 0.25), f"{dondeh}.paso_h", positivo=True))
                modelo, theta_inf, tau = "tabla", tabla_th[-1], 1.0
            elif modelo == "tabla":
                # Curva adiabática medida: tau y theta_inf salen de la tabla.
                for clave in ("theta_inf_C", "tau_h", "beta", *_DOSIFICACION):
                    if clave in dh:
                        raise ErrorConfiguracion(f"{dondeh}: con modelo tabla sobra '{clave}'.")
                filas = _requerir(dh, "tabla", dondeh)
                if not isinstance(filas, list) or not all(isinstance(f, (list, tuple)) and len(f) == 2 for f in filas):
                    raise ErrorConfiguracion(f"{dondeh}.tabla: lista de pares [t_h, theta_C].")
                tabla_t = tuple(_numero(f[0], f"{dondeh}.tabla t_h") for f in filas)
                tabla_th = tuple(_numero(f[1], f"{dondeh}.tabla theta_C") for f in filas)
                theta_inf, tau = tabla_th[-1], 1.0
            else:
                if "tabla" in dh:
                    raise ErrorConfiguracion(f"{dondeh}: 'tabla' solo con modelo tabla.")
                for clave in ("archivo", "curva", "paso_h"):
                    if clave in dh:
                        raise ErrorConfiguracion(f"{dondeh}: '{clave}' solo con modelo fuente_Q.")
                tau = _numero(_requerir(dh, "tau_h", dondeh), "tau_h")
                theta_inf = _theta_inf(dh, dondeh, mat)
            hid = ModeloHidratacion(
                modelo=modelo,
                theta_inf_C=theta_inf,
                tau_h=tau,
                rho=mat.rho,
                cp=mat.cp,
                beta=_numero(dh.get("beta", 1.0), "beta"),
                Ea_J_mol=_numero(dh.get("Ea_J_mol", 0.0), "Ea_J_mol"),
                T_ref_C=_numero(dh.get("T_ref_C", 20.0), "T_ref_C"),
                tabla_t_h=tabla_t,
                tabla_theta_C=tabla_th,
            )
        except ErrorConfiguracion:
            raise
        except ValueError as exc:
            raise ErrorConfiguracion(f"{dondeh}: {exc}") from exc
    return Hormigon(mat, hid)


def _theta_inf(dh: Mapping[str, Any], donde: str, mat: Material) -> float:
    """theta_inf directo o desde la dosificación; exactamente una de las dos fuentes."""
    tiene_dosificacion = any(k in dh for k in (*_DOSIFICACION, "grado_hidratacion_ultimo"))
    if ("theta_inf_C" in dh) == tiene_dosificacion:
        raise ErrorConfiguracion(
            f"{donde}: definir theta_inf_C o la dosificación (cemento_kg_m3, calor_cemento_J_kg), no ambas ni ninguna."
        )
    if "theta_inf_C" in dh:
        return _numero(dh["theta_inf_C"], f"{donde}.theta_inf_C", no_negativo=True)
    return theta_inf_desde_dosificacion(
        _numero(_requerir(dh, "cemento_kg_m3", donde), f"{donde}.cemento_kg_m3", positivo=True),
        _numero(_requerir(dh, "calor_cemento_J_kg", donde), f"{donde}.calor_cemento_J_kg", positivo=True),
        _numero(dh.get("grado_hidratacion_ultimo", 1.0), f"{donde}.grado_hidratacion_ultimo", positivo=True),
        mat.rho,
        mat.cp,
    )


def _fecha(valor: Any, donde: str) -> datetime:
    """Fecha-hora ISO local (p. ej. '2026-11-27T04:00'), en la zona del snapshot."""
    if isinstance(valor, datetime):
        return valor.replace(tzinfo=None)
    if isinstance(valor, date):
        return datetime(valor.year, valor.month, valor.day)
    try:
        return datetime.fromisoformat(str(valor)).replace(tzinfo=None)
    except ValueError as exc:
        raise ErrorConfiguracion(f"{donde}: fecha ISO inválida {valor!r} (ej. 2026-11-27T04:00).") from exc


def _ambiente(a: Mapping[str, Any], clima: Any, inicio: datetime | None, duracion_s: float,
              carpeta: Path) -> tuple[Ambiente, str]:
    """Ambiente constante, con serie manual o con un snapshot de clima (G07)."""
    if a.get("ciclo_diario") is not None:
        from .ciclo_diario import serie_diaria
        if inicio is None or clima is not None or any(k in a for k in ("T_C", "serie", "conveccion_viento")):
            raise ErrorConfiguracion("ciclo_diario: requiere simulacion.inicio y no se mezcla con snapshot, T_C, serie o viento.")
        if any(a.get(k, 0) != 0 for k in ("emisividad", "absortividad_solar")):
            raise ErrorConfiguracion("ciclo_diario: estos CSV solo aportan temperatura; no radiación.")
        c = _claves(a["ciclo_diario"], {"minima_C": float, "maxima_C": float,
                    "hora_min": float, "hora_max": float, "fuente": str}, "ambiente.ciclo_diario")
        try:
            ts, temperaturas = serie_diaria(inicio, duracion_s,
                _numero(_requerir(c, "minima_C", "ciclo_diario"), "minima_C"),
                _numero(_requerir(c, "maxima_C", "ciclo_diario"), "maxima_C"),
                c.get("hora_min", 6.0), c.get("hora_max", 15.0))
            h = _numero(_requerir(a, "h_W_m2K", "ambiente"), "h_W_m2K", no_negativo=True)
            nota = (f"ESCENARIO ESTIMADO: ciclo diario {c['minima_C']:g}–{c['maxima_C']:g} °C; "
                    f"mínima a {c.get('hora_min', 6):g} h y máxima a {c.get('hora_max', 15):g} h "
                    f"(horas supuestas, ajustables). {c.get('fuente', '')}. "
                    "Mismo ciclo de noviembre repetido durante toda la simulación, incluso fuera de noviembre. "
                    "Convección constante; sin viento variable ni radiación solar.")
            return Ambiente(T_C=temperaturas[0], h=h, serie_t_s=ts, serie_T_C=temperaturas), nota
        except ValueError as exc:
            raise ErrorConfiguracion(f"ciclo_diario: {exc}") from exc
    viento = None
    factor_viento = 1.0
    radiacion = {
        "absortividad": _numero(a.get("absortividad_solar", 0.0), "ambiente.absortividad_solar", no_negativo=True),
        "emisividad": _numero(a.get("emisividad", 0.0), "ambiente.emisividad", no_negativo=True),
        "factor_solar_lateral": _numero(a.get("factor_solar_lateral", 0.0), "ambiente.factor_solar_lateral",
                                        no_negativo=True),
    }
    if a.get("conveccion_viento") is not None:
        donde = "ambiente.conveccion_viento"
        cv = _claves(a["conveccion_viento"], _CONVECCION_VIENTO, donde)
        viento = (
            _numero(_requerir(cv, "a_W_m2K", donde), f"{donde}.a_W_m2K", no_negativo=True),
            _numero(_requerir(cv, "b_J_m3K", donde), f"{donde}.b_J_m3K", no_negativo=True),
        )
        if "h_W_m2K" in a:
            raise ErrorConfiguracion("ambiente: usar h_W_m2K o conveccion_viento, no ambos.")
        # [MAPA:doble-conteo] una correlación que ya incluye radiación no se combina con emisividad > 0
        if _booleano(cv.get("incluye_radiacion", False), f"{donde}.incluye_radiacion") and radiacion["emisividad"] > 0:
            raise ErrorConfiguracion(
                f"{donde}: la correlación incluye radiación (p. ej. McAdams 5,7 + 3,8·v) y además "
                "ambiente.emisividad > 0 cuenta la onda larga otra vez. Usar una correlación solo "
                "convectiva (Watmuff 2,8 + 3,0·v) o emisividad: 0."
            )
        if "altura_superficie_m" in cv:
            try:
                factor_viento = factor_viento_log(
                    _numero(cv.get("altura_medicion_m", 10.0), f"{donde}.altura_medicion_m", positivo=True),
                    _numero(cv["altura_superficie_m"], f"{donde}.altura_superficie_m", positivo=True),
                    _numero(cv.get("rugosidad_m", 0.03), f"{donde}.rugosidad_m", positivo=True),
                )
            except ValueError as exc:
                raise ErrorConfiguracion(f"{donde}: {exc}") from exc
    h = 0.0 if viento else _numero(_requerir(a, "h_W_m2K", "ambiente"), "ambiente.h_W_m2K", no_negativo=True)

    if clima is None:
        serie = a.get("serie") or []
        if not all(isinstance(p, (list, tuple)) and len(p) == 2 for p in serie):
            raise ErrorConfiguracion("ambiente.serie: lista de pares [t_h, T_C].")
        if viento:
            raise ErrorConfiguracion("ambiente.conveccion_viento requiere una sección 'clima' con viento.")
        try:
            return Ambiente(
                T_C=_numero(_requerir(a, "T_C", "ambiente"), "ambiente.T_C"),
                h=h,
                serie_t_s=tuple(_numero(p[0], "ambiente.serie t_h") * HORA for p in serie),
                serie_T_C=tuple(_numero(p[1], "ambiente.serie T_C") for p in serie),
                **radiacion,
            ), "ambiente constante o serie manual"
        except ValueError as exc:
            raise ErrorConfiguracion(f"ambiente: {exc}") from exc

    c = _claves(clima, _ESQUEMA["clima"], "clima")
    if inicio is None:
        raise ErrorConfiguracion("clima: definir simulacion.inicio (fecha-hora de t = 0).")
    for clave in ("T_C", "serie"):
        if clave in a:
            raise ErrorConfiguracion(f"ambiente.{clave}: con 'clima' la temperatura viene del snapshot.")
    def ruta_de(valor: Any) -> Path:
        ruta = Path(str(valor))
        return ruta if ruta.is_absolute() else (carpeta / ruta).resolve()

    try:
        snap = leer_snapshot(ruta_de(_requerir(c, "snapshot", "clima")))
        respaldo, desplazar_respaldo = None, 0
        if c.get("respaldo") is not None:
            r = _claves(c["respaldo"], {"snapshot": str, "desplazar_anios": int}, "clima.respaldo")
            respaldo = leer_snapshot(ruta_de(_requerir(r, "snapshot", "clima.respaldo")))
            desplazar_respaldo = r.get("desplazar_anios", 0)
        s = series_para_simulacion(snap, inicio, duracion_s, str(c.get("completar", "error")),
                                   c.get("desplazar_anios", 0), respaldo, desplazar_respaldo)
        if viento and not s.viento_m_s:
            raise ErrorConfiguracion(f"clima: el snapshot no trae {VAR_VIENTO} y conveccion_viento lo necesita.")
        if radiacion["absortividad"] > 0.0 and not s.G_W_m2:
            raise ErrorConfiguracion(f"clima: el snapshot no trae {VAR_G} y absortividad_solar > 0 lo necesita.")
        return Ambiente(
            T_C=s.T_C[0], h=h, serie_t_s=s.t_s, serie_T_C=s.T_C,
            serie_viento_m_s=s.viento_m_s if viento else (),
            serie_G_W_m2=s.G_W_m2 if radiacion["absortividad"] > 0.0 else (),
            h_viento=viento, factor_viento=factor_viento, **radiacion,
        ), s.nota
    except ErrorConfiguracion:
        raise
    except (ValueError, FileNotFoundError) as exc:
        raise ErrorConfiguracion(f"clima: {exc}") from exc


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
        _numero(m["paso_z_m"], "malla.paso_z_m", positivo=True) if m.get("paso_z_m") is not None else None,
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
        inicio = _fecha(s["inicio"], "simulacion.inicio") if "inicio" in s else None
        ambiente, nota_clima = _ambiente(a, datos.get("clima"), inicio, tiempo.duracion_s, carpeta)
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
    # [MAPA:config-suelo] suelo bajo la fundación (espesor, k, rho, cp, T inicial)
    if espesor > 0.0:
        suelo = Material(
            _numero(_requerir(su, "k_W_mK", "suelo"), "suelo.k_W_mK", positivo=True),
            _numero(_requerir(su, "rho_kg_m3", "suelo"), "suelo.rho_kg_m3", positivo=True),
            _numero(_requerir(su, "cp_J_kgK", "suelo"), "suelo.cp_J_kgK", positivo=True),
        )
        T_suelo = _numero(_requerir(su, "T_inicial_C", "suelo"), "suelo.T_inicial_C")

    if not isinstance(datos["hormigones"], Mapping) or not datos["hormigones"]:
        raise ErrorConfiguracion("hormigones: definir al menos un tipo.")
    hormigones = {str(n): _hormigon(str(n), d, carpeta) for n, d in datos["hormigones"].items()}

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

    cr = _claves(datos.get("criterios") or {}, _ESQUEMA["criterios"], "criterios")
    criterios = Criterios(
        _numero(cr.get("T_max_C", 70.0), "criterios.T_max_C"),
        _numero(cr.get("delta_T_C", 20.0), "criterios.delta_T_C", positivo=True),
        _numero(cr.get("profundidad_superficie_m", 0.025), "criterios.profundidad_superficie_m", no_negativo=True),
    )
    campos_cada_s = None
    if s.get("guardar_campos_cada_h") is not None:
        campos_cada_s = _numero(s["guardar_campos_cada_h"], "simulacion.guardar_campos_cada_h", positivo=True) * HORA
    guardar_campos = _booleano(s.get("guardar_campos", campos_cada_s is not None), "simulacion.guardar_campos")
    return ConfigCaso(
        ruta_ifc, malla, tiempo, ambiente, base, suelo, T_suelo, hormigones,
        guardar_campos, dict(datos), inicio, nota_clima, criterios, campos_cada_s,
        _tuberias(datos.get("tuberias")),
    )


# --- combinación con el IFC ----------------------------------------------------------

# [MAPA:prioridad-ifc-yaml] vertidas.<id> > vertidas.defecto > pset del IFC
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
        for alcance, datos_alcance in ((f"vertidas.{vid}", propia), ("vertidas.defecto", defecto)):
            if "inicio" in datos_alcance and "inicio_h" in datos_alcance:
                raise ErrorConfiguracion(f"{alcance}: usar 'inicio' (fecha) o 'inicio_h', no ambos.")
        prioridad = {f"vertidas.{vid}": 0, "vertidas.defecto": 1}
        if "inicio" in valores and prioridad.get(origen["inicio"], 2) <= prioridad.get(origen.get("inicio_h", ""), 2):
            if config.inicio is None:
                raise ErrorConfiguracion(f"{donde}: 'inicio' con fecha requiere simulacion.inicio.")
            fecha = _fecha(valores["inicio"], f"{donde}.inicio")
            valores["inicio_h"] = (fecha - config.inicio).total_seconds() / HORA
            origen["inicio_h"] = f"{origen['inicio']} ({fecha:%Y-%m-%d %H:%M})"
            if valores["inicio_h"] < 0.0:
                raise ErrorConfiguracion(f"{donde}: inicio {fecha} es anterior a simulacion.inicio {config.inicio}.")
        for campo in ("inicio_h", "T_colocacion_C", "hormigon"):
            if campo not in valores:
                raise ErrorConfiguracion(f"{donde}: falta '{campo}' en la config y en el IFC.")
        hormigon = str(valores["hormigon"])
        if hormigon not in config.hormigones:
            raise ErrorConfiguracion(f"{donde}: hormigón {hormigon!r} no está en 'hormigones'.")
        retiro = valores.get("retiro_moldaje_h")
        retiro_s = math.inf if retiro is None else _numero(retiro, f"{donde}.retiro_moldaje_h", positivo=True) * HORA
        R_lateral = _numero(valores.get("R_lateral_m2K_W", 0.0), f"{donde}.R_lateral", no_negativo=True)
        if "moldaje" in valores and prioridad.get(origen["moldaje"], 2) <= prioridad.get(
                origen.get("R_lateral_m2K_W", ""), 2):
            R_lateral = _proteccion(config, valores["moldaje"], f"{donde}.moldaje")[0]
            origen["R_lateral_m2K_W"] = f"{origen['moldaje']} ({valores['moldaje']})"
        capas = _capas_aislacion(config, valores, retiro_s, donde)
        try:
            plan = PlanVertida(
                vertida_id=vid,
                inicio_s=_numero(valores["inicio_h"], f"{donde}.inicio_h", no_negativo=True) * HORA,
                T_colocacion_C=_numero(valores["T_colocacion_C"], f"{donde}.T_colocacion_C"),
                hormigon=hormigon,
                visible=_booleano(valores.get("visible", True), f"{donde}.visible"),
                R_lateral=R_lateral,
                R_superior=_numero(valores.get("R_superior_m2K_W", 0.0), f"{donde}.R_superior", no_negativo=True),
                retiro_moldaje_s=retiro_s,
                nombre=nombre,
                origen=origen,
                capas=capas,
            )
        except ErrorConfiguracion:
            raise
        except ValueError as exc:
            raise ErrorConfiguracion(f"{donde}: {exc}") from exc
        planes.append(plan)
    return planes


def _proteccion(config: ConfigCaso, nombre: Any, donde: str) -> tuple[float, float, float]:
    """(R, espesor, k) de un material del catálogo 'protecciones': R = e/k."""
    catalogo = config.datos.get("protecciones") or {}
    if str(nombre) not in catalogo:
        raise ErrorConfiguracion(f"{donde}: {nombre!r} no está en 'protecciones' ({sorted(catalogo)}).")
    d = _claves(catalogo[str(nombre)], _PROTECCION, f"protecciones.{nombre}")
    e = _numero(_requerir(d, "espesor_m", f"protecciones.{nombre}"), f"protecciones.{nombre}.espesor_m", positivo=True)
    k = _numero(_requerir(d, "k_W_mK", f"protecciones.{nombre}"), f"protecciones.{nombre}.k_W_mK", positivo=True)
    return e / k, e, k


# [MAPA:aislacion-desmolde] aislación con su propio período; "desmolde" = empieza al retirar el moldaje
def _capas_aislacion(config: ConfigCaso, valores: Mapping[str, Any], retiro_s: float,
                     donde: str) -> tuple[CapaProteccion, ...]:
    """Capa de aislación de una vertida: caras, desde y hasta (horas desde su inicio)."""
    extra = [c for c in ("aislacion_caras", "aislacion_desde_h", "aislacion_hasta_h") if c in valores]
    if "aislacion" not in valores:
        if extra:
            raise ErrorConfiguracion(f"{donde}: {extra} sin 'aislacion'.")
        return ()
    R, e, k = _proteccion(config, valores["aislacion"], f"{donde}.aislacion")
    caras = valores.get("aislacion_caras", ["superior"])
    if not isinstance(caras, list) or not caras or not set(caras) <= {"superior", "lateral", "inferior"}:
        raise ErrorConfiguracion(f"{donde}.aislacion_caras: lista con 'superior', 'lateral' o 'inferior'.")
    desde = valores.get("aislacion_desde_h", 0.0)
    if desde == "desmolde":
        if not math.isfinite(retiro_s):
            raise ErrorConfiguracion(f"{donde}: aislacion_desde_h 'desmolde' sin retiro_moldaje_h.")
        desde_s = retiro_s
    else:
        desde_s = _numero(desde, f"{donde}.aislacion_desde_h", no_negativo=True) * HORA
    hasta = valores.get("aislacion_hasta_h")
    hasta_s = math.inf if hasta is None else _numero(hasta, f"{donde}.aislacion_hasta_h", positivo=True) * HORA
    try:
        return (CapaProteccion(f"aislación {valores['aislacion']} ({e * 1000:g} mm, k = {k:g})", R,
                               frozenset(caras), desde_s, hasta_s),)
    except ValueError as exc:
        raise ErrorConfiguracion(f"{donde}: {exc}") from exc


def _es_valido(valor: Any) -> bool:
    """Un valor del pset sirve si existe y no es un marcador tipo 'TBD'."""
    if valor is None:
        return False
    if isinstance(valor, str):
        return valor.strip().upper() not in ("", "TBD", "N/A", "NA")
    return True
