"""Comprueba las corridas terminadas y genera la evidencia y el HTML sin conexión."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from defensa import RAIZ, cargar_yaml, escribir_csv, guardar_json, resumir

EXTRA = RAIZ.parent / "Archivos Extra/Colocación progresiva"
EVIDENCIA = RAIZ / "docs/evidencia_colocacion_progresiva"
NIVELES = ("barrido", "fino", "confirmacion")
MODOS = {"eps200_T12": "conjunta", "eps200_T12_sucesiva": "sucesiva", "eps200_T12_progresiva": "progresiva"}
METRICAS = ("nivel", "curva", "clima", "D_h", "T_max_C", "t_T_h", "delta_C", "t_delta_h", "horizonte_h",
            "I_T", "I_delta", "I_F", "pico_tardio")


def verificar(r):
    if r["I_T"] != int(r["T_max_C"] > 70) or r["I_delta"] != int(r["delta_C"] > 20):
        raise ValueError(f"Indicadores incompatibles en {r['clave']}.")
    if r["I_F"] != max(r["I_T"], r["I_delta"]):
        raise ValueError(f"Unión incompatible en {r['clave']}.")
    serie = r["series"]
    if not all(math.isclose(delta, T - superficie, abs_tol=1e-10)
               for delta, T, superficie in zip(serie["delta_C"], serie["T_max_C"], serie["T_superficie_min_C"], strict=True)):
        raise ValueError(f"Diferencial incompatible en {r['clave']}.")
    for m, reloj in (("delta_C", "t_delta_h"), ("T_max_C", "t_T_h")):
        i = serie[m].index(max(serie[m]))
        if not math.isclose(r[m], serie[m][i]) or not math.isclose(r[reloj], serie["t_h"][i]):
            raise ValueError(f"Pico incompatible en {r['clave']}.")
    balance = r["balance_J"]
    aportes = sum(balance[k] for k in ("colocacion_J", "hidratacion_J", "ambiente_J", "base_J"))
    salidas = sum(balance[k] for k in ("fuga_vacio_J", "tuberias_J", "agua_J"))
    residuo = balance["E_final_J"] - balance["E_inicial_J"] - (aportes - salidas)
    escala = max(abs(v) for v in balance.values())
    if max(abs(residuo), abs(balance["residuo_J"])) / escala > 1e-12:
        raise ValueError(f"El balance no cierra en {r['clave']}.")
    if r["plan"] == "eps200_T12_progresiva":
        porciones = r["porciones"]
        cargas = sorted({p["carga"] for p in porciones})
        if cargas != list(range(1, 81)):
            raise ValueError(f"Cantidad de cargas incompatible en {r['clave']}.")
        for carga in cargas:
            grupo = [p for p in porciones if p["carga"] == carga]
            volumen = sum(p["volumen_m3"] for p in grupo)
            esperado = min(8, r["D_h"] * 40 - (carga - 1) * 8)
            if not math.isclose(volumen, esperado) or not math.isclose(grupo[0]["inicio_s"], (carga - 1)*720):
                raise ValueError(f"Reloj de carga incompatible en {r['clave']}.")
        if not math.isclose(r["D_h"] * 3600, porciones[-1]["fin_s"]):
            raise ValueError(f"Fin de colocación incompatible en {r['clave']}.")


def perfil(r):
    serie = r["series"]
    filas = []
    for t, temperatura, delta in zip(serie["t_h"], serie["T_max_C"], serie["delta_C"], strict=True):
        if t <= 24 or math.isclose(t, round(t), abs_tol=1e-9) or t in (r["t_T_h"], r["t_delta_h"], r["horizonte_h"]):
            filas.append([round(t, 6), round(temperatura, 5), round(delta, 5)])
    return filas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrada", type=Path, default=RAIZ / "results/colocacion_progresiva")
    parser.add_argument("--evidencia", type=Path, default=EVIDENCIA)
    parser.add_argument("--html", type=Path, default=EXTRA / "Colocación del hormigón.html")
    args = parser.parse_args()
    nuevas = sorted(ruta for plan, modo in MODOS.items() if modo != "conjunta"
                    for ruta in args.entrada.rglob(f"*__{plan}__*.json"))
    resultados_nuevos = [json.loads(r.read_text(encoding="utf-8")) for r in nuevas]
    progresivas = [r for r in resultados_nuevos if r["plan"] == "eps200_T12_progresiva"]
    if not progresivas:
        raise ValueError("Esperar a que termine como mínimo una corrida progresiva.")

    with ZipFile(RAIZ / "docs/evidencia_extension_defensa/corridas.zip") as archivo:
        historicas = [r for name in archivo.namelist() if name.endswith(".json")
                      if (r := json.loads(archivo.read(name)))["plan"] in MODOS and r["nivel"] in NIVELES]
    resultados = historicas + resultados_nuevos
    grupos = {}
    for r in resultados:
        verificar(r)
        llave = r["nivel"], r["curva"], r["clima"]
        modo = MODOS[r["plan"]]
        grupo = grupos.setdefault(llave, {})
        if modo in grupo:
            raise ValueError(f"Duplicado: {llave}, {modo}.")
        if grupo:
            previo = next(iter(grupo.values()))
            for campo in ("ifc", "hidratacion", "codigo", "clima"):
                if previo["entradas"][campo] != r["entradas"][campo]:
                    raise ValueError(f"Insumo distinto ({campo}) al comparar {llave}.")
        grupo[modo] = r

    # La vista conserva todas las porciones de una sola grilla. Las curvas conservan sus propias mallas.
    vista = max(progresivas, key=lambda r: (NIVELES.index(r["nivel"]), r["curva"] == "M1_SS", r["clima"]))
    estudio = cargar_yaml(RAIZ / "configs/defensa_extension_clima.yaml")
    climas = {k: v["peso"] for k, v in estudio["climas"].items() if v["peso"] > 0}
    matrices = {}
    for nivel in NIVELES:
        filas = [r for r in progresivas if r["nivel"] == nivel]
        if filas:
            estado = dict(n=len(filas), fallas=sum(r["I_F"] for r in filas), abiertos=sum(r["pico_tardio"] for r in filas))
            if len(filas) == len(climas)*len(estudio["curvas"]):
                estado.update(resumir(filas, estudio["curvas"], climas))
                estado["P_F_50_50"] = resumir(filas, estudio["pesos_alternativos_curvas"], climas)["P_F"]
            matrices[nivel] = estado

    ordenados = sorted(resultados, key=lambda r: (NIVELES.index(r["nivel"]), r["curva"] != "M1_SS", r["clima"], r["plan"]))
    tabla = [{**{k: r[k] for k in METRICAS}, "modo": MODOS[r["plan"]], "clave": r["clave"]} for r in ordenados]
    payload = {k: vista[k] for k in ("D_h", "porciones", "seccion", "cronograma")}
    payload.update(nivel_seccion=vista["nivel"], matriz=matrices,
                   resultados=[{**fila, "perfil": perfil(r)} for fila, r in zip(tabla, ordenados, strict=True)])
    datos = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    html = (EXTRA / "plantilla.html").read_text(encoding="utf-8")
    args.evidencia.mkdir(parents=True, exist_ok=True)
    args.html.parent.mkdir(parents=True, exist_ok=True)
    escribir_csv(args.evidencia / "comparacion.csv", tabla)
    escribir_csv(args.evidencia / "porciones.csv", vista["porciones"])
    guardar_json(args.evidencia / "estado.json", dict(
        progresivas=len(progresivas), nuevas=len(nuevas), matrices=matrices,
        nivel_seccion=vista["nivel"], residuos_max=max(r["residuo_relativo"] for r in progresivas),
        fuente_historica="aede6bfb38b4e69c92511c598fa62fecdfd6e427",
    ))
    with ZipFile(args.evidencia / "corridas.zip", "w", compression=ZIP_DEFLATED) as archivo:
        for ruta in nuevas:
            archivo.write(ruta, ruta.name)
    with ZipFile(args.evidencia / "corridas.zip") as archivo:
        if archivo.testzip() is not None or len(archivo.namelist()) != len(nuevas):
            raise ValueError("ZIP incompleto o corrupto.")
    args.html.write_text(html.replace("__DATOS_COLOCACION__", datos), encoding="utf-8")
    print(f"{len(nuevas)} corridas nuevas, {len(historicas)} de referencia. HTML: {args.html}")


if __name__ == "__main__":
    main()
