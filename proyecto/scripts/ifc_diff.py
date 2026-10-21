"""Comparación antes/después de dos estados de vertidas IFC, por GlobalId.

Cada lado puede ser un snapshot JSON (salida de ``ifc_state.py``) o un
archivo IFC directo (se captura al vuelo). La comparación recorre las
vertidas por GlobalId y reporta:

- vertidas añadidas / eliminadas;
- cambios de nombre y clase;
- cambios de propiedades, pset por pset (comparación exacta; numéricos
  comparados tras normalizar int/float);
- cambios de geometría: bbox (mín/máx por coordenada, en metros) y volumen
  de malla (en m³), con tolerancia **absoluta** y **relativa**:

      |a - b| <= tol_abs + tol_rel · max(|a|, |b|)

  Tolerancias por defecto: tol_abs = 1e-4 (0,1 mm en coordenadas; 1e-4 m³ en
  volumen) y tol_rel = 1e-6. Se expresan en unidades SI coherentes. Sirven
  para absorber ruido numérico de re-triangulación de una misma geometría,
  no para decidir qué es "cambio de diseño": eso lo decide el usuario
  revisando el reporte.

**Alcance de la comparación geométrica** (limitación documentada): bbox y
volumen detectan desplazamientos, cambios de tamaño y la mayoría de los
cambios de forma, pero **no detectan todo cambio geométrico**. Ejemplos que
pasan desapercibidos: rotar un sólido simétrico (p. ej. un octágono regular)
alrededor de su eje, o cualquier alteración que conserve a la vez el
envolvente axial y el volumen. Para ese tipo de casos se necesita comparar
mallas o sólidos completos, fuera del alcance de esta herramienta. Los
cambios de propiedades del pset se comparan de forma exacta e independiente.

Códigos de salida: 0 = sin diferencias; 1 = hay diferencias; 2 = error de
uso o de lectura.

Uso:
    python scripts/ifc_diff.py estado_antes.json geometry/foundation.ifc
    python scripts/ifc_diff.py a.json b.json --tol-abs 1e-3 --tol-rel 1e-5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ifc_state import capturar_estado

TOL_ABS_DEFECTO = 1e-4  # m (coordenadas) o m³ (volumen)
TOL_REL_DEFECTO = 1e-6


def _cargar_estado(ruta: Path) -> tuple[dict, str]:
    """Carga un estado desde JSON o desde un IFC; devuelve (estado, fuente)."""
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el archivo: {ruta}")
    if ruta.suffix.lower() == ".json":
        with ruta.open("r", encoding="utf-8") as archivo:
            return json.load(archivo), f"JSON {ruta}"
    return capturar_estado(ruta), f"IFC {ruta}"


def _dentro_de_tolerancia(a: float, b: float, tol_abs: float, tol_rel: float) -> bool:
    return abs(a - b) <= tol_abs + tol_rel * max(abs(a), abs(b))


def _valores_iguales(a, b) -> bool:
    """Igualdad de valores de propiedad: numéricos normalizados, resto exacto."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) == float(b)
    return a == b


def _fmt(valor) -> str:
    if isinstance(valor, float):
        return f"{valor:g}"
    return str(valor)


