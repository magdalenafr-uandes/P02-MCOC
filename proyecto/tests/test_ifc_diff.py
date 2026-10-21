"""Tests de la herramienta de comparación antes/después (ifc_diff).

Verifican que la herramienta detecta cambios de propiedades y geometría, y
que no reporta diferencias entre un estado y el mismo archivo. Ningún test
depende de una edición manual en Bonsai ni fija valores del archivo
versionado.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import ifcopenshell.api

from mcplan.bim.foundation import (
    PSET_FOUNDATION,
    construir_foundation,
)

RAIZ = Path(__file__).resolve().parents[1]
SCRIPTS = RAIZ / "scripts"


def _editar_tcoloc(modelo: ifcopenshell.file, guid: str, valor: float) -> None:
    producto = modelo.by_guid(guid)
    pset = next(
        relacion.RelatingPropertyDefinition
        for relacion in producto.IsDefinedBy
        if relacion.is_a("IfcRelDefinesByProperties")
        and relacion.RelatingPropertyDefinition.Name == PSET_FOUNDATION
    )
    ifcopenshell.api.run(
        "pset.edit_pset",
        modelo,
        pset=pset,
        properties={"TemperaturaColocacion_C": valor},
    )


def _editar_altura_prisma(
    modelo: ifcopenshell.file, guid: str, altura: float
) -> None:
    producto = modelo.by_guid(guid)
    solido = producto.Representation.Representations[0].Items[0]
    assert solido.is_a("IfcExtrudedAreaSolid"), solido.is_a()
    solido.Depth = altura


def _estado_desde_modelo(modelo: ifcopenshell.file, tmp_path, nombre: str) -> dict:
    sys.path.insert(0, str(SCRIPTS))
    try:
        from ifc_state import capturar_estado
    finally:
        sys.path.pop(0)
    ruta = tmp_path / nombre
    modelo.write(str(ruta))
    return capturar_estado(ruta)


def test_mismo_archivo_no_reporta_diferencias(tmp_path):
    sys.path.insert(0, str(SCRIPTS))
    try:
        from ifc_diff import comparar
        from ifc_state import capturar_estado
    finally:
        sys.path.pop(0)

    ruta = tmp_path / "foundation.ifc"
    construir_foundation().write(str(ruta))
    estado_a = capturar_estado(ruta)
    estado_b = capturar_estado(ruta)
    diferencias = comparar(estado_a, estado_b, tol_abs=1e-4, tol_rel=1e-6)
    # Solo pueden aparecer líneas "geometría: sin cambios".
    assert all("geometría: sin cambios" in d for d in diferencias)


def test_detecta_cambio_de_propiedad(tmp_path):
    sys.path.insert(0, str(SCRIPTS))
    try:
        from ifc_diff import comparar
    finally:
        sys.path.pop(0)

    # Un solo modelo en memoria: así los GUIDs coinciden entre archivos y el
    # diff no reporta vertidas "añadidas/eliminadas" por builds independientes.
    modelo = construir_foundation()
    estado_a = _estado_desde_modelo(modelo, tmp_path, "antes.ifc")

    guid_vertida_1 = _guid_vertida(modelo, vertida_id=1)
    _editar_tcoloc(modelo, guid_vertida_1, 19.0)
    estado_b = _estado_desde_modelo(modelo, tmp_path, "despues.ifc")

    diferencias = comparar(estado_a, estado_b, tol_abs=1e-4, tol_rel=1e-6)
    propiedades = [
        d for d in diferencias if "TemperaturaColocacion_C" in d
    ]
    assert len(propiedades) == 1
    assert "18" in propiedades[0] and "19" in propiedades[0]
    # La geometría no cambió: solo la línea de propiedad es un cambio real.
    reales = [d for d in diferencias if "geometría: sin cambios" not in d]
    assert len(reales) == 1


def test_detecta_cambio_geometrico_por_volumen_y_bbox(tmp_path):
    sys.path.insert(0, str(SCRIPTS))
    try:
        from ifc_diff import comparar
    finally:
        sys.path.pop(0)

    modelo = construir_foundation()
    estado_a = _estado_desde_modelo(modelo, tmp_path, "a.ifc")

    # Vertida_01 es un prisma (IfcExtrudedAreaSolid): cambiar la altura de la
    # extrusión altera volumen y bbox sin tocar los GUIDs.
    guid_v1 = _guid_vertida(modelo, vertida_id=1)
    _editar_altura_prisma(modelo, guid_v1, 0.66)
    estado_b = _estado_desde_modelo(modelo, tmp_path, "b.ifc")

    diferencias = comparar(estado_a, estado_b, tol_abs=1e-4, tol_rel=1e-6)
    geom = [d for d in diferencias if "geometría:" in d and "sin cambios" not in d]
    assert geom, "El cambio de altura debe reportarse como diferencia geométrica"
    texto = "\n".join(diferencias)
    assert "volumen_m3" in texto
    assert "bbox_max[2]" in texto


def test_cli_codigos_de_salida(tmp_path):
    modelo = construir_foundation()
    ruta_a = tmp_path / "a.ifc"
    modelo.write(str(ruta_a))
    guid_v1 = _guid_vertida(modelo, vertida_id=1)
    _editar_tcoloc(modelo, guid_v1, 19.0)
    ruta_b = tmp_path / "b.ifc"
    modelo.write(str(ruta_b))

    resultado_igual = subprocess.run(
        [sys.executable, str(SCRIPTS / "ifc_diff.py"), str(ruta_a), str(ruta_a)],
        capture_output=True,
        text=True,
    )
    assert resultado_igual.returncode == 0, resultado_igual.stdout + resultado_igual.stderr

    resultado_cambio = subprocess.run(
        [sys.executable, str(SCRIPTS / "ifc_diff.py"), str(ruta_a), str(ruta_b)],
        capture_output=True,
        text=True,
    )
    assert resultado_cambio.returncode == 1, (
        resultado_cambio.stdout + resultado_cambio.stderr
    )
    assert "TemperaturaColocacion_C" in resultado_cambio.stdout


def _guid_vertida(modelo: ifcopenshell.file, vertida_id: int) -> str:
    from ifcopenshell.util.element import get_psets

    from mcplan.bim.ifc_io import productos_vertida

    for producto in productos_vertida(modelo):
        if get_psets(producto)[PSET_FOUNDATION]["VertidaID"] == vertida_id:
            return producto.GlobalId
    raise AssertionError(f"No se encontró la vertida {vertida_id}")


def test_snapshot_json_redondo(tmp_path):
    """El snapshot se puede escribir y volver a leer sin pérdida de claves."""
    sys.path.insert(0, str(SCRIPTS))
    try:
        from ifc_state import capturar_estado
    finally:
        sys.path.pop(0)

    ruta = tmp_path / "foundation.ifc"
    construir_foundation().write(str(ruta))
    estado = capturar_estado(ruta)
    salida = tmp_path / "estado.json"
    with salida.open("w", encoding="utf-8") as archivo:
        json.dump(estado, archivo, indent=2, ensure_ascii=False, sort_keys=True)
    with salida.open("r", encoding="utf-8") as archivo:
        recargado = json.load(archivo)
    assert set(recargado["vertidas"]) == set(estado["vertidas"])
    assert recargado["totales"] == estado["totales"]
