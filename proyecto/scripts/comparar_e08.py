"""Compara dos corridas del pipeline que solo difieren en los inputs (E08).

Muestra el efecto de un cambio pedido en el laboratorio (Δx, ocultar una
vertida, hora de inicio, T de colocación...) sin tocar el código: las dos
corridas usan el mismo YAML y difieren solo en ``--variante``.

Uso:
    python scripts/comparar_e08.py --variante vertidas.2.T_colocacion_C=10
    python scripts/comparar_e08.py --variante vertidas.5.visible=false
    python scripts/comparar_e08.py --variante vertidas.3.inicio_h=30 --comun simulacion.duracion_h=96
    python scripts/comparar_e08.py --variante malla.paso_m=0.25 --base malla.paso_m=0.5

Por defecto ambas corridas usan el modo rápido (Δx = 0,5 m, 72 h; ~12 s cada
una); ``--completo`` usa el YAML tal cual (Δx = 0,25 m, 14 días).
"""

from __future__ import annotations

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import argparse
import sys
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_e07 import HORA, RAIZ  # noqa: E402

from mcplan.caso import ErrorConfiguracion, aplicar_sobrescrituras, ejecutar_pipeline, leer_config  # noqa: E402

RAPIDO = ["malla.paso_m=0.5", "simulacion.duracion_h=72"]


def delta_T_por_vertida_en_el_tiempo(s) -> np.ndarray:
    series = np.array([s.delta_T_vertida_C(v) for v in sorted(s.T_max_vertida_C)])
    with np.errstate(all="ignore"):
        return np.nanmax(np.where(np.isnan(series), -np.inf, series), axis=0)


def correr(config: Path, cambios: list[str]):
    datos = aplicar_sobrescrituras(yaml.safe_load(config.read_text(encoding="utf-8")), cambios)
    return ejecutar_pipeline(leer_config(datos, base_rutas=config.parent))


