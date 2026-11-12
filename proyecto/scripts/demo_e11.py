"""E11: snapshot real -> BC -> simulación corta -> VTK -> corte PyVista.

Desde proyecto/: python scripts/demo_e11.py [--abrir]
Las salidas regenerables quedan en results/e11; no requiere red.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import yaml

from mcplan.caso import aplicar_sobrescrituras, ejecutar_pipeline, leer_config
from mcplan.caso.clima import leer_snapshot
from mcplan.visualizacion import escribir_serie_vtk

RAIZ = Path(__file__).resolve().parents[1]


def configurar():
    ruta = RAIZ / "configs/e07_caso_base.yaml"
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8-sig"))
    # Fecha exclusiva del laboratorio: no cambia el inicio de obra del caso base.
    datos = aplicar_sobrescrituras(datos, [
        'simulacion.inicio="2026-11-12T04:00"',
        "simulacion.duracion_h=48", "malla.paso_m=0.5",
        "simulacion.guardar_campos_cada_h=6", "clima.completar=error",
        # La evidencia E11 se generó con el pronóstico del 7-nov; el caso base ya usa uno más nuevo.
        "clima.snapshot=../data/weather/2026-11-07T2001_pronostico",
    ])
    datos["clima"].pop("respaldo", None)
    return leer_config(datos, base_rutas=ruta.parent)


def visualizar(vti: Path, destino: Path, abrir: bool = False):
    import pyvista as pv

    grilla = pv.read(vti)
    hormigon = grilla.threshold([0.5, 1.5], scalars="material")
    # Núcleo térmico: celda activa más caliente, no necesariamente centro geométrico.
    centros = hormigon.cell_centers().points
    nucleo = centros[np.argmax(hormigon["temperatura"])]
    corte = hormigon.clip(normal="y", origin=nucleo, invert=False)
    plot = pv.Plotter(off_screen=not abrir, window_size=(1200, 800))
    plot.add_mesh(hormigon.outline(), color="gray")
    plot.add_mesh(corte, scalars="temperatura", cmap="inferno",
                  scalar_bar_args={"title": "Temperatura [C]"})
    plot.add_points(nucleo, color="cyan", point_size=16, render_points_as_spheres=True)
    plot.add_point_labels([nucleo], ["Nucleo termico (T maxima)"], font_size=16,
                          always_visible=True)
    plot.add_text("E11 - 48 h | clipping por nucleo\nSuperficie: envolvente exterior del hormigon",
                  font_size=12)
    plot.add_axes()
    centro = np.asarray(hormigon.center)
    plot.camera_position = [centro + [32, -40, 25], centro, (0, 0, 1)]
    plot.reset_camera()
    plot.show(screenshot=str(destino), auto_close=True)
    return {"nucleo_xyz_m": nucleo.tolist(), "celdas_hormigon": hormigon.n_cells,
            "celdas_corte": corte.n_cells}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--abrir", action="store_true", help="Abrir ventana 3D interactiva")
    parser.add_argument("--guardado", action="store_true", help="Abrir VTK existente sin recalcular")
    args = parser.parse_args()
    salida = RAIZ / "results/e11"
    salida.mkdir(parents=True, exist_ok=True)
    if args.guardado:
        import xml.etree.ElementTree as ET
        pvd = salida / "vtk/temperatura.pvd"
        if pvd.is_file():
            entradas = ET.parse(pvd).findall(".//DataSet")
            ultima = max(entradas, key=lambda e: float(e.attrib["timestep"]))
            ultimo = pvd.parent / ultima.attrib["file"]
            if ultimo.is_file():
                print(f"Abriendo resultado guardado: {ultimo}")
                visualizar(ultimo, salida / "corte_3d.png", args.abrir)
                return
        print("No hay resultado guardado: se generara una vez.")
    c = configurar()
    snapshot = leer_snapshot(RAIZ / "data/weather/2026-11-07T2001_pronostico")
    print(snapshot.descripcion())
    print(json.dumps(snapshot.metadata, ensure_ascii=False, indent=2))
    print(c.nota_clima)
    horas = np.arange(49)
    aire = [c.ambiente.temperatura(float(h * 3600)) for h in horas]
    with (salida / "borde.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_h", "T_aire_C", "h_conveccion_W_m2K", "h_total_W_m2K", "T_eq_superior_C"])
        for h, T in zip(horas, aire):
            t = float(h * 3600)
            ht, eq = c.ambiente.condiciones(t)
            w.writerow([h, T, c.ambiente.h_conveccion(t), ht, eq["superior"]])
    r = ejecutar_pipeline(c)
    s = r.simulacion
    fig, ax = plt.subplots(figsize=(10, 5), layout="constrained")
    ax.plot(horas, aire, label="Aire: snapshot -> BC")
    ax.plot(np.asarray(s.tiempos_s) / 3600, s.T_max_C, label="Nucleo: maximo activo")
    ax.plot(np.asarray(s.tiempos_s) / 3600, s.T_sup_min_C, label="Superficie minima a 25 mm")
    ax.set(xlabel="Horas desde 12-nov-2026 04:00 (America/Santiago)", ylabel="Temperatura [C]")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.savefig(salida / "temperaturas.png", dpi=150)
    plt.close(fig)
    pvd = escribir_serie_vtk(salida / "vtk", r.grilla, r.plan, s)
    ultimo = sorted(pvd.parent.glob("temperatura_*.vti"))[-1]
    vista = visualizar(ultimo, salida / "corte_3d.png", args.abrir)
    evidencia = {"inicio": c.inicio.isoformat(), "duracion_h": 48,
                 "fuente": snapshot.metadata, "nota_clima": c.nota_clima,
                 "sha256_snapshot": hashlib.sha256((snapshot.carpeta / "forecast.json").read_bytes()).hexdigest(),
                 "T_max_C": max(s.T_max_C), "balance": s.balance, "vista": vista,
                 "serie_vtk": "vtk/temperatura.pvd"}
    (salida / "metadata_resultado.json").write_text(json.dumps(evidencia, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(evidencia, indent=2, ensure_ascii=False))
    print(f"Salidas: {salida}")


if __name__ == "__main__":
    main()
