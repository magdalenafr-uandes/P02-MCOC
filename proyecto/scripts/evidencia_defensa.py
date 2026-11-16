"""Empaqueta corridas verificadas y genera las figuras de la defensa."""

from __future__ import annotations

import argparse
from copy import deepcopy
import csv
from itertools import product
import json
from pathlib import Path
import zipfile

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from defensa import RAIZ, cargar_yaml, clave_corrida, escribir_tablas, huella_modelo, ruta_corrida, sha256_archivo
from mcplan.caso.config import leer_config
from mcplan.caso.pipeline import ejecutar_pipeline


def cargar_corridas(entrada, estudio):
    archivos = sorted(entrada.glob("*__*__*__*__*.json"))
    filas = [(p, json.loads(p.read_text(encoding="utf-8"))) for p in archivos]
    version = huella_modelo()
    antigua = huella_modelo(normalizar=False)
    filtradas = {}
    for p, r in filas:
        entradas = r["entradas"]
        if entradas["codigo"] not in (version, antigua):
            continue
        carpeta = RAIZ / "configs"
        caso = deepcopy(r["caso"])
        if r["periodo_base"]:
            # La clave original se calculó con el tipo numérico del YAML.
            caso["simulacion"]["duracion_h"] = estudio["horizonte_h"]
        extendido = estudio["horizonte_extendido_h"]
        if r["clave"] != clave_corrida(caso, entradas, r["D_h"], extendido):
            raise ValueError(f"La configuración registrada no coincide con la clave de {p.name}.")
        clima = caso["clima"]
        firma = dict(entradas, codigo=version)
        for campo, datos_clima in (("clima", clima), ("respaldo", clima.get("respaldo"))):
            if datos_clima is None:
                continue
            rutas = [carpeta / datos_clima["snapshot"] / n for n in ("forecast.json", "metadata.json")]
            cruda = [sha256_archivo(s) for s in rutas]
            portable = [sha256_archivo(s, texto=True) for s in rutas]
            if entradas[campo] not in (cruda, portable):
                raise ValueError(f"Archivos de clima distintos a los registrados en {p.name}.")
            firma[campo] = portable
        for campo, nombre in (("ifc", caso["ifc"]), ("hidratacion", caso["hormigones"]["M1"]["hidratacion"]["archivo"])):
            if sha256_archivo(carpeta / nombre) != entradas[campo]:
                raise ValueError(f"El archivo {campo} de {p.name} cambió.")
        r.update(entradas=firma, clave=clave_corrida(caso, firma, r["D_h"], extendido))
        salida = ruta_corrida(entrada, r["nivel"], r["plan"], r["curva"], r["clima"], r["clave"])
        filtradas[salida.name] = (salida, r)
    if not filtradas:
        raise ValueError("Todavía no hay corridas que empaquetar.")
    filtradas = list(filtradas.values())
    identidades = [(r["plan"], r["nivel"], r["curva"], r["clima"]) for _, r in filtradas]
    if len(identidades) != len(set(identidades)):
        raise ValueError("Hay dos configuraciones vigentes con el mismo identificador. Revisar antes de publicar.")
    for _, r in filtradas:
        if r["I_F"] != max(r["I_T"], r["I_delta"]):
            raise ValueError(f"Indicador conjunto inconsistente en {r['clave']}.")
        balance = r["balance_J"]
        escala = max(abs(balance[k]) for k in ("E_final_J", "E_inicial_J", "colocacion_J", "hidratacion_J"))
        if abs(balance["residuo_J"]) > 1e-8 * escala:
            raise ValueError(f"Balance fuera de tolerancia en {r['clave']}.")
        series = r["series"]
        if not np.allclose(np.asarray(series["T_max_C"]) - series["T_superficie_min_C"], series["delta_C"]):
            raise ValueError(f"Diferencial inconsistente en {r['clave']}.")
    return filtradas


def verificar_familia(filas, estudio, nivel):
    primarios = [m for m, clima in estudio["climas"].items() if clima["peso"] > 0]
    esperados = set(product(estudio["planes"], estudio["curvas"], primarios))
    encontrados = {(r["plan"], r["curva"], r["clima"]) for r in filas if r["nivel"] == nivel}
    return sorted(esperados - encontrados)


