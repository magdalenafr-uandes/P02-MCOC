"""Tests de generación y lectura del modelo IFC (E01)."""

from __future__ import annotations

from pathlib import Path

import ifcopenshell

from mcplan.bim import CAMPOS_REQUERIDOS, guardar_modelo, leer_modelo

RAIZ = Path(__file__).resolve().parents[1]
IFC_VERSIONADO = RAIZ / "geometry" / "fundacion_e01_ejemplo.ifc"


def test_generar_y_leer_tres_vertidas(tmp_path):
    ruta = guardar_modelo(tmp_path / "modelo.ifc")
    assert ruta.is_file()

    resumen = leer_modelo(ruta)

    assert resumen.schema == "IFC4"
    assert [v.nombre for v in resumen.vertidas] == [
        "Vertida_01",
        "Vertida_02",
        "Vertida_03",
    ]
    assert len({v.guid for v in resumen.vertidas}) == 3

    for vertida in resumen.vertidas:
        assert vertida.clase == "IfcSlab"
        assert vertida.guid
        assert vertida.tiene_geometria
        for campo in CAMPOS_REQUERIDOS:
            assert campo in vertida.propiedades, f"Falta {campo} en {vertida.nombre}"

    assert any("DEGREE_CELSIUS" in u for u in resumen.unidades)
    assert any("METRE" in u for u in resumen.unidades)


def test_modelo_ifc_versionado_existe_y_se_lee():
    assert IFC_VERSIONADO.is_file(), (
        f"Falta el IFC versionado: {IFC_VERSIONADO}. "
        "Ejecute: python scripts/make_ifc.py"
    )
    resumen = leer_modelo(IFC_VERSIONADO)
    assert len(resumen.vertidas) == 3
    assert all(v.tiene_geometria for v in resumen.vertidas)


def test_ifc_contiene_estructura_espacial():
    modelo = ifcopenshell.open(str(IFC_VERSIONADO))
    assert modelo.by_type("IfcProject")
    assert modelo.by_type("IfcSite")
    assert modelo.by_type("IfcBuilding")
    assert modelo.by_type("IfcBuildingStorey")
    assert len(modelo.by_type("IfcSlab")) == 3
