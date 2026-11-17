"""Figuras comparables de la extensión, usando únicamente corridas conservadas."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from defensa import RAIZ


def buscar(carpeta, plan, nivel, curva="M1_SS", clima="era5_2025"):
    rutas = list(carpeta.glob(f"{nivel}__{plan}__{curva}__{clima}__*.json"))
    if len(rutas) != 1:
        raise ValueError(f"Se requiere una corrida: {plan}/{nivel}/{curva}/{clima}, encontradas {len(rutas)}")
    return json.loads(rutas[0].read_text(encoding="utf-8"))


def graficar_sensibilidad(larga, destino):
    niveles = {
        "barrido": "0,50 × 0,10",
        "cribado": "0,50 × 0,05",
        "fino": "0,25 × 0,05",
        "confirmacion": "0,20 × 0,05",
        "temporal": "Paso",
        "registro": "Registro",
    }
    datos = {}
    for nivel in niveles:
        rutas = list(larga.glob(f"{nivel}__eps200_T12__M1_SS__era5_2025__*.json"))
        if rutas:
            datos[nivel] = buscar(larga, "eps200_T12", nivel)["delta_C"]
    malla = [n for n in datos if n not in ("temporal", "registro")]
    puntuales = [n for n in datos if n in ("temporal", "registro")]
    posicion = {n: i for i, n in enumerate(datos)}
    fig, ax = plt.subplots(figsize=(8.5, 4), layout="constrained")
    ax.axhline(20, color="#a44436", ls="--", label="Límite 20 °C")
    ax.plot([posicion[n] for n in malla], [datos[n] for n in malla], "o-", color="#087f79",
            label="Sensibilidad espacial")
    if puntuales:
        ax.axvline(len(malla) - .5, color="#b9c4c9", lw=1)
        ax.plot([posicion[n] for n in puntuales], [datos[n] for n in puntuales],
                "D", color="#4e617d", label="Pruebas sobre cribado")
    for n, valor in datos.items():
        ax.annotate(f"{valor:.3f}".replace(".", ","), (posicion[n], valor),
                    xytext=(0, 7 if valor < 19.6 else -18), textcoords="offset points", ha="center")
    ax.set_xticks(list(posicion.values()), [niveles[n] for n in datos])
    ax.set(xlabel="Mallas Δx × Δz [m]  /  Pruebas de paso y registro",
           ylabel="Diferencial máximo [°C]", title="EPS 200 mm · 12 °C · M1_SS · ERA5 2025")
    ax.legend(frameon=False, fontsize=9)
    fig.savefig(destino / "sensibilidad_numerica.png", dpi=190)
    plt.close(fig)


def main():
    larga = RAIZ / "results/defensa_extension_larga"
    corta = RAIZ / "results/defensa_extension"
    destino = RAIZ / "docs/evidencia_extension_defensa/figuras"
    destino.mkdir(parents=True, exist_ok=True)
    fino_200 = list(larga.glob("fino__eps200_T12__M1_SS__era5_2025__*.json"))
    nivel_200 = "fino" if fino_200 else "cribado"
    filas = [
        (buscar(RAIZ / "results/defensa", "unica_poliestireno", "barrido"), "18 °C · EPS 100 mm · barrido", "#88583d"),
        (buscar(corta, "eps100_T12", "fino"), "12 °C · EPS 100 mm · fino", "#b44e4b"),
        (buscar(larga, "eps200_T12", nivel_200), f"12 °C · EPS 200 mm · {nivel_200}" +
         (" (provisional)" if not fino_200 else ""), "#087f79"),
    ]
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.8), layout="constrained")
    for r, nombre, color in filas:
        s = r["series"]
        t = np.asarray(s["t_h"]) / 24
        axes[0].plot(t, s["T_max_C"], color=color, lw=1.8, label=nombre + " · máxima")
        axes[0].plot(t, s["T_superficie_min_C"], color=color, lw=1, ls=":", label=nombre + " · superficie")
        axes[1].plot(t, s["delta_C"], color=color, lw=1.8, label=nombre)
    for ax, limite, ylabel in zip(axes, (70, 20), ("Temperatura [°C]", "Diferencial global a 25 mm [°C]")):
        ax.axhline(limite, color="#333333", ls="--", lw=1, label=f"Límite {limite} °C")
        ax.set(xlabel="Días desde 19/11/2026 04:00 · America/Santiago", ylabel=ylabel, xlim=(0, 28))
        ax.grid(axis="y", alpha=.2)
        ax.legend(loc="upper center", bbox_to_anchor=(.5, -.21), fontsize=8, frameon=False, ncol=2 if ax is axes[0] else 1)
    fig.suptitle("M1_SS · ERA5 2025 · mismo volumen, caudal y duración física")
    fig.savefig(destino / "comparacion_control.png", dpi=190)
    plt.close(fig)
    graficar_sensibilidad(larga, destino)
    print(destino)


if __name__ == "__main__":
    main()
