"""Valida y conserva localmente la evidencia de los controles adicionales."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import zipfile

import numpy as np

from defensa import (RAIZ, cargar_yaml, clave_corrida, escribir_csv, escribir_tablas,
                     huella_modelo, sha256_archivo)


def verificar(r, estudio, extendido):
    caso = deepcopy(r["caso"])
    if r["periodo_base"]:
        caso["simulacion"]["duracion_h"] = estudio["horizonte_h"]
    # argparse conserva defaults enteros pero convierte opciones explícitas a float.
    # 672 y 672.0 representan el mismo horizonte; se admite cada serialización.
    claves = {clave_corrida(caso, r["entradas"], r["D_h"], extendido)}
    if float(extendido).is_integer():
        claves.add(clave_corrida(caso, r["entradas"], r["D_h"], int(extendido)))
        claves.add(clave_corrida(caso, r["entradas"], r["D_h"], float(extendido)))
    assert r["clave"] in claves, "Clave/configuración distinta"
    assert r["entradas"]["codigo"] == huella_modelo(), "El solver cambió"
    for campo, ruta in (("ifc", caso["ifc"]), ("hidratacion", caso["hormigones"]["M1"]["hidratacion"]["archivo"])):
        assert r["entradas"][campo] == sha256_archivo(RAIZ / "configs" / ruta), campo
    for campo, clima in (("clima", caso["clima"]), ("respaldo", caso["clima"].get("respaldo"))):
        if clima:
            assert r["entradas"][campo] == [sha256_archivo(RAIZ / "configs" / clima["snapshot"] / n, texto=True)
                                           for n in ("forecast.json", "metadata.json")], campo
    s = r["series"]
    delta = np.array(s["T_max_C"]) - s["T_superficie_min_C"]
    assert np.allclose(delta, s["delta_C"], atol=1e-10)
    assert np.isclose(np.max(delta), r["delta_C"], atol=1e-10)
    assert r["I_F"] == max(r["I_T"], r["I_delta"])
    assert r["I_T"] == int(r["T_max_C"] > 70)
    assert r["I_delta"] == int(r["delta_C"] > 20)
    b = r["balance_J"]
    escala = max(abs(b[k]) for k in ("E_final_J", "E_inicial_J", "colocacion_J", "hidratacion_J"))
    assert abs(b["residuo_J"]) / escala < 1e-8
    return abs(b["residuo_J"]) / escala


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--entrada", type=Path, default=RAIZ / "results/defensa_extension_larga")
    p.add_argument("--salida", type=Path, default=RAIZ / "docs/evidencia_extension_defensa")
    p.add_argument("--estudio", type=Path, default=RAIZ / "configs/defensa_extension_clima.yaml")
    p.add_argument("--horizonte-extendido", type=float, default=672.0)
    args = p.parse_args()
    estudio = cargar_yaml(args.estudio)
    lista = [(ruta, json.loads(ruta.read_text(encoding="utf-8"))) for ruta in sorted(args.entrada.glob("*__*__*__*__*.json"))]
    if not lista:
        raise ValueError("No hay corridas completas.")
    identidades = [(r["nivel"], r["plan"], r["curva"], r["clima"]) for _, r in lista]
    if len(identidades) != len(set(identidades)):
        raise ValueError("Dos configuraciones para una misma identidad; revisar antes de agregar.")
    residuos = [verificar(r, estudio, args.horizonte_extendido) for _, r in lista]
    args.salida.mkdir(parents=True, exist_ok=True)
    escribir_tablas(args.salida, [r for _, r in lista], estudio)
    puntos = []
    for _, r in lista:
        puntos.append(dict(plan=r["plan"], nivel=r["nivel"], curva=r["curva"], clima=r["clima"],
                           clave=r["clave"], commit=r["commit"], horizonte_h=r["horizonte_h"],
                           T_colocacion_C=r["caso"]["vertidas"]["defecto"]["T_colocacion_C"],
                           espesor_m=r["caso"]["protecciones"]["eps_extension"]["espesor_m"],
                           margen_T_C=70-r["T_max_C"], margen_delta_C=20-r["delta_C"],
                           punto_frio=json.dumps(r["punto_frio"], ensure_ascii=False),
                           punto_caliente=json.dumps(r["punto_caliente"], ensure_ascii=False)))
    escribir_csv(args.salida / "trazabilidad.csv", puntos)
    with zipfile.ZipFile(args.salida / "corridas.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for ruta, _ in lista:
            z.write(ruta, ruta.name)
    with zipfile.ZipFile(args.salida / "corridas.zip") as z:
        assert z.testzip() is None and len(z.namelist()) == len(lista)
    estado = dict(corridas=len(lista), horizonte_extendido_h=args.horizonte_extendido,
                  max_residuo_relativo=max(residuos), solver=huella_modelo(),
                  nota="Sólo agrega matrices completas por plan/nivel. Revisar horizontes abiertos y resolución antes de recomendar.")
    (args.salida / "estado.json").write_text(json.dumps(estado, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(lista)} corridas verificadas. Residuo relativo máximo {max(residuos):.3e}.")


if __name__ == "__main__":
    main()
