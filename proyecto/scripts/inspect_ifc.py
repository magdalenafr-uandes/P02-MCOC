"""Inspección unificada del IFC de la fundación con IfcOpenShell.

Lista las vertidas (selección semántica por pset UANDES_HormigonMasivo),
sus GUIDs, clases, propiedades, y verifica la geometría: bounding boxes en
coordenadas de mundo y comparación del volumen de malla con el analítico y
con la tabla de la guía Bonsai (tolerancia del 1 %).

Uso:
    python scripts/inspect_ifc.py
    python scripts/inspect_ifc.py geometry/foundation.ifc
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mcplan.bim.foundation import (
    PSET_FOUNDATION,
    VERTIDAS_FOUNDATION,
    resumen_geometrico,
    volumen_analitico,
)
from mcplan.bim.ifc_io import CAMPOS_REQUERIDOS, leer_modelo

RAIZ = Path(__file__).resolve().parents[1]

# Volúmenes aproximados de la sección 19 de la guía Bonsai [m³].
VOLUMENES_GUIA_M3 = {
    "Vertida_01": 147.63,
    "Vertida_02": 147.63,
    "Vertida_03": 214.22,
    "Vertida_04": 88.92,
    "Vertida_05": 38.48,
}


def _valor(propiedades: dict, campo: str) -> str:
    if campo not in propiedades:
        return "—"
    valor = propiedades[campo]
    if isinstance(valor, float):
        return f"{valor:g}"
    return str(valor)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Inspecciona el IFC de la fundación: vertidas, propiedades, "
            "bbox y volúmenes."
        )
    )
    parser.add_argument(
        "ruta",
        nargs="?",
        type=Path,
        default=RAIZ / "geometry" / "foundation.ifc",
        help="Archivo IFC a inspeccionar (por defecto geometry/foundation.ifc).",
    )
    args = parser.parse_args()

    resumen = leer_modelo(args.ruta)

    print(f"Archivo:  {args.ruta}")
    print(f"Esquema:  {resumen.schema}")
    print(f"Proyecto: {resumen.proyecto}")
    print("Unidades:")
    for unidad in resumen.unidades:
        print(f"  - {unidad}")
    print()

    if not resumen.vertidas:
        raise SystemExit(
            f"No se encontraron vertidas: ningún IfcProduct lleva el pset "
            f"{PSET_FOUNDATION} con VertidaID."
        )

    print(f"Selección: pset {PSET_FOUNDATION} con VertidaID (clase esperada IfcFooting)")
    print(
        f"{'Vertida':<14} {'Clase':<12} {'GUID':<24} "
        f"{'VertidaID':>9} {'Inicio_h':>9} {'Tcoloc_C':>9}"
    )
    print("-" * 82)
    for vertida in resumen.vertidas:
        props = vertida.propiedades
        print(
            f"{vertida.nombre:<14} {vertida.clase:<12} {vertida.guid:<24} "
            f"{_valor(props, 'VertidaID'):>9} "
            f"{_valor(props, 'Inicio_h'):>9} "
            f"{_valor(props, 'TemperaturaColocacion_C'):>9}"
        )
    print()

    advertencias = [
        (v.nombre, adv) for v in resumen.vertidas for adv in v.advertencias
    ]
    if advertencias:
        print("Advertencias:")
        for nombre, adv in advertencias:
            print(f"  - {nombre}: {adv}")
        print()

    print("Propiedades requeridas por vertida:")
    for vertida in resumen.vertidas:
        print(f"[{vertida.nombre}] geometría: {'sí' if vertida.tiene_geometria else 'no'}")
        for campo in CAMPOS_REQUERIDOS:
            print(f"  {campo}: {_valor(vertida.propiedades, campo)}")
        faltantes = [c for c in CAMPOS_REQUERIDOS if c not in vertida.propiedades]
        if faltantes:
            print(f"  FALTAN: {', '.join(faltantes)}")
        print()

    esperados = {v.nombre: v for v in VERTIDAS_FOUNDATION}
    resumen_geo = resumen_geometrico(args.ruta)
    print(f"{'Vertida':<12} {'V malla':>10} {'V analítico':>12} {'d rel':>10}  BBox size [m]")
    print("-" * 78)
    for geo in resumen_geo:
        esperado = esperados.get(geo.nombre)
        v_ana = volumen_analitico(esperado) if esperado else float("nan")
        delta = abs(geo.volumen_m3 - v_ana) / v_ana if v_ana else float("nan")
        size = tuple(
            round(float(b - a), 4) for a, b in zip(geo.bbox_min, geo.bbox_max)
        )
        guia = VOLUMENES_GUIA_M3.get(geo.nombre)
        guia_txt = f"{guia:.2f}" if guia is not None else "—"
        print(
            f"{geo.nombre:<12} {geo.volumen_m3:>10.2f} {v_ana:>12.2f} "
            f"{delta:>10.2e}  {size}  (guía: {guia_txt})"
        )

    total = sum(g.volumen_m3 for g in resumen_geo)
    print()
    print(f"Volumen total de malla: {total:.2f} m³")
    print(f"Número de vertidas: {len(resumen.vertidas)}")


if __name__ == "__main__":
    main()
