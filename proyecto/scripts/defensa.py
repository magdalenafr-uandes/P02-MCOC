"""Ejecuta y reanuda la comparación reproducible para la defensa E13."""

from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from copy import deepcopy
import csv
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import inspect
from itertools import product
import json
import math
from pathlib import Path
import subprocess
from time import perf_counter

import numpy as np
import yaml

from mcplan.bim.mallas_ifc import extraer_vertidas
from mcplan.caso.config import leer_config
from mcplan.caso.pipeline import ejecutar_pipeline

RAIZ = Path(__file__).resolve().parents[1]
HORA = 3600
LIMITE_RIESGO = Decimal("0.05")


def cargar_yaml(ruta):
    return yaml.safe_load(ruta.read_text(encoding="utf-8-sig"))


def sha256_archivo(ruta):
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def guardar_json(ruta, valor):
    # Un archivo JSON final identifica una corrida completa y permite reanudar.
    temporal = ruta.with_suffix(".tmp")
    temporal.write_text(json.dumps(valor, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporal.replace(ruta)


def cronograma(solidos, capacidad, plan, retiro_h):
    if not math.isfinite(capacidad) or capacidad <= 0 or plan["espera_h"] < 0:
        raise ValueError("La capacidad debe ser positiva y la espera, no negativa.")
    if plan["activacion"] not in ("conjunta", "sucesiva"):
        raise ValueError("Activación desconocida.")
    if plan["activacion"] == "conjunta" and plan["espera_h"]:
        raise ValueError("La operación continua de activación conjunta no admite esperas.")
    reloj = 0.0
    filas = []
    for solido in solidos:
        duracion = solido.volumen / capacidad
        activacion = 0.0 if plan["activacion"] == "conjunta" else reloj
        filas.append(dict(vertida=solido.vertida_id, volumen_m3=solido.volumen, inicio_h=reloj,
                          fin_h=reloj + duracion, duracion_h=duracion,
                          activacion_h=activacion, retiro_h=activacion + retiro_h))
        reloj += duracion + plan["espera_h"]
    return filas


def preparar_caso(base, estudio, plan, clima, curva, nivel, filas, horizonte_h):
    datos = deepcopy(base)
    datos["simulacion"].update(inicio=estudio["inicio"], duracion_h=horizonte_h,
                               fraccion_dt=nivel["fraccion_dt"], guardar_cada_h=nivel["registro_h"],
                               guardar_campos=False)
    datos["simulacion"].pop("guardar_campos_cada_h", None)
    datos["malla"].update(paso_m=nivel["paso_m"], paso_z_m=nivel["paso_z_m"])
    datos["clima"] = {k: v for k, v in clima.items() if k != "peso"}
    datos["hormigones"]["M1"]["hidratacion"].update(curva=curva, Ea_J_mol=estudio["Ea_J_mol"])
    datos["tuberias"] = []
    datos.pop("enfriamiento", None)
    defecto = datos["vertidas"]["defecto"]
    defecto.update(T_colocacion_C=estudio["temperatura_colocacion_C"],
                   retiro_moldaje_h=estudio["retiro_moldaje_h"])
    if plan["aislacion"]:
        defecto.update(aislacion=plan["aislacion"], aislacion_caras=["superior", "lateral"])
    for fila in filas:
        datos["vertidas"][fila["vertida"]] = {"inicio_h": fila["activacion_h"]}
    return datos


# [MAPA:defensa-metricas] máximo en hormigón activo y diferencial global a 25 mm, al mismo instante
def metricas(resultado):
    simulacion = resultado.simulacion
    tiempos = np.asarray(simulacion.tiempos_s) / HORA
    maximos = np.asarray(simulacion.T_max_C)
    delta = simulacion.delta_T_C
    if not np.any(np.isfinite(delta)):
        raise ValueError("La corrida no produjo un diferencial global de superficie.")
    i_max = int(np.nanargmax(maximos))
    i_delta = int(np.nanargmax(delta))
    grilla = resultado.grilla

    def punto(i, superficie=False):
        series = simulacion.T_sup_min_vertida_C if superficie else simulacion.T_max_vertida_C
        ids = simulacion.idx_sup_vertida if superficie else simulacion.idx_max_vertida
        valores = ((serie[i], vid) for vid, serie in series.items() if np.isfinite(serie[i]))
        valor, vid = (min if superficie else max)(valores)
        idx = np.unravel_index(ids[vid][i], grilla.forma)
        xyz = [float(o + (j + 0.5) * d) for o, j, d in zip(grilla.definicion.origen, idx, grilla.paso)]
        salida = dict(temperatura_C=valor, vertida=vid, centro_voxel_m=xyz)
        if superficie:
            cara = simulacion.cara_sup_vertida[vid][i]
            eje = "xyz".index(cara[0])
            punto_m = xyz.copy()
            profundidad = resultado.config.criterios.profundidad_superficie_m
            punto_m[eje] += (1 if cara[1] == "+" else -1) * max(grilla.paso[eje] / 2 - profundidad, 0)
            salida.update(cara=cara, punto_evaluado_m=punto_m)
        return salida

    def sigue_subiendo(serie, i):
        final = tiempos[-1]
        ultima = serie[tiempos >= final - 24]
        previa = serie[(tiempos >= final - 48) & (tiempos < final - 24)]
        return bool(
            tiempos[i] >= final - 24
            or (np.any(np.isfinite(previa)) and np.nanmax(ultima) > np.nanmax(previa) + 0.1)
        )

    evaluable = np.isfinite(delta)
    dT_vertida, vid, t_dT_vertida = simulacion.delta_T_max_por_vertida()
    return dict(
        T_max_C=float(maximos[i_max]), t_T_h=float(tiempos[i_max]), punto_T=punto(i_max),
        delta_C=float(delta[i_delta]), t_delta_h=float(tiempos[i_delta]),
        punto_caliente=punto(i_delta), punto_frio=punto(i_delta, superficie=True),
        delta_dentro_vertida_C=float(dT_vertida), vertida_delta=vid, t_delta_vertida_h=t_dT_vertida / HORA,
        horizonte_h=float(tiempos[-1]),
        pico_tardio=sigue_subiendo(maximos, i_max) or sigue_subiendo(delta, i_delta),
        balance_J=simulacion.balance,
        pasos=sum(etapa["pasos"] for etapa in simulacion.etapas),
        volumenes=resultado.volumetria,
        series=dict(t_h=tiempos[evaluable].tolist(), T_max_C=maximos[evaluable].tolist(),
                    T_superficie_min_C=np.asarray(simulacion.T_sup_min_C)[evaluable].tolist(),
                    delta_C=delta[evaluable].tolist()),
    )


def calcular(tarea):
    ruta = Path(tarea["ruta"])
    datos = tarea["datos"]
    inicio = perf_counter()
    config = leer_config(datos, Path(tarea["carpeta"]))
    resultado = metricas(ejecutar_pipeline(config))
    periodo_base = None
    if resultado["pico_tardio"]:
        periodo_base = {k: resultado[k] for k in ("T_max_C", "t_T_h", "delta_C", "t_delta_h", "horizonte_h")}
        datos = deepcopy(datos)
        datos["simulacion"]["duracion_h"] = tarea["horizonte_extendido_h"]
        config = leer_config(datos, Path(tarea["carpeta"]))
        resultado = metricas(ejecutar_pipeline(config))
    criterio = config.criterios
    resultado.update(
        clave=tarea["clave"], commit=tarea["commit"], plan=tarea["plan"], curva=tarea["curva"],
        clima=tarea["clima"], nivel=tarea["nivel"], entradas=tarea["entradas"], caso=datos,
        D_h=tarea["D_h"], clima_detalle=config.nota_clima, periodo_base=periodo_base,
        I_T=int(resultado["T_max_C"] > criterio.T_max_C),
        I_delta=int(resultado["delta_C"] > criterio.delta_T_C),
        segundos=perf_counter() - inicio,
    )
    resultado["I_F"] = max(resultado["I_T"], resultado["I_delta"])
    guardar_json(ruta, resultado)
    return resultado


def leer_previo(tarea):
    try:
        resultado = json.loads(Path(tarea["ruta"]).read_text(encoding="utf-8"))
        if resultado["clave"] == tarea["clave"] and "I_F" in resultado and "series" in resultado:
            return resultado
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return None


def decimal(valor):
    return Decimal(str(valor))


# [MAPA:defensa-riesgo] unión ponderada de excedencias, sin duplicar una falla doble
def resumir(resultados, pesos_curvas, pesos_climas):
    esperado = set(product(pesos_curvas, pesos_climas))
    visto = {(r["curva"], r["clima"]) for r in resultados}
    if visto != esperado or len(resultados) != len(esperado):
        raise ValueError("Se requiere exactamente una fila por escenario.")
    curvas = {k: decimal(v) for k, v in pesos_curvas.items()}
    climas = {k: decimal(v) for k, v in pesos_climas.items()}
    if min((*curvas.values(), *climas.values())) < 0 or sum(curvas.values()) != 1 or sum(climas.values()) <= 0:
        raise ValueError("Los pesos de curva deben sumar uno y los de clima tener suma positiva.")
    total_clima = sum(climas.values())
    sumas = [sum(curvas[r["curva"]] * climas[r["clima"]] * r[k] for r in resultados)
             for k in ("I_T", "I_delta", "I_F")]
    if any(r["pico_tardio"] for r in resultados):
        cumple = "indeterminado_horizonte"
    else:
        cumple = "si" if sumas[-1] <= LIMITE_RIESGO * total_clima else "no"
    return dict(P_T=float(sumas[0] / total_clima), P_delta=float(sumas[1] / total_clima),
                P_F=float(sumas[2] / total_clima), cumple=cumple)


def escribir_csv(ruta, filas):
    if filas:
        with ruta.open("w", encoding="utf-8", newline="") as archivo:
            salida = csv.DictWriter(archivo, fieldnames=list(filas[0]))
            salida.writeheader()
            salida.writerows(filas)


def escribir_tablas(salida, resultados, estudio):
    columnas = ("plan", "nivel", "curva", "clima", "D_h", "T_max_C", "t_T_h", "delta_C",
                "t_delta_h", "I_T", "I_delta", "I_F", "horizonte_h", "pico_tardio", "segundos")
    pesos_climas = {n: c["peso"] for n, c in estudio["climas"].items() if c["peso"] > 0}
    total_clima = sum(pesos_climas.values())
    filas = [{**{k: r[k] for k in columnas},
              "peso_w": estudio["curvas"].get(r["curva"], 0) * pesos_climas.get(r["clima"], 0) / total_clima}
             for r in resultados]
    escribir_csv(salida / "escenarios.csv", filas)
    resumen = []
    for plan, nivel in sorted({(r["plan"], r["nivel"]) for r in resultados}):
        casos = [r for r in resultados if r["plan"] == plan and r["nivel"] == nivel and r["clima"] in pesos_climas
                 and r["curva"] in estudio["curvas"]]
        if len(casos) == len(pesos_climas) * len(estudio["curvas"]):
            for pesos in ("curvas", "pesos_alternativos_curvas"):
                resumen.append(dict(plan=plan, nivel=nivel, pesos=pesos, D_h=casos[0]["D_h"],
                                    **resumir(casos, estudio[pesos], pesos_climas)))
    escribir_csv(salida / "comparacion.csv", resumen)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=RAIZ / "configs/defensa.yaml")
    parser.add_argument("--salida", type=Path, default=RAIZ / "results/defensa")
    parser.add_argument("--plan", action="append")
    parser.add_argument("--curva", action="append")
    parser.add_argument("--clima", action="append")
    parser.add_argument("--nivel", default="cribado")
    parser.add_argument("--procesos", type=int, default=1)
    parser.add_argument("--solo-cronograma", action="store_true")
    args = parser.parse_args()
    if args.procesos < 1:
        parser.error("--procesos debe ser positivo.")
    carpeta = args.config.resolve().parent
    estudio = cargar_yaml(args.config)
    base = cargar_yaml(carpeta / estudio["caso_base"])
    rutas = [carpeta / base["ifc"], carpeta / base["hormigones"]["M1"]["hidratacion"]["archivo"]]
    solidos = extraer_vertidas(rutas[0])
    args.salida.mkdir(parents=True, exist_ok=True)
    inicio = datetime.fromisoformat(estudio["inicio"])
    horarios = {n: cronograma(solidos, estudio["capacidad_m3_h"], p, estudio["retiro_moldaje_h"])
                for n, p in estudio["planes"].items()}
    escribir_csv(args.salida / "cronogramas.csv", [
        dict(plan=plan, **f, inicio=(inicio + timedelta(hours=f["inicio_h"])).isoformat(),
             fin=(inicio + timedelta(hours=f["fin_h"])).isoformat(), zona=estudio["zona_horaria"])
        for plan, filas in horarios.items() for f in filas
    ])
    print(f"Volumen IFC: {sum(s.volumen for s in solidos):.3f} m3. Cronogramas: {args.salida}", flush=True)
    if args.solo_cronograma:
        return
    codigo = hashlib.sha256()
    for funcion in (cronograma, preparar_caso, metricas, calcular):
        codigo.update(inspect.getsource(funcion).encode())
    for ruta in sorted((RAIZ / "src/mcplan").rglob("*.py")):
        codigo.update(ruta.read_bytes())
    archivos = dict(ifc=sha256_archivo(rutas[0]), hidratacion=sha256_archivo(rutas[1]), codigo=codigo.hexdigest())
    commit = subprocess.check_output(["git", "-C", str(RAIZ), "rev-parse", "HEAD"], text=True).strip()
    def preparar_tarea(plan, curva, clima, nivel):
        historico = estudio["climas"][clima]
        dir_clima = carpeta / historico["snapshot"]
        entradas = dict(archivos, clima=[sha256_archivo(dir_clima / n) for n in ("forecast.json", "metadata.json")])
        if "respaldo" in historico:
            respaldo = carpeta / historico["respaldo"]["snapshot"]
            entradas["respaldo"] = [sha256_archivo(respaldo / n) for n in ("forecast.json", "metadata.json")]
        datos = preparar_caso(base, estudio, estudio["planes"][plan], historico, curva,
                              estudio["niveles"][nivel], horarios[plan], estudio["horizonte_h"])
        D_h = horarios[plan][-1]["fin_h"]
        extendido = estudio["horizonte_extendido_h"]
        clave = hashlib.sha256(json.dumps([datos, entradas, D_h, extendido], sort_keys=False).encode()).hexdigest()
        ruta = args.salida / f"{nivel}__{plan}__{curva}__{clima}__{clave[:12]}.json"
        return dict(ruta=str(ruta), clave=clave, datos=datos, carpeta=str(carpeta),
                    entradas=entradas, commit=commit, horizonte_extendido_h=extendido,
                    plan=plan, curva=curva, clima=clima, nivel=nivel, D_h=D_h)

    tareas = [preparar_tarea(p, c, m, args.nivel) for p, c, m in product(
        args.plan or estudio["planes"], args.curva or estudio["curvas"],
        args.clima or [n for n, c in estudio["climas"].items() if c["peso"] > 0])]
    pendientes = [t for t in tareas if leer_previo(t) is None]
    print(f"Corridas: {len(tareas)} seleccionadas, {len(pendientes)} por ejecutar.", flush=True)

    def informar(r):
        print(f"{r['plan']}/{r['curva']}/{r['clima']}: Tmax={r['T_max_C']:.3f}, "
              f"dT={r['delta_C']:.3f}, {r['segundos']:.1f} s", flush=True)

    pausa = args.salida / "PAUSAR"
    if args.procesos == 1:
        for tarea in pendientes:
            if pausa.exists():
                break
            informar(calcular(tarea))
    else:
        with ProcessPoolExecutor(max_workers=args.procesos) as executor:
            en_curso = set()
            por_iniciar = iter(pendientes)
            while True:
                while len(en_curso) < args.procesos and not pausa.exists():
                    siguiente = next(por_iniciar, None)
                    if siguiente is None:
                        break
                    en_curso.add(executor.submit(calcular, siguiente))
                if not en_curso:
                    break
                terminadas, en_curso = wait(en_curso, return_when=FIRST_COMPLETED)
                for futuro in terminadas:
                    informar(futuro.result())
    if pausa.exists():
        print(f"Campaña en pausa. Quitar {pausa} antes de continuar.", flush=True)
    resultados = []
    for ruta in sorted(args.salida.glob("*__*__*__*__*.json")):
        nivel, plan, curva, clima, _ = ruta.stem.split("__")
        if nivel in estudio["niveles"] and plan in estudio["planes"] and clima in estudio["climas"]:
            actual = preparar_tarea(plan, curva, clima, nivel)
            if Path(actual["ruta"]) == ruta and (resultado := leer_previo(actual)) is not None:
                resultados.append(resultado)
    escribir_tablas(args.salida, resultados, estudio)


if __name__ == "__main__":
    main()
