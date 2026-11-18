"""Compara el candidato térmico con cargas de 8 m³ cada 12 minutos."""

from __future__ import annotations

import argparse
from dataclasses import replace
from itertools import product
import math
from pathlib import Path
import subprocess
from time import perf_counter

import numpy as np

from defensa import (
    HORA, RAIZ, calcular, cargar_yaml, clave_corrida, cronograma, escribir_tablas,
    guardar_json, huella_modelo, leer_previo, metricas, ruta_corrida, sha256_archivo,
)
from explorar_defensa import preparar_extension
from mcplan.bim.mallas_ifc import extraer_vertidas
from mcplan.bim.voxelizador import pesos_area
from mcplan.caso.config import leer_config
from mcplan.caso.pipeline import ejecutar_pipeline
from mcplan.thermal.etapas import DominioVoxel, SimuladorEtapas

INTERVALO_S = 12 * 60
VOLUMEN_CARGA_M3 = 8.0


# [MAPA:colocacion-progresiva] proyección de la cadencia de suministro a voxeles y reloj IFC
def dividir_grilla(grilla, plan, filas, capacidad):
    """Parte el flujo continuo en cargas globales, respetando el orden de los sólidos."""
    if not math.isclose(capacidad * INTERVALO_S / HORA, VOLUMEN_CARGA_M3):
        raise ValueError("La campaña usa 8 m³ cada 12 min a 40 m³/h.")
    ids = grilla.vertida_id
    lotes = np.zeros(ids.shape, dtype=np.int16)
    por_id = {p.vertida_id: p for p in plan}
    asignaciones, porciones = [], []
    acumulado = 0.0
    for fila in filas:
        vid = fila["vertida"]
        original = por_id[vid]
        x, y, z = np.nonzero(ids == vid)
        orden = np.lexsort((y, x, z))
        indices = np.ravel_multi_index((x[orden], y[orden], z[orden]), ids.shape)
        volumen = fila["volumen_m3"]
        fin = acumulado + volumen
        anterior = 0
        primera = math.floor(acumulado / VOLUMEN_CARGA_M3)
        ultima = math.ceil(fin / VOLUMEN_CARGA_M3)
        for carga in range(primera, ultima):
            v0 = max(acumulado, carga * VOLUMEN_CARGA_M3)
            v1 = min(fin, (carga + 1) * VOLUMEN_CARGA_M3)
            limite = round(len(indices) * (v1 - acumulado) / volumen)
            if limite <= anterior:
                raise ValueError(f"Porción {carga + 1}/{vid} sin voxeles a esta resolución.")
            identificador = len(porciones) + 1
            t0 = v0 / capacidad * HORA
            lotes.ravel()[indices[anterior:limite]] = identificador
            asignaciones.append(replace(
                original, vertida_id=identificador, inicio_s=t0,
                retiro_moldaje_s=original.retiro_moldaje_s + original.inicio_s - t0,
            ))
            porciones.append(dict(id=identificador, carga=carga + 1, vertida=vid,
                                  inicio_s=t0, fin_s=v1/capacidad*HORA,
                                  volumen_m3=v1-v0, voxeles=limite-anterior))
            anterior = limite
        if anterior != len(indices):
            raise ValueError(f"Volumen incompleto en el sólido {vid}.")
        acumulado = fin
    if not np.array_equal(lotes > 0, ids > 0):
        raise ValueError("El fraccionamiento cambió la geometría de hormigón.")
    return lotes, asignaciones, porciones


class SimuladorPorTandas(SimuladorEtapas):
    """Activa por porción y comunica los máximos de los cinco sólidos originales."""

    def __init__(self, resultado, lotes, plan, progreso):
        config, grilla = resultado.config, resultado.grilla
        self.ids_ifc = grilla.vertida_id
        self.vertidas_ifc = tuple(p.vertida_id for p in resultado.plan)
        pesos = pesos_area(resultado.solidos, grilla) if config.malla.corregir_area else None
        super().__init__(
            DominioVoxel(lotes, grilla.es_suelo, grilla.paso, pesos), plan,
            config.hormigones, config.ambiente, config.base, config.tiempo,
            config.suelo, config.T_suelo_inicial_C,
            profundidad_superficie_m=config.criterios.profundidad_superficie_m,
            progreso=progreso,
        )

    def _registrar(self, res, t, T, activo, caras, ids, forzar_campo=False):
        if not res.tiempos_s:
            res.T_max_vertida_C = {vid: [] for vid in self.vertidas_ifc}
        super()._registrar(res, t, T, activo, caras, self.ids_ifc, forzar_campo)


