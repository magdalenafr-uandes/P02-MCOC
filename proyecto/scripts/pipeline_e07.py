"""Pipeline E07/E08: IFC -> voxeles -> simulación térmica por etapas.

Todo parámetro sale del YAML; ``--set`` lo cambia sin editar archivos ni código.

Uso:
    python scripts/pipeline_e07.py
    python scripts/pipeline_e07.py --set malla.paso_m=0.2 --set vertidas.3.T_colocacion_C=12
    python scripts/pipeline_e07.py --solo-grilla --set malla.paso_m=0.05
    python scripts/pipeline_e07.py --figura results/figures/e07_pipeline.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import yaml

from mcplan.caso import ErrorConfiguracion, aplicar_sobrescrituras, ejecutar_pipeline, leer_config

RAIZ = Path(__file__).resolve().parents[1]
HORA = 3600.0


def _imprimir(r) -> None:
    c, g = r.config, r.grilla
    print(f"IFC: {c.ruta_ifc}")
    dx, _, dz = g.paso
    print(f"Grilla: {g.forma} = {np.prod(g.forma):,} voxeles, Δx = Δy = {dx:g} m, Δz = {dz:g} m, "
          f"{g.definicion.n_suelo} capas de suelo, solapados = {g.voxeles_solapados}")
    print("\nPlan de vertidas (valor [origen]):")
    for p in r.plan:
        o = p.origen
        retiro = "nunca" if np.isinf(p.retiro_moldaje_s) else f"{p.retiro_moldaje_s / HORA:g} h"
        print(f"  {p.vertida_id} {p.nombre:11s} visible={p.visible!s:5s} "
              f"inicio={p.inicio_s / HORA:g} h [{o.get('inicio_h')}]  "
              f"T_col={p.T_colocacion_C:g} °C [{o.get('T_colocacion_C')}]  "
              f"{p.hormigon} [{o.get('hormigon')}]  retiro={retiro}  "
              f"R_lat={p.R_lateral:g} R_sup={p.R_superior:g}")
    print("\nVolumen (G04):  vertida   V_malla [m³]   V_h [m³]   e_V")
    for f in r.volumetria:
        print(f"                {f['vertida_id']:5d}   {f['V_malla_m3']:12.3f}   {f['V_h_m3']:8.3f}   {f['e_V']:.2%}")
    V = sum(f["V_malla_m3"] for f in r.volumetria)
    Vh = sum(f["V_h_m3"] for f in r.volumetria)
    print(f"                total   {V:12.3f}   {Vh:8.3f}   {abs(Vh - V) / V:.2%}")
    a, ac = r.area_exterior_m2, r.area_exterior_corregida_m2
    usada = "corregida" if c.malla.corregir_area else "staircase"
    print(f"\nSuperficie exterior del hormigón [m²]   lateral  superior  total")
    print(f"  staircase (|nx|+|ny|+|nz|)·A      {a['lateral']:8.1f}  {a['superior']:8.1f}  {a['total']:6.1f}")
    print(f"  corregida (w = 1/||n||₁)          {ac['lateral']:8.1f}  {ac['superior']:8.1f}  {ac['total']:6.1f}")
    print(f"  convección calculada con el área {usada} (malla.corregir_area = {c.malla.corregir_area})")

    s = r.simulacion
    if s is None:
        return
    print("\nEtapas:")
    for e in s.etapas:
        nuevas = f" activa {e['nuevas']}" if e["nuevas"] else ""
        print(f"  {e['t0_s'] / HORA:6.1f}-{e['t1_s'] / HORA:6.1f} h: {e['pasos']:4d} pasos, "
              f"dt = {e['dt_s']:.0f} s (límite monótono {e['dt_limite_s']:.0f} s){nuevas}")
    print("\nPicos por vertida:")
    for vid in sorted(s.T_max_vertida_C):
        T, t = s.pico(vid)
        print(f"  {vid}: T_max = {T:.2f} °C a las {t / HORA:.1f} h")
    dT = s.delta_T_C
    i = int(np.nanargmax(dT))
    print(f"T_max global = {np.nanmax(s.T_max_C):.2f} °C;  ΔT núcleo-superficie máx = {dT[i]:.2f} °C "
          f"a las {s.tiempos_s[i] / HORA:.1f} h (T de la cara expuesta)")
    b = s.balance
    print(f"Balance de energía: residuo = {b['residuo_J']:.3e} J "
          f"({abs(b['residuo_J']) / max(abs(b['E_final_J']), 1.0):.1e} relativo); "
          f"hidratación {b['hidratacion_J']:.3e} J, ambiente {b['ambiente_J']:.3e} J, base {b['base_J']:.3e} J")


def _figura(r, salida: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    s, g = r.simulacion, r.grilla
    t = np.asarray(s.tiempos_s) / HORA
    fig, ejes = plt.subplots(1, 2, figsize=(14, 5), layout="constrained")
    for vid, serie in sorted(s.T_max_vertida_C.items()):
        ejes[0].plot(t, serie, label=f"T_max vertida {vid}")
    ejes[0].plot(t, s.T_sup_min_C, "k--", label="T mínima en superficie")
    ejes[0].set_xlabel("t [h]")
    ejes[0].set_ylabel("T [°C]")
    ejes[0].set_title("Temperaturas por vertida")
    ejes[0].legend(fontsize=8)
    ejes[0].grid(alpha=0.3)

    j = g.forma[1] // 2
    T = np.where(s.activo_final | g.es_suelo, s.T_final, np.nan)[:, j, :]
    x0, z0 = g.definicion.origen[0], g.definicion.origen[2]
    extension = [x0, x0 + g.forma[0] * g.paso[0], z0, z0 + g.forma[2] * g.paso[2]]
    im = ejes[1].imshow(T.T, origin="lower", extent=extension, cmap="inferno", aspect="equal")
    fig.colorbar(im, ax=ejes[1], label="T [°C]")
    ejes[1].set_xlabel("x [m]")
    ejes[1].set_ylabel("z [m]")
    ejes[1].set_title(f"Corte central y = 0 a t = {t[-1]:.0f} h (suelo bajo z = 0)")
    fig.suptitle(f"Pipeline E07: Δx = Δy = {g.paso[0]:g} m, Δz = {g.paso[2]:g} m; "
                 f"parámetros desde {r.config.ruta_ifc.name} + YAML")
    salida.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(salida, dpi=150)
    plt.close(fig)
    print(f"\nFigura: {salida}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", type=Path, default=RAIZ / "configs" / "e07_caso_base.yaml")
    p.add_argument("--set", dest="sobrescrituras", action="append", default=[], metavar="CLAVE=VALOR",
                   help="Sobrescribe un parámetro del YAML (repetible).")
    p.add_argument("--solo-grilla", action="store_true", help="Voxeliza sin simular.")
    p.add_argument("--figura", type=Path, help="Guarda historia de temperaturas y corte final (PNG).")
    a = p.parse_args(argv)
    try:
        datos = yaml.safe_load(a.config.read_text(encoding="utf-8")) or {}
        datos = aplicar_sobrescrituras(datos, a.sobrescrituras)
        config = leer_config(datos, base_rutas=a.config.parent)
        resultado = ejecutar_pipeline(config, simular=not a.solo_grilla)
    except (ErrorConfiguracion, FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    _imprimir(resultado)
    if a.figura and resultado.simulacion is not None:
        _figura(resultado, a.figura)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
