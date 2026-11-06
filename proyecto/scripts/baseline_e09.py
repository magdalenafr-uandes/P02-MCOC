"""Ejecuta E09 y genera figuras y series de temperatura para la entrega."""

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import yaml

from mcplan.caso import ejecutar_pipeline, leer_config
from pipeline_e07 import HORA, RAIZ, _figura_3d, _imprimir


def exportar_series(resultado, figuras: Path, datos: Path) -> None:
    s, g = resultado.simulacion, resultado.grilla
    x, y, z = [g.definicion.centros(eje) for eje in range(3)]
    i, j = np.abs(x).argmin(), np.abs(y).argmin()
    # Núcleo en V2, extremo lateral a igual cota y coronación del pedestal.
    k = np.abs(z - 0.825).argmin()
    borde = np.flatnonzero(g.vertida_id[:, j, k] > 0)[-1]
    cima = np.flatnonzero(g.vertida_id[i, j, :] > 0)[-1]
    puntos = {"Núcleo": (i, j, k), "Borde lateral": (borde, j, k),
              "Coronación": (i, j, cima)}
    activacion = {p.vertida_id: p.inicio_s for p in resultado.plan}
    tiempos = sorted(s.campos)
    series = {}
    fig, ax = plt.subplots(figsize=(10, 5), layout="constrained")
    ax.plot(np.asarray(s.tiempos_s) / HORA, s.T_max_C, "k", lw=2,
            label="Máximo del hormigón activo")
    for nombre, celda in puntos.items():
        vid = g.vertida_id[celda]
        valores = [float(s.campos[t][celda]) if t >= activacion[vid] else np.nan
                   for t in tiempos]
        series[nombre] = dict(zip(tiempos, valores))
        xyz = tuple(float(eje[n]) for eje, n in zip((x, y, z), celda))
        pico = int(np.nanargmax(valores))
        print(f"{nombre}: V{vid}, xyz={xyz}, máximo {valores[pico]:.2f} °C "
              f"a {tiempos[pico] / HORA:g} h, final {valores[-1]:.2f} °C")
        ax.plot(np.asarray(tiempos) / HORA, valores, label=f"{nombre} (V{vid})")
    for t in sorted(set(activacion.values())):
        ax.axvline(t / HORA, color="0.6", alpha=0.35, lw=0.8)
    ax.set(xlabel="Horas desde la primera vertida", ylabel="Temperatura [°C]",
           title="E09 · Máximo global y tres sondas virtuales", xlim=(0, s.tiempos_s[-1] / HORA))
    ax.grid(alpha=0.2)
    ax.legend()
    fig.savefig(figuras / "e09_temperaturas.png", dpi=160)
    plt.close(fig)

    maximos = dict(zip(s.tiempos_s, s.T_max_C))
    with datos.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["t_h", "T_max_C", "T_nucleo_C", "T_borde_C", "T_coronacion_C"])
        for t in sorted(maximos.keys() | s.campos.keys()):
            valores = [maximos.get(t, np.nan), *(v.get(t, np.nan) for v in series.values())]
            escritor.writerow([f"{t / HORA:g}", *[
                f"{v:.5f}" if np.isfinite(v) else "" for v in valores
            ]])


def main() -> None:
    config = RAIZ / "configs" / "e09_baseline.yaml"
    datos = yaml.safe_load(config.read_text(encoding="utf-8-sig"))
    resultado = ejecutar_pipeline(leer_config(datos, base_rutas=config.parent))
    _imprimir(resultado)
    figuras = RAIZ / "results" / "figures"
    figuras.mkdir(parents=True, exist_ok=True)
    exportar_series(resultado, figuras, RAIZ / "docs" / "e09_temperaturas.csv")
    _figura_3d(resultado, figuras / "e09_cortes.png", [6, 24, 48, 336])


if __name__ == "__main__":
    main()