def graficar(resultados, resumen, destino, nivel):
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 12, "axes.spines.top": False,
        "axes.spines.right": False, "axes.labelcolor": "#192c3c", "text.color": "#192c3c",
    })
    colores = {"Sin aislación": "#53687c", "Manta": "#097b73", "Poliestireno": "#916427"}
    marcadores = {"Sin aislación": "o", "Manta": "s", "Poliestireno": "^"}
    fig, ax = plt.subplots(figsize=(8, 4.7), layout="constrained")
    ax.axhline(5, color="#ab492f", ls="--", lw=1.7, label="Límite 5%")
    vistos = set()
    for r in resumen:
        tipo = next((k for k in ("Manta", "Poliestireno") if r["plan"].endswith(k.lower())), "Sin aislación")
        D, P = float(r["D_h"]), 100 * float(r["P_F"])
        clave = (round(D, 8), round(P, 8), tipo)
        if clave not in vistos:
            ax.scatter(D, P, s=88, color=colores[tipo], marker=marcadores[tipo], label=tipo)
            vistos.add(clave)
    ax.set(xlabel="Duración física [h]", ylabel="Excedencia conjunta [%]", ylim=(-4, 108))
    ax.grid(axis="y", color="#dbe2e6")
    manejadores, nombres = ax.get_legend_handles_labels()
    leyenda = dict(zip(nombres, manejadores))
    ax.legend(leyenda.values(), leyenda.keys(), loc="center right", frameon=False)
    fig.savefig(destino / "duracion_riesgo.png", dpi=180)
    plt.close(fig)

    principal = {r["plan"] for r in resumen}
    caso = [r for r in resultados if r["nivel"] == nivel and r["plan"] in principal
            and r["curva"] == "M1_SS" and r["clima"] == "era5_2025"
            and r["plan"] in ("unica", "unica_manta", "unica_poliestireno")]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.85), sharex=True, layout="constrained")
    for r in caso:
        serie = r["series"]
        t = np.asarray(serie["t_h"]) / 24
        etiqueta = next((k for k in ("Manta", "Poliestireno") if r["plan"].endswith(k.lower())), "Sin aislación")
        color = colores[etiqueta]
        axes[0].plot(t, serie["T_max_C"], color=color, lw=2, label=f"Máxima · {etiqueta}")
        axes[0].plot(t, serie["T_superficie_min_C"], color=color, ls=":", lw=1.4,
                     label=f"Superficie · {etiqueta}")
        axes[1].plot(t, serie["delta_C"], color=color, lw=2, label=etiqueta)
    for ax, limite, y in zip(axes, (70, 20), ("Temperatura [°C]", "Diferencial global [°C]")):
        ax.axhline(limite, color="#ab492f", ls="--", lw=1.2, label=f"Límite {limite} °C")
        ax.set(xlabel="Días desde el inicio de obra", ylabel=y)
        ax.grid(axis="y", color="#dbe2e6")
        ax.legend(fontsize=8.6, frameon=False)
    fig.savefig(destino / "curvas_comparadas.png", dpi=175)
    plt.close(fig)


