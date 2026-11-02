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
    inicio = f"{c.inicio:%Y-%m-%d %H:%M}" if c.inicio else "sin fecha (t relativo)"
    print(f"Inicio (t = 0): {inicio};  clima: {c.nota_clima}")
    hid = {n: h.hidratacion for n, h in c.hormigones.items()}
    for n, m in hid.items():
        if m is not None:
            print(f"Hidratación {n}: modelo {m.modelo}, θ∞ = {m.theta_inf_C:.1f} K "
                  f"(Q∞ = {m.calor_total_J_m3 / 1e6:.0f} MJ/m³), Ea = {m.Ea_J_mol:g} J/mol")
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
    ocultas = {p.vertida_id for p in r.plan if not p.visible}
    print("\nVolumen (G04):  vertida   V_malla [m³]   V_h [m³]   e_V")
    for f in r.volumetria:
        nota = "   (oculta: no se activa)" if f["vertida_id"] in ocultas else ""
        print(f"                {f['vertida_id']:5d}   {f['V_malla_m3']:12.3f}   {f['V_h_m3']:8.3f}   "
              f"{f['e_V']:.2%}{nota}")
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
    cr = c.criterios
    prof = f"a {cr.profundidad_superficie_m * 1000:g} mm bajo la cara" if cr else "en la cara"
    dTv, vid_dT, t_dT = s.delta_T_max_por_vertida()
    print(f"T_max global = {np.nanmax(s.T_max_C):.2f} °C")
    print(f"ΔT núcleo-superficie (superficie {prof}):")
    for vid in sorted(s.T_max_vertida_C):
        serie = s.delta_T_vertida_C(vid)
        if not np.all(np.isnan(serie)):
            j = int(np.nanargmax(serie))
            print(f"  vertida {vid}: máx {serie[j]:6.2f} °C a las {s.tiempos_s[j] / HORA:6.1f} h")
    print(f"  global (núcleo de una vertida vs. superficie de otra; cota conservadora): "
          f"{dT[i]:.2f} °C a las {s.tiempos_s[i] / HORA:.1f} h")
    if cr:
        T_max = float(np.nanmax(s.T_max_C))
        dias = s.tiempos_s[-1] / 86400.0
        print(f"\nCriterios docentes (hoja de ruta; no normativos), {dias:g} días simulados:")
        for nombre, valor, limite in (("T_max", T_max, cr.T_max_C),
                                      (f"ΔT (vertida {vid_dT})", dTv, cr.delta_T_C)):
            estado = "cumple" if valor <= limite else "NO cumple"
            print(f"  {nombre:21s} {valor:6.2f} °C  límite {limite:g} °C  -> {estado} (margen {limite - valor:+.2f} °C)")
        if dias < 14.0 - 1e-9:
            print("  ATENCIÓN: el criterio se evalúa sobre los máximos de 14 días; esta corrida es más corta.")
        print("  Incertidumbre de discretización (convergencia en Δx): ±0,2 °C en T_max, ~1 °C en ΔT.")
    for aviso in s.advertencias:
        print(f"ADVERTENCIA (plan no construible tal cual): {aviso}")
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


def instantes_automaticos(r) -> list[float]:
    """Segunda vertida recién colocada, última recién colocada, pico de T y final [s]."""
    s = r.simulacion
    inicios = sorted({p.inicio_s for p in r.plan if p.visible and p.inicio_s < r.config.tiempo.duracion_s})
    elegidos = []
    if len(inicios) > 1:
        elegidos.append(inicios[1] + HORA)
    elegidos.append(inicios[-1] + HORA)
    elegidos.append(s.tiempos_s[int(np.nanargmax(s.T_max_C))])
    elegidos.append(s.tiempos_s[-1])
    return sorted({min(t, s.tiempos_s[-1]) for t in elegidos})


