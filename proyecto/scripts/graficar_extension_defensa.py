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
    niveles = ("barrido", "cribado", "fino", "confirmacion", "temporal", "registro")
    datos = []
    for nivel in niveles:
        rutas = list(larga.glob(f"{nivel}__eps200_T12__M1_SS__era5_2025__*.json"))
        if rutas:
            r = json.loads(rutas[0].read_text(encoding="utf-8"))
            datos.append((nivel, r["delta_C"]))
    fig, ax = plt.subplots(figsize=(8.5, 4), layout="constrained")
    ax.axhline(20, color="#a44436", ls="--", label="Límite 20 °C")
    ax.plot([n for n, _ in datos], [v for _, v in datos], "o-", color="#087f79")
    for i, (_, valor) in enumerate(datos):
        ax.annotate(f"{valor:.3f}", (i, valor), xytext=(0, -16), textcoords="offset points", ha="center")
    ax.set(ylabel="Diferencial máximo [°C]", title="EPS 200 mm · 12 °C · M1_SS · ERA5 2025")
    ax.legend(frameon=False)
    fig.savefig(destino / "sensibilidad_numerica.png", dpi=190)
    plt.close(fig)
    print(destino)


if __name__ == "__main__":
    main()