def corte(resultado, destino):
    caso = deepcopy(resultado["caso"])
    caso["vertidas"] = {int(k) if k.isdigit() else k: v for k, v in caso["vertidas"].items()}
    caso["simulacion"].update(guardar_campos=True, guardar_campos_cada_h=resultado["t_delta_h"])
    r = ejecutar_pipeline(leer_config(caso, RAIZ / "configs"))
    instante = resultado["t_delta_h"] * 3600
    t = min(r.simulacion.campos, key=lambda x: abs(x - instante))
    if not np.isclose(t, instante, rtol=0.0, atol=1e-6):
        raise ValueError("El campo guardado no corresponde al instante del diferencial máximo.")
    grilla = r.grilla
    origen = grilla.definicion.origen
    d = grilla.paso
    y = resultado["punto_caliente"]["centro_voxel_m"][1]
    j = round((y - origen[1]) / d[1] - 0.5)
    activas = [p.vertida_id for p in r.plan if p.visible and p.inicio_s <= t]
    mascara = np.isin(grilla.vertida_id[:, j, :], activas)
    if not mascara.any():
        raise ValueError("El corte no contiene hormigón activo.")
    campo = np.where(mascara, r.simulacion.campos[t][:, j, :], np.nan)
    T_guardada = resultado["punto_caliente"]["temperatura_C"]
    if not np.isclose(np.nanmax(campo), T_guardada, rtol=0.0, atol=0.02):
        raise ValueError("El corte no reproduce la temperatura caliente del escenario.")
    x0, z0 = origen[0], origen[2]
    nx, nz = campo.shape
    fig, ax = plt.subplots(figsize=(9.2, 4.15), layout="constrained")
    im = ax.imshow(campo.T, origin="lower",
                   extent=(x0, x0 + nx * d[0], z0, z0 + nz * d[2]),
                   vmin=10, vmax=70, cmap="inferno", interpolation="nearest")
    x_hot, _, z_hot = resultado["punto_caliente"]["centro_voxel_m"]
    ax.scatter(x_hot, z_hot, marker="+", s=95, color="#34e3f0", linewidth=2)
    ax.set(xlabel="X [m]", ylabel="Z [m]",
           ylim=(0, 5), title=f"Corte Y = {y:.2f} m · {resultado['t_delta_h']:.2f} h")
    fig.colorbar(im, ax=ax, label="Temperatura del voxel [°C]")
    fig.savefig(destino, dpi=190)
    plt.close(fig)
    print(f"Corte verificado para {resultado['plan']}, {resultado['clima']}, {resultado['curva']}.")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--entrada", type=Path, default=RAIZ / "results/defensa")
    p.add_argument("--salida", type=Path, default=RAIZ / "docs/evidencia_defensa")
    p.add_argument("--figuras", type=Path)
    p.add_argument("--nivel", default="cribado")
    p.add_argument("--permitir-parcial", action="store_true")
    p.add_argument("--corte", action="store_true")
    args = p.parse_args()
    estudio = cargar_yaml(RAIZ / "configs/defensa.yaml")
    lista = cargar_corridas(args.entrada, estudio)
    resultados = [r for _, r in lista]
    faltantes = verificar_familia(resultados, estudio, args.nivel)
    if faltantes and not args.permitir_parcial:
        raise ValueError(f"Quedan {len(faltantes)} escenarios de {args.nivel} por ejecutar.")
    args.salida.mkdir(parents=True, exist_ok=True)
    escribir_tablas(args.salida, resultados, estudio)
    archivo_cronograma = args.entrada / "cronogramas.csv"
    (args.salida / archivo_cronograma.name).write_bytes(archivo_cronograma.read_bytes())
    comprimido = args.salida / "corridas.zip"
    with zipfile.ZipFile(comprimido, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archivo:
        for ruta, resultado in lista:
            texto = json.dumps(resultado, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
            archivo.writestr(ruta.name, texto.encode("utf-8"))
    with zipfile.ZipFile(comprimido) as archivo:
        if archivo.testzip() is not None or len(archivo.namelist()) != len(lista):
            raise ValueError("No se pudo verificar el archivo de corridas.")
    (args.salida / "estado.json").write_text(json.dumps({
        "version_modelo": resultados[0]["entradas"]["codigo"], "corridas": len(lista),
        "nivel_principal": args.nivel, "faltantes": faltantes,
    }, indent=2) + "\n", encoding="utf-8")
    if args.figuras:
        args.figuras.mkdir(parents=True, exist_ok=True)
    if args.figuras and not faltantes:
        with (args.salida / "comparacion.csv").open(encoding="utf-8", newline="") as f:
            resumen = [r for r in csv.DictReader(f) if r["nivel"] == args.nivel and r["pesos"] == "curvas"]
        graficar(resultados, resumen, args.figuras, args.nivel)
    if args.figuras and args.corte:
        base = next(r for r in resultados if (r["plan"], r["nivel"], r["curva"], r["clima"])
                    == ("unica", "cribado", "M1_SS", "era5_2025"))
        corte(base, args.figuras / "corte_critico.png")
    print(f"{len(lista)} corridas verificadas. Pendientes de {args.nivel}: {len(faltantes)}.")


if __name__ == "__main__":
    main()
