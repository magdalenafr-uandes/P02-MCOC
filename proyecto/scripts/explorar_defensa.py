"""Amplía controles de defensa sin cambiar el solver ni las corridas previas.

Reutiliza preparación, extracción y agregación de defensa.py; cada JSON conserva
el caso completo y su clave. Los resultados de esta familia se guardan aparte.
"""
from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from copy import deepcopy
from datetime import datetime, timedelta
from itertools import product
from pathlib import Path
import subprocess

from defensa import (RAIZ, calcular, cargar_yaml, clave_corrida, cronograma,
                     escribir_csv, escribir_tablas, huella_modelo, leer_previo,
                     preparar_caso, ruta_corrida, sha256_archivo)
from mcplan.bim.mallas_ifc import extraer_vertidas


# [MAPA:defensa-controles] controles adicionales conservando geometría, capacidad y pesos
def preparar_extension(base, estudio, control, clima, curva, nivel, filas):
    base = deepcopy(base)
    base["protecciones"]["eps_extension"] = {"espesor_m": control["espesor_m"], "k_W_mK": 0.035}
    estudio = dict(estudio, temperatura_colocacion_C=control["T_colocacion_C"])
    plan = dict(activacion=control["activacion"], espera_h=0, aislacion="eps_extension")
    caso = preparar_caso(base, estudio, plan, clima, curva, nivel, filas, estudio["horizonte_h"])
    caso["vertidas"]["defecto"].update(aislacion_desde_h=0)
    return caso


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--familia", type=Path, default=RAIZ / "configs/defensa_extension.yaml")
    parser.add_argument("--estudio", type=Path, default=RAIZ / "configs/defensa.yaml")
    parser.add_argument("--salida", type=Path, default=RAIZ / "results/defensa_extension")
    parser.add_argument("--plan", action="append")
    parser.add_argument("--curva", action="append")
    parser.add_argument("--clima", action="append")
    parser.add_argument("--nivel", default="barrido")
    parser.add_argument("--procesos", type=int, default=3)
    parser.add_argument("--horizonte-extendido", type=float, default=448)
    args = parser.parse_args()
    if args.procesos < 1 or args.horizonte_extendido < 336:
        parser.error("Procesos positivos y horizonte extendido >= 336 h.")
    estudio = cargar_yaml(args.estudio)
    estudio["horizonte_extendido_h"] = args.horizonte_extendido
    controles = cargar_yaml(args.familia)["planes"]
    carpeta = args.estudio.resolve().parent
    base = cargar_yaml(carpeta / estudio["caso_base"])
    solidos = extraer_vertidas(carpeta / base["ifc"])
    args.salida.mkdir(parents=True, exist_ok=True)
    entradas = dict(ifc=sha256_archivo(carpeta / base["ifc"]),
                    hidratacion=sha256_archivo(carpeta / base["hormigones"]["M1"]["hidratacion"]["archivo"]),
                    codigo=huella_modelo())
    commit = subprocess.check_output(["git", "-C", str(RAIZ), "rev-parse", "HEAD"], text=True).strip()
    tareas, horarios = [], []
    for nombre, curva, clima in product(args.plan or controles, args.curva or estudio["curvas"],
                                      args.clima or [k for k, v in estudio["climas"].items() if v["peso"] > 0]):
        control = controles[nombre]
        filas = cronograma(solidos, estudio["capacidad_m3_h"],
                           dict(activacion=control["activacion"], espera_h=0), estudio["retiro_moldaje_h"])
        historico = estudio["climas"][clima]
        firma = dict(entradas, clima=[sha256_archivo(carpeta / historico["snapshot"] / n, texto=True)
                                      for n in ("forecast.json", "metadata.json")])
        if "respaldo" in historico:
            firma["respaldo"] = [sha256_archivo(carpeta / historico["respaldo"]["snapshot"] / n, texto=True)
                                 for n in ("forecast.json", "metadata.json")]
        datos = preparar_extension(base, estudio, control, historico, curva, estudio["niveles"][args.nivel], filas)
        D_h = filas[-1]["fin_h"]
        clave = clave_corrida(datos, firma, D_h, args.horizonte_extendido)
        tareas.append(dict(ruta=str(ruta_corrida(args.salida, args.nivel, nombre, curva, clima, clave)),
                           clave=clave, datos=datos, carpeta=str(carpeta), entradas=firma, commit=commit,
                           horizonte_extendido_h=args.horizonte_extendido, plan=nombre, curva=curva,
                           clima=clima, nivel=args.nivel, D_h=D_h))
        if not any(r["plan"] == nombre for r in horarios):
            inicio = datetime.fromisoformat(estudio["inicio"])
            horarios.extend(dict(plan=nombre, **f, inicio=(inicio + timedelta(hours=f["inicio_h"])).isoformat(),
                                 fin=(inicio + timedelta(hours=f["fin_h"])).isoformat(), zona=estudio["zona_horaria"])
                            for f in filas)
    pendientes = [t for t in tareas if leer_previo(t) is None]
    print(f"Seleccionadas {len(tareas)}; pendientes {len(pendientes)}.", flush=True)
    def informar(r):
        print(f"{r['plan']}/{r['nivel']}/{r['curva']}/{r['clima']}: "
              f"T={r['T_max_C']:.4f}, delta={r['delta_C']:.4f}, "
              f"horizonte={r['horizonte_h']}, abierto={r['pico_tardio']}, {r['segundos']:.1f}s", flush=True)

    pausa = args.salida / "PAUSAR"
    if args.procesos == 1:
        # Sin colas de multiprocessing: alternativa ante WinError 6 de Windows.
        for tarea in pendientes:
            if pausa.exists():
                break
            informar(calcular(tarea))
    else:
        with ProcessPoolExecutor(max_workers=args.procesos) as pool:
            restantes, en_curso = iter(pendientes), set()
            while True:
                while len(en_curso) < args.procesos and not pausa.exists():
                    tarea = next(restantes, None)
                    if tarea is None:
                        break
                    en_curso.add(pool.submit(calcular, tarea))
                if not en_curso:
                    break
                terminadas, en_curso = wait(en_curso, return_when=FIRST_COMPLETED)
                for futuro in terminadas:
                    informar(futuro.result())
    resultados = [leer_previo(t) for t in tareas]
    if pausa.exists():
        print("Pausa solicitada; corridas terminadas conservadas.", flush=True)
        return
    if any(r is None for r in resultados):
        raise ValueError("Faltan corridas seleccionadas.")
    escribir_tablas(args.salida, resultados, estudio)
    escribir_csv(args.salida / "cronogramas.csv", horarios)


if __name__ == "__main__":
    main()