def _figura_3d(r, salida: Path, instantes_h: list[float] | None) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm, ListedColormap, Normalize

    from mcplan.visualizacion import activo_en, dibujar_3d

    g, s = r.grilla, r.simulacion
    visibles = [p for p in r.plan if p.visible]
    hormigon = np.isin(g.vertida_id, [p.vertida_id for p in visibles])
    paneles = 1
    instantes = []
    if s is not None:
        pedidos = [h * HORA for h in instantes_h] if instantes_h else instantes_automaticos(r)
        guardados = np.array(sorted(s.campos))
        # primer campo guardado en o después del instante pedido (si no hay, el último)
        instantes = sorted({float(guardados[guardados >= t - 1e-9][0]) if np.any(guardados >= t - 1e-9)
                            else float(guardados[-1]) for t in pedidos})
        paneles += len(instantes)
    columnas = min(paneles, 3)
    filas = -(-paneles // columnas)
    fig = plt.figure(figsize=(6.2 * columnas, 4.6 * filas), layout="constrained")

    ids_visibles = sorted(p.vertida_id for p in visibles)
    colores = plt.get_cmap("tab10")(np.arange(len(ids_visibles)) % 10)
    mapa_ids = np.zeros(g.forma)
    for n, vid in enumerate(ids_visibles):
        mapa_ids[g.vertida_id == vid] = n
    cmap_ids = ListedColormap(colores)
    norm_ids = BoundaryNorm(np.arange(len(ids_visibles) + 1) - 0.5, len(ids_visibles))
    ax = fig.add_subplot(filas, columnas, 1, projection="3d")
    dibujar_3d(ax, g, mapa_ids, hormigon, cmap_ids, norm_ids,
               titulo=f"vertida_id (visibles: {ids_visibles})\nΔx = {g.paso[0]:g} m, Δz = {g.paso[2]:g} m")
    fig.colorbar(plt.cm.ScalarMappable(norm_ids, cmap_ids), ax=ax, shrink=0.5, ticks=range(len(ids_visibles)),
                 format=lambda x, _: f"V{ids_visibles[int(x)]}" if 0 <= int(x) < len(ids_visibles) else "")

    if instantes:
        T_vals = np.concatenate([s.campos[t][activo_en(g, r.plan, t)] for t in instantes])
        norm = Normalize(float(T_vals.min()), float(T_vals.max()))
        cmap = plt.get_cmap("inferno")
        for n, t in enumerate(instantes, start=2):
            ax = fig.add_subplot(filas, columnas, n, projection="3d")
            activas = sorted(p.vertida_id for p in visibles if p.inicio_s <= t + 1e-9)
            fecha = f" ({r.config.inicio + __import__('datetime').timedelta(seconds=t):%d-%b %H:%M})" if r.config.inicio else ""
            dibujar_3d(ax, g, s.campos[t], activo_en(g, r.plan, t), cmap, norm,
                       titulo=f"t = {t / HORA:.0f} h{fecha}\nactivas: {activas}")
        fig.colorbar(plt.cm.ScalarMappable(norm, cmap), ax=fig.axes[-1], shrink=0.5, label="T [°C]")
    fig.suptitle("Fundación voxelizada (media fundación, corte en y = 0; z exagerada ×2) y temperatura por etapas", fontsize=12)
    salida.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(salida, dpi=110)
    plt.close(fig)
    print(f"Figura 3D: {salida}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", type=Path, default=RAIZ / "configs" / "e07_caso_base.yaml")
    p.add_argument("--set", dest="sobrescrituras", action="append", default=[], metavar="CLAVE=VALOR",
                   help="Sobrescribe un parámetro del YAML (repetible).")
    p.add_argument("--solo-grilla", action="store_true", help="Voxeliza sin simular.")
    p.add_argument("--figura", type=Path, help="Guarda historia de temperaturas y corte final (PNG).")
    p.add_argument("--figura3d", type=Path, help="Figura 3D: vertida_id y temperatura en varios instantes (PNG).")
    p.add_argument("--instantes", type=float, nargs="+", metavar="H",
                   help="Horas de los paneles 3D (por defecto: activaciones, pico y final).")
    p.add_argument("--vtk", type=Path, metavar="CARPETA", help="Serie .vti + .pvd para ParaView.")
    a = p.parse_args(argv)
    try:
        datos = yaml.safe_load(a.config.read_text(encoding="utf-8")) or {}
        if (a.figura3d or a.vtk) and not a.solo_grilla:
            # Campos 3D cada 3 h salvo que la config o --set digan otra cosa.
            datos = aplicar_sobrescrituras(datos, ["simulacion.guardar_campos_cada_h=3"])
        datos = aplicar_sobrescrituras(datos, a.sobrescrituras)
        config = leer_config(datos, base_rutas=a.config.parent)
        resultado = ejecutar_pipeline(config, simular=not a.solo_grilla)
    except (ErrorConfiguracion, FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    _imprimir(resultado)
    if a.figura and resultado.simulacion is not None:
        _figura(resultado, a.figura)
    if a.figura3d:
        _figura_3d(resultado, a.figura3d, a.instantes)
    if a.vtk and resultado.simulacion is not None:
        from mcplan.visualizacion import escribir_serie_vtk

        pvd = escribir_serie_vtk(a.vtk, resultado.grilla, resultado.plan, resultado.simulacion)
        print(f"VTK: {pvd} ({len(resultado.simulacion.campos)} instantes; abrir el .pvd en ParaView)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
