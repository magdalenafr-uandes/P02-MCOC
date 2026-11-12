"""E12: caso determinista completo de 14 días y su diagnóstico térmico.

Desde proyecto/:
    .venv\\Scripts\\python.exe scripts\\e12_determinista.py            # caso base + variante sin tuberías
    .venv\\Scripts\\python.exe scripts\\e12_determinista.py --rapido   # Δx = 0,5 m (prueba, ~1 min)
    .venv\\Scripts\\python.exe scripts\\e12_determinista.py --abrir    # además, ventana PyVista interactiva

Usa configs/e07_caso_base.yaml sin cambios (malla, clima, curva, suelo, moldaje,
tuberías). Salidas regenerables en results/e12/ (VTK, CSV); la evidencia liviana
(figuras y resumen.json) en results/figures/e12_*.png y docs/evidencia_e12/.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import yaml

from mcplan.caso import aplicar_sobrescrituras, ejecutar_pipeline, leer_config

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = RAIZ / "configs" / "e07_caso_base.yaml"
HORA = 3600.0


def configurar(extra: list[str]):
    datos = yaml.safe_load(CONFIG.read_text(encoding="utf-8-sig"))
    datos = aplicar_sobrescrituras(datos, extra)
    return datos, leer_config(datos, base_rutas=CONFIG.parent)


def centro(r, idx: int) -> list[float]:
    g = r.grilla
    ijk = np.unravel_index(idx, g.forma)
    return [float(g.definicion.origen[a] + (ijk[a] + 0.5) * g.paso[a]) for a in range(3)]


def describir(r, idx: int) -> dict:
    """Celda -> coordenadas, vertida y posición dentro de la pieza (profundidad bajo su cara superior)."""
    g = r.grilla
    i, j, k = np.unravel_index(idx, g.forma)
    vid = int(g.vertida_id[i, j, k])
    columna = np.nonzero(np.isin(g.vertida_id[i, j, :], [p.vertida_id for p in r.plan if p.visible]))[0]
    tope = g.definicion.origen[2] + (columna.max() + 1) * g.paso[2]
    x, y, z = centro(r, idx)
    return dict(celda=int(idx), ijk=[int(i), int(j), int(k)], xyz_m=[round(x, 3), round(y, 3), round(z, 3)],
                vertida=vid, radio_m=round(float(np.hypot(x, y)), 3),
                prof_bajo_cara_superior_m=round(float(tope - z), 3))


def fecha(c, t_s: float) -> str:
    return (c.inicio + timedelta(seconds=float(t_s))).strftime("%d-%b %H:%M")


def diagnosticar(r) -> dict:
    s, c = r.simulacion, r.config
    t = np.asarray(s.tiempos_s)
    # T_max: el máximo de todas las vertidas y su celda
    mejor = max(((s.pico(v), v) for v in s.T_max_vertida_C), key=lambda x: x[0][0])
    (Tmax, tTmax), vT = mejor
    iT = int(np.nonzero(t == tTmax)[0][0])
    # ΔT por vertida (criterio de la misma pieza): núcleo y superficie a 25 mm
    dT, vdT, tdT = s.delta_T_max_por_vertida()
    idT = int(np.nonzero(t == tdT)[0][0])
    por_vertida = {}
    for v in sorted(s.T_max_vertida_C):
        Tv, tv = s.pico(v)
        serie = s.delta_T_vertida_C(v)
        j = int(np.nanargmax(serie))
        por_vertida[v] = dict(T_max_C=round(Tv, 2), t_T_max_h=round(tv / HORA, 1),
                              dT_max_C=round(float(serie[j]), 2), t_dT_max_h=round(t[j] / HORA, 1))
    cr = c.criterios
    return dict(
        T_max=dict(valor_C=round(Tmax, 2), t_h=round(tTmax / HORA, 1), fecha=fecha(c, tTmax),
                   limite_C=cr.T_max_C, cumple=bool(Tmax <= cr.T_max_C),
                   ubicacion=describir(r, s.idx_max_vertida[vT][iT])),
        dT_max=dict(valor_C=round(dT, 2), t_h=round(tdT / HORA, 1), fecha=fecha(c, tdT), vertida=vdT,
                    limite_C=cr.delta_T_C, cumple=bool(dT <= cr.delta_T_C),
                    T_nucleo_C=round(s.T_max_vertida_C[vdT][idT], 2),
                    T_superficie_C=round(s.T_sup_min_vertida_C[vdT][idT], 2),
                    nucleo=describir(r, s.idx_max_vertida[vdT][idT]),
                    superficie=dict(describir(r, s.idx_sup_vertida[vdT][idT]), cara=s.cara_sup_vertida[vdT][idT],
                                    profundidad_m=cr.profundidad_superficie_m)),
        por_vertida=por_vertida,
        T_max_final_C=round(float(s.T_max_C[-1]), 2),
        balance_GJ={k[:-2]: round(v / 1e9, 2) for k, v in s.balance.items() if k.endswith("_J")},
        residuo_relativo=float(abs(s.balance["residuo_J"]) / abs(s.balance["E_final_J"])),
        tuberias_GJ={k: round(v / 1e9, 2) for k, v in s.energia_por_tuberia_J.items()},
    )


def figura_curvas(r, sin_tub, salida: Path) -> None:
    s, c = r.simulacion, r.config
    t = [c.inicio + timedelta(seconds=x) for x in s.tiempos_s]
    aire = [c.ambiente.temperatura(x) for x in s.tiempos_s]
    fig, ejes = plt.subplots(3, 1, figsize=(12, 11), sharex=True, layout="constrained")
    colores = plt.get_cmap("tab10")
    ax = ejes[0]
    ax.plot(t, aire, color="0.6", lw=0.8, label="Aire (forecast + respaldo)")
    for n, v in enumerate(sorted(s.T_max_vertida_C)):
        ax.plot(t, s.T_max_vertida_C[v], color=colores(n), label=f"V{v} núcleo (T máx)")
        ax.plot(t, s.T_sup_min_vertida_C[v], color=colores(n), ls="--", lw=0.9, label=f"V{v} superficie 25 mm (mín)")
    ax.axhline(c.criterios.T_max_C, color="r", ls=":", label="Límite 70 °C")
    fin_fc = c.inicio + timedelta(hours=19)
    for a in ejes:
        a.axvline(fin_fc, color="k", lw=0.8, ls="-.")
        a.grid(alpha=0.3)
    ax.text(fin_fc, ax.get_ylim()[1], " fin del forecast (19 h) → respaldo ERA5", va="top", fontsize=8)
    ax.set_ylabel("T [°C]")
    ax.set_title("Núcleo y superficie por vertida (caso base, con tuberías)")
    ax.legend(fontsize=7, ncol=3, loc="upper right")
    ax = ejes[1]
    for n, v in enumerate(sorted(s.T_max_vertida_C)):
        ax.plot(t, s.delta_T_vertida_C(v), color=colores(n), label=f"V{v}")
    ax.axhline(c.criterios.delta_T_C, color="r", ls=":", label="Límite 20 °C")
    ax.set_ylabel("ΔT núcleo − superficie [°C]")
    ax.set_title("Diferencial dentro de cada vertida (criterio 20 °C)")
    ax.legend(fontsize=8, ncol=6)
    ax = ejes[2]
    ax.plot(t, s.T_max_C, "k", label="Con tuberías (caso base)")
    if sin_tub is not None:
        t2 = [c.inicio + timedelta(seconds=x) for x in sin_tub.tiempos_s]
        ax.plot(t2, sin_tub.T_max_C, "k--", label="Sin tuberías")
    ax2 = ax.twinx()
    ax2.plot(t, np.asarray(s.potencia_tuberias_W) / 1e3, color="tab:cyan", lw=0.9, label="Potencia extraída por el agua")
    ax2.set_ylabel("Potencia tuberías [kW]", color="tab:cyan")
    ax.set_ylabel("T máx global [°C]")
    ax.set_title("Mecanismo: hidratación vs. extracción por tuberías")
    ax.legend(loc="upper left", fontsize=8)
    ax2.legend(loc="upper right", fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d-%b"))
    salida.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(salida, dpi=130)
    plt.close(fig)


def figura_3d(diag, pvd: Path, salida: Path, abrir: bool) -> None:
    """Corte vertical por la celda de T máx en el instante del pico y a los 7 días (z exagerada ×3)."""
    import xml.etree.ElementTree as ET

    import pyvista as pv

    serie = {float(e.attrib["timestep"]): pvd.parent / e.attrib["file"] for e in ET.parse(pvd).findall(".//DataSet")}
    tiempos = np.array(sorted(serie))
    p_T = np.array(diag["T_max"]["ubicacion"]["xyz_m"])
    p_s = np.array(diag["dT_max"]["superficie"]["xyz_m"])
    pedidos = [diag["T_max"]["t_h"], 168.0]
    plot = pv.Plotter(off_screen=not abrir, shape=(2, 1), window_size=(1500, 1100), border=False)
    for n, t_pedido in enumerate(pedidos):
        t = float(tiempos[np.argmin(np.abs(tiempos - t_pedido))])
        hormigon = pv.read(serie[t]).threshold([0.5, 1.5], scalars="material")
        hormigon.points[:, 2] *= 3.0  # la fundación es plana (≈ 20 × 4 m): se exagera z
        origen = p_T * [1, 1, 3]
        corte = hormigon.clip(normal="y", origin=origen, invert=False)
        plot.subplot(n, 0)
        plot.add_mesh(hormigon.outline(), color="gray")
        clim = [10, 185] if n == 0 else [10, float(np.nanmax(corte["temperatura"]))]
        plot.add_mesh(corte, scalars="temperatura", cmap="inferno", clim=clim,
                      scalar_bar_args={"title": f"T [°C] t={t:.0f} h", "vertical": True})
        etiquetas = [(origen, "cyan", f"T máx {diag['T_max']['valor_C']:.0f} °C (t = {diag['T_max']['t_h']:.0f} h)")]
        if n == 0:
            etiquetas.append((p_s * [1, 1, 3], "white", "superficie del ΔT máx (cara x-, otra sección)"))
        for p, color, texto in etiquetas:
            plot.add_points(p, color=color, point_size=14, render_points_as_spheres=True)
            plot.add_point_labels([p], [texto], font_size=13, always_visible=True)
        plot.add_text(f"t = {t:.0f} h desde el 27-nov 04:00 | corte y = {p_T[1]:.2f} m por la celda de T máx | z ×3",
                      font_size=11)
        c = np.asarray(hormigon.center)
        plot.camera_position = [c + [6, -45, 14], c, (0, 0, 1)]
        plot.reset_camera()
        plot.camera.zoom(1.3)
    plot.show(screenshot=str(salida), auto_close=True)


def git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=RAIZ).stdout.strip()
    except OSError:
        return "?"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rapido", action="store_true", help="Δx = 0,5 m: solo para probar el script.")
    ap.add_argument("--sin-variante", action="store_true", help="No correr la comparación sin tuberías.")
    ap.add_argument("--abrir", action="store_true", help="Abrir la vista PyVista interactiva.")
    ap.add_argument("--solo-3d", action="store_true", help="Rehacer la figura 3D con el VTK y resumen guardados.")
    args = ap.parse_args(argv)
    if args.solo_3d:
        diag = json.loads((RAIZ / "docs" / "evidencia_e12" / "resumen.json").read_text(encoding="utf-8"))
        figura_3d(diag, RAIZ / "results" / "e12" / "vtk" / "temperatura.pvd", RAIZ / "results" / "figures" / "e12_3d.png",
                  args.abrir)
        return 0
    extra = ["simulacion.guardar_campos_cada_h=3"] + (["malla.paso_m=0.5"] if args.rapido else [])
    datos, c = configurar(extra)
    salida = RAIZ / "results" / ("e12_rapido" if args.rapido else "e12")
    salida.mkdir(parents=True, exist_ok=True)
    print(f"Clima: {c.nota_clima}")
    t0 = time.perf_counter()
    r = ejecutar_pipeline(c)
    t_base = time.perf_counter() - t0
    print(f"Caso base: {t_base:.0f} s")
    sin_tub = None
    if not args.sin_variante:
        _, c2 = configurar([e for e in extra if "guardar_campos" not in e] + ["tuberias=[]"])
        sin_tub = ejecutar_pipeline(c2).simulacion
    s = r.simulacion
    diag = diagnosticar(r)
    if sin_tub is not None:
        i = int(np.nanargmax(sin_tub.T_max_C))
        dTs, vs, ts = sin_tub.delta_T_max_por_vertida()
        diag["sin_tuberias"] = dict(T_max_C=round(float(sin_tub.T_max_C[i]), 2), t_h=round(sin_tub.tiempos_s[i] / HORA, 1),
                                    dT_max_C=round(dTs, 2), vertida=vs, t_dT_h=round(ts / HORA, 1))
    # instante guardado más cercano al pico (para la vista 3D)
    tiempos_campo = np.array(sorted(s.campos))
    t_campo = float(tiempos_campo[np.argmin(np.abs(tiempos_campo - diag["T_max"]["t_h"] * HORA))])
    diag["_t_campo_h"], diag["_fecha_campo"] = t_campo / HORA, fecha(c, t_campo)

    from mcplan.visualizacion import escribir_serie_vtk
    pvd = escribir_serie_vtk(salida / "vtk", r.grilla, r.plan, s)
    n = list(tiempos_campo).index(t_campo)
    vti = pvd.parent / f"temperatura_{n:04d}.vti"
    figuras = salida if args.rapido else RAIZ / "results" / "figures"
    sufijo = "_rapido" if args.rapido else ""
    figura_curvas(r, sin_tub, figuras / f"e12_curvas{sufijo}.png")
    figura_3d(diag, pvd, figuras / f"e12_3d{sufijo}.png", args.abrir)

    with (salida / "series.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        vids = sorted(s.T_max_vertida_C)
        w.writerow(["t_h", "fecha", "T_aire_C", "T_max_C", "P_tuberias_kW"]
                   + [f"V{v}_{x}" for v in vids for x in ("nucleo_C", "sup25mm_C", "dT_C")])
        for k, ts_ in enumerate(s.tiempos_s):
            fila = [round(ts_ / HORA, 3), fecha(c, ts_), round(c.ambiente.temperatura(ts_), 2),
                    round(s.T_max_C[k], 3), round(s.potencia_tuberias_W[k] / 1e3, 2)]
            for v in vids:
                a, b = s.T_max_vertida_C[v][k], s.T_sup_min_vertida_C[v][k]
                fila += [round(a, 3), round(b, 3), round(a - b, 3)]
            w.writerow(fila)

    clima = datos["clima"]
    snap = (CONFIG.parent / clima["snapshot"]).resolve()
    resp = (CONFIG.parent / clima["respaldo"]["snapshot"]).resolve()
    diag.update(
        commit_codigo=git_sha(), ejecutado_en_s=round(t_base, 1),
        malla=dict(paso_m=c.malla.pasos[0], paso_z_m=c.malla.pasos[2], voxeles=int(np.prod(r.grilla.forma))),
        inicio=c.inicio.isoformat(), duracion_h=c.tiempo.duracion_s / HORA,
        hidratacion=dict(curva=datos["hormigones"]["M1"]["hidratacion"]["curva"],
                         theta_inf_K=round(c.hormigones["M1"].hidratacion.theta_inf_C, 1)),
        clima=dict(nota=c.nota_clima,
                   forecast=dict(carpeta=snap.name, metadata=json.loads((snap / "metadata.json").read_text(encoding="utf-8")),
                                 sha256=hashlib.sha256((snap / "forecast.json").read_bytes()).hexdigest()),
                   respaldo=dict(carpeta=resp.name, desplazar_anios=clima["respaldo"].get("desplazar_anios"),
                                 sha256=hashlib.sha256((resp / "forecast.json").read_bytes()).hexdigest())),
        plan=[dict(id=p.vertida_id, nombre=p.nombre, inicio_h=p.inicio_s / HORA, inicio=fecha(c, p.inicio_s),
                   T_colocacion_C=p.T_colocacion_C, hormigon=p.hormigon, R_moldaje=p.R_lateral,
                   retiro_moldaje_h=p.retiro_moldaje_s / HORA, R_superior=p.R_superior) for p in r.plan],
    )
    diag.pop("_t_campo_h"), diag.pop("_fecha_campo")
    diag["vista_3d"] = dict(t_campo_h=t_campo / HORA, archivo=vti.name)
    evidencia = salida if args.rapido else RAIZ / "docs" / "evidencia_e12"
    evidencia.mkdir(parents=True, exist_ok=True)
    (evidencia / "resumen.json").write_text(json.dumps(diag, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: diag[k] for k in ("T_max", "dT_max", "por_vertida", "sin_tuberias", "balance_GJ")
                      if k in diag}, indent=2, ensure_ascii=False))
    print(f"Evidencia: {evidencia / 'resumen.json'}; figuras en {figuras}; VTK en {pvd}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