def comparar(
    estado_a: dict,
    estado_b: dict,
    tol_abs: float,
    tol_rel: float,
) -> list[str]:
    """Lista de líneas de diferencias (vacía si no hay diferencias)."""
    diferencias: list[str] = []

    guias_a = set(estado_a.get("vertidas", {}))
    guias_b = set(estado_b.get("vertidas", {}))

    for guid in sorted(guias_a - guias_b):
        datos = estado_a["vertidas"][guid]
        diferencias.append(
            f"ELIMINADA  {guid} ({datos.get('nombre', '?')}) — presente solo en A"
        )
    for guid in sorted(guias_b - guias_a):
        datos = estado_b["vertidas"][guid]
        diferencias.append(
            f"AÑADIDA    {guid} ({datos.get('nombre', '?')}) — presente solo en B"
        )

    for guid in sorted(guias_a & guias_b):
        va = estado_a["vertidas"][guid]
        vb = estado_b["vertidas"][guid]
        etiqueta = f"{guid} ({va.get('nombre', '?')})"

        for campo in ("nombre", "clase"):
            if va.get(campo) != vb.get(campo):
                diferencias.append(
                    f"{etiqueta}  {campo}: {_fmt(va.get(campo))} -> {_fmt(vb.get(campo))}"
                )

        psets_a = va.get("propiedades", {})
        psets_b = vb.get("propiedades", {})
        for pset in sorted(set(psets_a) | set(psets_b)):
            props_a = psets_a.get(pset, {})
            props_b = psets_b.get(pset, {})
            for prop in sorted(set(props_a) | set(props_b)):
                valor_a = props_a.get(prop)
                valor_b = props_b.get(prop)
                if not _valores_iguales(valor_a, valor_b):
                    diferencias.append(
                        f"{etiqueta}  {pset}.{prop}: "
                        f"{_fmt(valor_a)} -> {_fmt(valor_b)}"
                    )

        geom_cambios: list[str] = []
        for etiqueta_geom, clave in (
            ("bbox_min", "bbox_min"),
            ("bbox_max", "bbox_max"),
        ):
            lista_a = va.get(clave) or []
            lista_b = vb.get(clave) or []
            if len(lista_a) != len(lista_b):
                geom_cambios.append(f"{etiqueta_geom}: dimensionalidad distinta")
                continue
            for i, (coord_a, coord_b) in enumerate(zip(lista_a, lista_b)):
                if not _dentro_de_tolerancia(coord_a, coord_b, tol_abs, tol_rel):
                    geom_cambios.append(
                        f"{etiqueta_geom}[{i}]: {coord_a:.6g} -> {coord_b:.6g} "
                        f"(Δ={abs(coord_a - coord_b):.3e} > tol)"
                    )
        vol_a = va.get("volumen_m3")
        vol_b = vb.get("volumen_m3")
        if (
            isinstance(vol_a, (int, float))
            and isinstance(vol_b, (int, float))
            and not _dentro_de_tolerancia(vol_a, vol_b, tol_abs, tol_rel)
        ):
            geom_cambios.append(
                f"volumen_m3: {vol_a:.6g} -> {vol_b:.6g} "
                f"(Δ={abs(vol_a - vol_b):.3e} > tol)"
            )

        if geom_cambios:
            diferencias.append(f"{etiqueta}  geometría:")
            diferencias.extend(f"    {linea}" for linea in geom_cambios)
        else:
            diferencias.append(
                f"{etiqueta}  geometría: sin cambios "
                f"(tol abs={tol_abs:g}, rel={tol_rel:g})"
            )

    return diferencias


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compara dos estados de vertidas IFC (JSON o IFC) por GlobalId: "
            "propiedades exactas, geometría con tolerancias."
        )
    )
    parser.add_argument("estado_a", type=Path, help="Estado 'antes' (JSON o IFC).")
    parser.add_argument("estado_b", type=Path, help="Estado 'después' (JSON o IFC).")
    parser.add_argument(
        "--tol-abs",
        type=float,
        default=TOL_ABS_DEFECTO,
        help=f"Tolerancia absoluta para geometría (defecto {TOL_ABS_DEFECTO:g}).",
    )
    parser.add_argument(
        "--tol-rel",
        type=float,
        default=TOL_REL_DEFECTO,
        help=f"Tolerancia relativa para geometría (defecto {TOL_REL_DEFECTO:g}).",
    )
    args = parser.parse_args()

    if args.tol_abs < 0 or args.tol_rel < 0:
        parser.error("Las tolerancias deben ser no negativas.")

    try:
        estado_a, fuente_a = _cargar_estado(args.estado_a)
        estado_b, fuente_b = _cargar_estado(args.estado_b)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as error:
        print(f"Error al cargar los estados: {error}", file=sys.stderr)
        raise SystemExit(2) from error

    print(f"Estado A: {fuente_a} — {estado_a.get('totales', {})}")
    print(f"Estado B: {fuente_b} — {estado_b.get('totales', {})}")
    print()

    diferencias = comparar(estado_a, estado_b, args.tol_abs, args.tol_rel)

    for linea in diferencias:
        print(linea)

    print()
    n_cambios = len(
        [
            linea
            for linea in diferencias
            if "geometría: sin cambios" not in linea
        ]
    )
    if n_cambios == 0:
        print("Sin diferencias (propiedades exactas; geometría dentro de tolerancia).")
        raise SystemExit(0)
    print(f"Total de líneas con diferencias: {n_cambios}")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