def resumen(nombre: str, r) -> dict[str, float]:
    s = r.simulacion
    dTv, vid, t_dT = s.delta_T_max_por_vertida()
    V = sum(f["V_malla_m3"] for f in r.volumetria)
    Vh = sum(f["V_h_m3"] for f in r.volumetria)
    fila = {"T_max": float(np.nanmax(s.T_max_C)), "dT": dTv, "e_V": 100 * abs(Vh - V) / V,
            "visibles": [p.vertida_id for p in r.plan if p.visible]}
    for vid_ in sorted(s.T_max_vertida_C):
        fila[f"pico_{vid_}"] = s.pico(vid_)
    print(f"{nombre:9s} visibles {fila['visibles']}  T_max {fila['T_max']:6.2f} °C  "
          f"ΔT {fila['dT']:6.2f} °C (vertida {vid}, {t_dT / HORA:.0f} h)  e_V {fila['e_V']:.2f} %")
    for aviso in s.advertencias:
        print(f"          ADVERTENCIA: {aviso}")
    return fila


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, default=RAIZ / "configs" / "e07_caso_base.yaml")
    ap.add_argument("--variante", action="append", default=[], metavar="CLAVE=VALOR", required=True)
    ap.add_argument("--base", action="append", default=[], metavar="CLAVE=VALOR",
                    help="Cambios solo del caso base (por defecto ninguno).")
    ap.add_argument("--comun", action="append", default=[], metavar="CLAVE=VALOR",
                    help="Cambios de ambas corridas.")
    ap.add_argument("--completo", action="store_true", help="Sin modo rápido: YAML tal cual.")
    ap.add_argument("--instante", type=float, metavar="H", help="Hora del corte 3D (por defecto el final).")
    ap.add_argument("--salida", type=Path, default=RAIZ / "results" / "figures" / "e08_comparacion.png")
    a = ap.parse_args(argv)
    comun = ([] if a.completo else RAPIDO) + ["simulacion.guardar_campos_cada_h=3"] + a.comun
    try:
        print(f"Común: {comun}\nBase: {a.base or '(YAML)'}\nVariante: {a.variante}\n")
        rb = correr(a.config, comun + a.base)
        rv = correr(a.config, comun + a.base + a.variante)
    except (ErrorConfiguracion, FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    fb, fv = resumen("base", rb), resumen("variante", rv)
    print(f"\nEfecto: T_max {fv['T_max'] - fb['T_max']:+.2f} °C, ΔT {fv['dT'] - fb['dT']:+.2f} °C")
    for vid in sorted(set(rb.simulacion.T_max_vertida_C) & set(rv.simulacion.T_max_vertida_C)):
        (Tb, tb), (Tv, tv) = fb[f"pico_{vid}"], fv[f"pico_{vid}"]
        if not (np.isnan(Tb) and np.isnan(Tv)):
            print(f"  vertida {vid}: pico {Tb:6.2f} -> {Tv:6.2f} °C ({Tv - Tb:+.2f}), "
                  f"a las {tb / HORA:5.1f} -> {tv / HORA:5.1f} h")

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize

    from mcplan.visualizacion import activo_en, dibujar_3d

    fig = plt.figure(figsize=(16, 10), layout="constrained")
    ax1 = fig.add_subplot(2, 2, 1)
    for n, (vid, serie) in enumerate(sorted(rb.simulacion.T_max_vertida_C.items())):
        color = plt.get_cmap("tab10")(n % 10)
        ax1.plot(np.asarray(rb.simulacion.tiempos_s) / HORA, serie, color=color, label=f"V{vid} base")
        if vid in rv.simulacion.T_max_vertida_C:
            ax1.plot(np.asarray(rv.simulacion.tiempos_s) / HORA, rv.simulacion.T_max_vertida_C[vid], "--",
                     color=color, label=f"V{vid} variante")
    ax1.set(xlabel="t [h]", ylabel="T_max de la vertida [°C]", title="Pico por vertida: base (—) vs variante (--)")
    ax1.legend(fontsize=7, ncol=2)
    ax1.grid(alpha=0.3)
    ax2 = fig.add_subplot(2, 2, 2)
    for r, estilo, nombre in ((rb, "-", "base"), (rv, "--", "variante")):
        ax2.plot(np.asarray(r.simulacion.tiempos_s) / HORA, delta_T_por_vertida_en_el_tiempo(r.simulacion),
                 estilo, color="k", label=nombre)
    if rb.config.criterios:
        ax2.axhline(rb.config.criterios.delta_T_C, color="r", lw=0.8, label="criterio")
    ax2.set(xlabel="t [h]", ylabel="ΔT núcleo-superficie [°C]", title="ΔT máximo dentro de cada vertida")
    ax2.legend()
    ax2.grid(alpha=0.3)

    instantes = []
    for r in (rb, rv):
        guardados = np.array(sorted(r.simulacion.campos))
        t = guardados[-1] if a.instante is None else guardados[np.argmin(abs(guardados - a.instante * HORA))]
        instantes.append(float(t))
    valores = [r.simulacion.campos[t][activo_en(r.grilla, r.plan, t)] for r, t in zip((rb, rv), instantes)]
    norm = Normalize(min(float(v.min()) for v in valores if v.size), max(float(v.max()) for v in valores if v.size))
    cmap = plt.get_cmap("inferno")
    for n, (r, t, nombre) in enumerate(zip((rb, rv), instantes, ("base", "variante")), start=3):
        ax = fig.add_subplot(2, 2, n, projection="3d")
        dibujar_3d(ax, r.grilla, r.simulacion.campos[t], activo_en(r.grilla, r.plan, t), cmap, norm,
                   titulo=f"{nombre}: t = {t / HORA:.0f} h (corte y = 0)")
    fig.colorbar(plt.cm.ScalarMappable(norm, cmap), ax=fig.axes[-1], shrink=0.6, label="T [°C]")
    fig.suptitle(f"Efecto de {' '.join(a.variante)}  (mismo solver; solo cambian los inputs)", fontsize=12)
    a.salida.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(a.salida, dpi=110)
    plt.close(fig)
    print(f"\nFigura: {a.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