def seccion(grilla, lotes):
    """Corte x-z de la grilla en el centro del eje y para el HTML."""
    plano = lotes[:, grilla.forma[1] // 2, :].T
    celdas = np.argwhere(plano > 0)
    z0, x0 = celdas.min(axis=0)
    z1, x1 = celdas.max(axis=0) + 1
    return dict(celdas=plano[z0:z1, x0:x1].tolist(), dx_m=grilla.paso[0], dz_m=grilla.paso[2])


def simular(tarea):
    inicio = perf_counter()
    datos = tarea["datos"]
    periodo_base = None
    for horizonte in (datos["simulacion"]["duracion_h"], tarea["horizonte_extendido_h"]):
        caso = {**datos, "simulacion": {**datos["simulacion"], "duracion_h": horizonte}}
        config = leer_config(caso, Path(tarea["carpeta"]))
        resultado = ejecutar_pipeline(config, simular=False)
        lotes, plan, porciones = dividir_grilla(resultado.grilla, resultado.plan,
                                              tarea["filas"], tarea["capacidad_m3_h"])
        pendiente = 168 * HORA

        def avance(t, total):
            nonlocal pendiente
            if t >= pendiente or t >= total:
                print(f"  {tarea['curva']} / {tarea['clima']}: {t/HORA:.0f}/{total/HORA:.0f} h simuladas", flush=True)
                pendiente += 168 * HORA

        corrida = SimuladorPorTandas(resultado, lotes, plan, avance)
        if avisos := corrida.advertencias_apoyo():
            raise ValueError(f"Orden sin soporte: {avisos}")
        resultado.simulacion = corrida.ejecutar()
        if not np.array_equal(resultado.simulacion.activo_final, resultado.grilla.vertida_id > 0):
            raise ValueError("No se activó todo el hormigón.")
        resumen = metricas(resultado)
        if not resumen["pico_tardio"] or horizonte == tarea["horizonte_extendido_h"]:
            break
        periodo_base = {k: resumen[k] for k in ("T_max_C", "delta_C", "horizonte_h")}

    balance = resumen["balance_J"]
    escala = max(abs(v) for v in balance.values())
    residual = abs(balance["residuo_J"]) / escala
    esperado = sum(p["voxeles"] for p in porciones) * resultado.grilla.volumen_voxel
    material = config.hormigones["M1"].material
    energia = material.rho * material.cp * esperado * 12
    if residual > 1e-12 or not math.isclose(energia, balance["colocacion_J"], rel_tol=1e-12):
        raise ValueError("No cierra el balance de energía de la colocación progresiva.")
    resumen.update({k: tarea[k] for k in ("clave", "commit", "plan", "curva", "clima", "nivel", "entradas", "D_h")})
    resumen.update(caso=caso, periodo_base=periodo_base, porciones=porciones,
                   seccion=seccion(resultado.grilla, lotes), cronograma=tarea["filas"],
                   volumen_grilla_m3=esperado, residuo_relativo=residual, segundos=perf_counter()-inicio,
                   I_T=int(resumen["T_max_C"] > config.criterios.T_max_C),
                   I_delta=int(resumen["delta_C"] > config.criterios.delta_T_C))
    resumen["I_F"] = max(resumen["I_T"], resumen["I_delta"])
    guardar_json(Path(tarea["ruta"]), resumen)
    return resumen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nivel", choices=("barrido", "fino", "confirmacion"), default="barrido")
    parser.add_argument("--curva", action="append", choices=("M1_SS", "M1_22A"))
    parser.add_argument("--clima", action="append", choices=("era5_2023", "era5_2024", "era5_2025"))
    parser.add_argument("--modo", choices=("progresiva", "sucesiva"), default="progresiva")
    parser.add_argument("--salida", type=Path, default=RAIZ / "results/colocacion_progresiva")
    args = parser.parse_args()
    carpeta = RAIZ / "configs"
    estudio = cargar_yaml(carpeta / "defensa_extension_clima.yaml")
    base = cargar_yaml(carpeta / estudio["caso_base"])
    controles = cargar_yaml(carpeta / "defensa_extension.yaml")["planes"]
    control = controles["eps200_T12_sucesiva"]
    solidos = extraer_vertidas(carpeta / base["ifc"])
    filas = cronograma(solidos, estudio["capacidad_m3_h"], dict(activacion="sucesiva", espera_h=0),
                      estudio["retiro_moldaje_h"])
    entradas = dict(ifc=sha256_archivo(carpeta / base["ifc"]), codigo=huella_modelo(),
                    hidratacion=sha256_archivo(carpeta / base["hormigones"]["M1"]["hidratacion"]["archivo"]))
    if args.modo == "progresiva":
        entradas["colocacion_progresiva"] = sha256_archivo(Path(__file__), texto=True)
    commit = subprocess.check_output(["git", "-C", str(RAIZ), "rev-parse", "HEAD"], text=True).strip()
    nombre = f"eps200_T12_{args.modo}"
    args.salida.mkdir(parents=True, exist_ok=True)
    resultados = []
    climas = args.clima or [k for k, v in estudio["climas"].items() if v["peso"] > 0]
    for curva, clima in product(args.curva or estudio["curvas"], climas):
        if (args.salida / "PAUSAR").exists():
            break
        archivo_clima = estudio["climas"][clima]
        firma = dict(entradas, clima=[sha256_archivo(carpeta / archivo_clima["snapshot"] / n, texto=True)
                                     for n in ("forecast.json", "metadata.json")])
        datos = preparar_extension(base, estudio, control, archivo_clima, curva, estudio["niveles"][args.nivel], filas)
        duracion = filas[-1]["fin_h"]
        horizonte = estudio["horizonte_extendido_h"]
        clave = clave_corrida(datos, firma, duracion, horizonte)
        tarea = dict(ruta=str(ruta_corrida(args.salida, args.nivel, nombre, curva, clima, clave)),
                     datos=datos, carpeta=str(carpeta), entradas=firma, clave=clave, commit=commit,
                     horizonte_extendido_h=horizonte, plan=nombre, curva=curva, clima=clima,
                     nivel=args.nivel, D_h=duracion, filas=filas, capacidad_m3_h=estudio["capacidad_m3_h"])
        previo = leer_previo(tarea)
        print(f"{args.nivel} / {args.modo} / {curva} / {clima} ({'guardada' if previo else 'inicio'})", flush=True)
        r = previo if previo else (simular(tarea) if args.modo == "progresiva" else calcular(tarea))
        print(f"  T={r['T_max_C']:.4f} °C, delta={r['delta_C']:.4f} °C, "
              f"horizonte={r['horizonte_h']}, abierto={r['pico_tardio']}, {r['segundos']:.1f}s", flush=True)
        resultados.append(r)
    escribir_tablas(args.salida, resultados, estudio)


if __name__ == "__main__":
    main()
