"""Fuente de calor de hidratación medida Q(t) [W/m³] -> curva adiabática θ(t) [K].

Lee el archivo de la campaña experimental entregado por el profesor
(``data/hidratacion/source_terms.txt``): columnas de Q(t) por probeta y
campaña, cada 60 s. El solver no lee este archivo: la configuración lo
convierte aquí en una tabla (t, θ) para ``ModeloHidratacion('tabla')``.

Conversión (energía): bajo condición adiabática todo el calor generado eleva
la temperatura, así que

    θ(t) = ∫₀ᵗ Q(s) ds / (ρ·cp)        [K]

con ρ·cp del hormigón del caso. Luego el solver recupera la potencia como
q''' = ρ·cp·dθ/dt_e·f(T) (``MAPA:hidratacion-potencia``): con f(T) = 1, el
calor entregado coincide con el medido.

Supuestos (declarados en el YAML):
- las probetas son pequeñas y siguen la temperatura del laboratorio, así que
  la curva se interpreta a T_ref (edad equivalente);
- después del fin del registro de una probeta, su Q se toma como 0 (al final
  ya vale 0–3 W/m³ en la campaña 22A);
- las 2 h previas al inicio de la ventana no están en el archivo.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

HORA = 3600.0
MEDIA = "media"


@dataclass(frozen=True)
class SerieFuente:
    """Q(t) de todas las probetas del archivo."""

    t_h: np.ndarray                 # (n,) horas
    Q: dict[str, np.ndarray]        # nombre -> (n,) W/m³, NaN tras el fin del registro
    sha256: str

    @property
    def nombres(self) -> tuple[str, ...]:
        return tuple(self.Q)

    def curva(self, nombre: str) -> np.ndarray:
        """Q(t) [W/m³] de una probeta, o la media de todas (``'media'``); NaN -> 0."""
        if nombre == MEDIA:
            return np.mean([np.nan_to_num(q, nan=0.0) for q in self.Q.values()], axis=0)
        if nombre not in self.Q:
            raise ValueError(f"Curva {nombre!r} inexistente; opciones: {MEDIA}, {', '.join(self.nombres)}.")
        return np.nan_to_num(self.Q[nombre], nan=0.0)


# [MAPA:fuente-medida] archivo del profesor Q(t) [W/m³] -> θ(t) = ∫Q dt / (ρ cp)
def leer_fuente(ruta: str | Path) -> SerieFuente:
    """Lee ``source_terms.txt``: comentarios ``#``; la última línea ``#`` con
    ``time_h`` nombra las columnas."""
    ruta = Path(ruta)
    crudo = ruta.read_bytes()
    nombres: list[str] | None = None
    for linea in crudo.decode("utf-8").splitlines():
        if linea.startswith("#") and "time_h" in linea and "[" not in linea:
            nombres = linea.lstrip("#").split()
    if not nombres or nombres[0] != "time_h":
        raise ValueError(f"{ruta}: no se encontró la fila de encabezado '# time_h ...'.")
    datos = np.loadtxt(ruta, comments="#")
    if datos.ndim != 2 or datos.shape[1] != len(nombres):
        raise ValueError(f"{ruta}: {len(nombres)} columnas en el encabezado y {datos.shape[-1]} en los datos.")
    t = datos[:, 0]
    if t[0] != 0.0 or np.any(np.diff(t) <= 0.0):
        raise ValueError(f"{ruta}: el tiempo debe partir en 0 y ser creciente.")
    Q = {n: datos[:, i] for i, n in enumerate(nombres) if i > 0}
    for n, q in Q.items():
        validos = q[~np.isnan(q)]
        if validos.size == 0 or np.any(validos < 0.0):
            raise ValueError(f"{ruta}: la curva {n} está vacía o tiene Q negativo.")
    return SerieFuente(t, Q, hashlib.sha256(crudo).hexdigest())


def elevacion_adiabatica(t_h: np.ndarray, Q: np.ndarray, rho_cp: float,
                         paso_h: float = 0.25) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Tabla (t [h], θ [K]) cada ``paso_h``, desde (0, 0), con θ = ∫Q dt / ρcp (trapecios)."""
    if not rho_cp > 0.0 or not paso_h > 0.0:
        raise ValueError("rho_cp y paso_h deben ser positivos.")
    t_h = np.asarray(t_h, float)
    Q = np.clip(np.asarray(Q, float), 0.0, None)
    E = np.concatenate([[0.0], np.cumsum(0.5 * (Q[1:] + Q[:-1]) * np.diff(t_h) * HORA)])
    tabla_t = np.arange(0.0, t_h[-1] + 1e-9, paso_h)
    if tabla_t[-1] < t_h[-1]:
        tabla_t = np.append(tabla_t, t_h[-1])
    theta = np.maximum.accumulate(np.interp(tabla_t, t_h, E) / rho_cp)
    return tuple(float(x) for x in tabla_t), tuple(float(x) for x in theta)
