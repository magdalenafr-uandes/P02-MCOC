"""Modelo adiabático exponencial ajustable, sin dependencia de temperatura.

T_ad(edad) = incremento_K * (1 - exp(-edad / escala_s)).
La edad se mide desde la colocación, en segundos. qdot es potencia por
volumen de hormigón [W/m³], no potencia total [W]. Una futura extensión
por edad equivalente debe integrar su tasa con temperatura absoluta y
parámetros experimentales; este modelo no incorpora ese efecto.
"""
from dataclasses import dataclass
from pathlib import Path
import csv
import hashlib
import numpy as np


@dataclass(frozen=True)
class HidratacionAdiabatica:
    incremento_K: float
    escala_s: float

    def __post_init__(self):
        if not np.isfinite([self.incremento_K, self.escala_s]).all() or self.incremento_K < 0 or self.escala_s <= 0:
            raise ValueError('Incremento no negativo y escala positiva, ambos finitos.')

    def incremento(self, edad_s):
        edad = np.asarray(edad_s, dtype=float)
        if not np.isfinite(edad).all() or np.any(edad < 0):
            raise ValueError('La edad debe ser no negativa y finita.')
        return self.incremento_K * (-np.expm1(-edad / self.escala_s))

    def qdot(self, edad_s, rho: float, cp: float):
        """rho [kg/m³] cp [J/(kg K)] dT_ad/dedad [K/s] -> W/m³."""
        self.incremento(edad_s)  # valida edades
        if not np.isfinite([rho, cp]).all() or rho <= 0 or cp <= 0:
            raise ValueError('rho y cp deben ser positivos finitos.')
        return rho * cp * self.incremento_K / self.escala_s * np.exp(-np.asarray(edad_s)/self.escala_s)

    def incremento_paso(self, edad_s, dt_s: float):
        """Integral exacta de la curva durante el paso, expresada en K."""
        self.incremento(edad_s)
        if not np.isfinite(dt_s) or dt_s < 0:
            raise ValueError('dt debe ser no negativo y finito.')
        return self.incremento_K * np.exp(-np.asarray(edad_s)/self.escala_s) * (-np.expm1(-dt_s/self.escala_s))


@dataclass(frozen=True)
class AjusteAdiabatico:
    modelo: HidratacionAdiabatica
    rmse_K: float
    error_max_K: float
    advertencias: tuple[str, ...]


def ajustar_curva(edad_s, incremento_K) -> AjusteAdiabatico:
    """Mínimos cuadrados en K; ajusta incremento final y escala, no k/rho/cp.

    Se elimina analíticamente la amplitud para cada escala y se minimiza
    en log(escala) por sección áurea. No requiere SciPy. El CSV debe ser
    elevación adiabática desde la colocación, nunca temperatura absoluta
    ni un ensayo semiadiabático sin corrección de pérdidas.
    """
    t, y = np.asarray(edad_s, float), np.asarray(incremento_K, float)
    if t.ndim != 1 or y.shape != t.shape or not np.isfinite(t).all() or not np.isfinite(y).all():
        raise ValueError('Edades e incrementos deben ser vectores finitos de igual longitud.')
    orden = np.argsort(t)
    t, y = t[orden], y[orden]
    if len(t) < 4 or np.any(t < 0) or np.any(y < 0) or np.any(np.diff(t) <= 0) or np.count_nonzero(t > 0) < 3:
        raise ValueError('Se requieren >=4 edades únicas, >=3 positivas e incrementos no negativos.')
    if np.any((t == 0) & (y != 0)) or y.max() <= 0:
        raise ValueError('La elevación inicial debe ser cero y la curva debe generar calor.')

    def objetivo(log_escala):
        f = -np.expm1(-t / np.exp(log_escala))
        amplitud = float(f @ y / (f @ f))
        return float(np.sum((amplitud*f-y)**2)), amplitud

    logs = np.linspace(np.log(t[t > 0].min()/100), np.log(t.max()*1e4), 161)
    valores = [objetivo(v)[0] for v in logs]
    indice = int(np.argmin(valores))
    if indice in (0, len(logs)-1):
        raise ValueError('La curva no identifica una escala de hidratación dentro del rango de ajuste.')
    a, b = logs[indice-1], logs[indice+1]
    razon = (np.sqrt(5)-1)/2
    c, d = b-razon*(b-a), a+razon*(b-a)
    for _ in range(100):
        if objetivo(c)[0] < objetivo(d)[0]:
            b, d = d, c
            c = b-razon*(b-a)
        else:
            a, c = c, d
            d = a+razon*(b-a)
    log_escala = (a+b)/2
    _, amplitud = objetivo(log_escala)
    modelo = HidratacionAdiabatica(amplitud, float(np.exp(log_escala)))
    residuo = modelo.incremento(t)-y
    avisos = []
    if t.max() < 3*modelo.escala_s:
        avisos.append('La curva no llega a tres escalas: el incremento final es una extrapolación poco restringida.')
    if float(np.sqrt(np.mean(residuo**2))) > .05*max(float(y.max()), 1.):
        avisos.append('RMSE >5% del incremento observado: revisar si el modelo exponencial es adecuado.')
    return AjusteAdiabatico(modelo, float(np.sqrt(np.mean(residuo**2))), float(abs(residuo).max()), tuple(avisos))


def ajustar_csv(ruta: str | Path) -> tuple[AjusteAdiabatico, dict]:
    """Columnas obligatorias edad_h,incremento_K; separador coma, UTF-8."""
    ruta = Path(ruta)
    with ruta.open(encoding='utf-8-sig', newline='') as archivo:
        lector = csv.DictReader(archivo)
        if lector.fieldnames != ['edad_h', 'incremento_K']:
            raise ValueError('Cabecera requerida: edad_h,incremento_K.')
        try:
            datos = [(float(f['edad_h'])*3600, float(f['incremento_K'])) for f in lector]
        except (TypeError, ValueError) as exc:
            raise ValueError('El CSV contiene una fila no numérica o incompleta.') from exc
    if not datos:
        raise ValueError('La curva CSV está vacía.')
    t, y = np.asarray(datos).T
    ajuste = ajustar_curva(t, y)
    return ajuste, dict(archivo=str(ruta.resolve()), sha256=hashlib.sha256(ruta.read_bytes()).hexdigest(),
                        muestras=len(t), rmse_K=ajuste.rmse_K, error_max_K=ajuste.error_max_K,
                        advertencias=list(ajuste.advertencias))
