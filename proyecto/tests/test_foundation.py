"""Tests del IFC de la fundación (guía Bonsai, 5 vertidas).

La selección de vertidas es semántica (pset UANDES_HormigonMasivo +
VertidaID), no por prefijo del nombre; un test de robustez lo verifica.
Ningún test fija la temperatura de colocación del archivo versionado: ese
valor puede cambiar tras una edición manual en Bonsai (round-trip E02).
"""

from __future__ import annotations

from pathlib import Path

import ifcopenshell
import ifcopenshell.util.element
import pytest

from mcplan.bim.foundation import (
    PSET_FOUNDATION,
    VERTIDAS_FOUNDATION,
    construir_foundation,
    guardar_foundation,
    resumen_geometrico,
    volumen_analitico,
)
from mcplan.bim.ifc_io import leer_modelo, productos_vertida

RAIZ = Path(__file__).resolve().parents[1]
IFC_FOUNDATION = RAIZ / "geometry" / "foundation.ifc"

# Volúmenes aproximados de la tabla de la sección 19 de la guía Bonsai.
VOLUMENES_GUIA_M3 = {
    "Vertida_01": 147.63,
    "Vertida_02": 147.63,
    "Vertida_03": 214.22,
    "Vertida_04": 88.92,
    "Vertida_05": 38.48,
}


def _productos_vertida(modelo: ifcopenshell.file):
    return productos_vertida(modelo)


def test_construir_foundation_cinco_ifc_footing():
    modelo = construir_foundation()
    assert modelo.schema == "IFC4"
    productos = _productos_vertida(modelo)
    assert [p.Name for p in productos] == [f"Vertida_0{i}" for i in range(1, 6)]
    assert all(p.is_a("IfcFooting") for p in productos)
    assert len({p.GlobalId for p in productos}) == 5


def test_estructura_espacial_completa():
    modelo = construir_foundation()
    assert modelo.by_type("IfcProject")
    assert modelo.by_type("IfcSite")
    assert modelo.by_type("IfcBuilding")
    assert modelo.by_type("IfcBuildingStorey")
    nivel = modelo.by_type("IfcBuildingStorey")[0]
    assert nivel.Elevation == 0.0
    contained = nivel.ContainsElements
    assert len(contained) == 1
    assert len(contained[0].RelatedElements) == 5


def test_pset_uandes_hormigon_masivo():
    modelo = construir_foundation()
    for producto in _productos_vertida(modelo):
        psets = ifcopenshell.util.element.get_psets(producto)
        assert PSET_FOUNDATION in psets
        assert "Pset_HormigonMasivo" not in psets
        props = psets[PSET_FOUNDATION]
        assert props["VertidaID"] in (1, 2, 3, 4, 5)
        assert props["TemperaturaColocacion_C"] == 18.0
        assert props["TipoHormigon"] == "M1"
        assert props["RetiroMoldaje_h"] == 72.0


def test_deteccion_semantica_no_depende_del_nombre(tmp_path):
    """Cambiar el nombre de una vertida no altera su detección."""
    modelo = construir_foundation()
    primera = productos_vertida(modelo)[0]
    primera.Name = "Cimiento_Andes"
    ruta = tmp_path / "renombrada.ifc"
    modelo.write(str(ruta))

    resumen = leer_modelo(ruta)
    assert len(resumen.vertidas) == 5
    assert resumen.vertidas[0].nombre == "Cimiento_Andes"
    assert all(v.advertencias == () for v in resumen.vertidas)


def test_leer_modelo_detecta_cinco_en_archivo_generado(tmp_path):
    ruta = guardar_foundation(tmp_path / "foundation.ifc")
    resumen = leer_modelo(ruta)
    assert resumen.schema == "IFC4"
    assert len(resumen.vertidas) == 5
    assert [v.propiedades["VertidaID"] for v in resumen.vertidas] == [1, 2, 3, 4, 5]
    assert all(v.tiene_geometria for v in resumen.vertidas)
    assert all(v.clase == "IfcFooting" for v in resumen.vertidas)


def test_bbox_y_alturas_según_guia(tmp_path):
    ruta = guardar_foundation(tmp_path / "foundation.ifc")
    resumen = {g.nombre: g for g in resumen_geometrico(ruta)}

    # La guía exige 18 m entre caras opuestas del octágono exterior.
    for nombre in ("Vertida_01", "Vertida_02", "Vertida_03"):
        xmin, ymin, zmin = resumen[nombre].bbox_min
        xmax, ymax, zmax = resumen[nombre].bbox_max
        assert xmax - xmin == pytest.approx(18.0, abs=1e-3)
        assert ymax - ymin == pytest.approx(18.0, abs=1e-3)
        assert xmin == pytest.approx(-xmax, abs=1e-6)
        assert ymin == pytest.approx(-ymax, abs=1e-6)
        assert zmin >= -1e-9

    # Pedestal: 7 m de diámetro, base en z=3.30, tope en z=4.30.
    pedestal = resumen["Vertida_05"]
    assert pedestal.bbox_max[0] - pedestal.bbox_min[0] == pytest.approx(7.0, abs=1e-3)
    assert pedestal.bbox_min[2] == pytest.approx(3.30, abs=1e-6)
    assert pedestal.bbox_max[2] == pytest.approx(4.30, abs=1e-6)


def test_volumenes_malla_vs_analítico_y_guia(tmp_path):
    ruta = guardar_foundation(tmp_path / "foundation.ifc")
    for geo in resumen_geometrico(ruta):
        esperado = next(v for v in VERTIDAS_FOUNDATION if v.nombre == geo.nombre)
        analitico = volumen_analitico(esperado)
        assert geo.volumen_m3 == pytest.approx(analitico, rel=1e-9)
        # La guía reporta volúmenes "aproximados": tolerancia del 1 %.
        assert geo.volumen_m3 == pytest.approx(
            VOLUMENES_GUIA_M3[geo.nombre], rel=0.01
        )


def test_volumen_analítico_tabla_guia():
    """Los volúmenes analíticos de la geometría docente calzan con la sección 19."""
    for vertida in VERTIDAS_FOUNDATION:
        v = volumen_analitico(vertida)
        assert v == pytest.approx(VOLUMENES_GUIA_M3[vertida.nombre], rel=0.01)


def test_archivo_versionado_existe_y_es_consistente():
    """El IFC versionado tiene 5 vertidas con pset; no fija valores de propiedades.

    Es deliberadamente laxo en valores: el archivo puede haber sido editado
    manualmente en Bonsai (round-trip E02) y seguir siendo consistente.
    """
    assert IFC_FOUNDATION.is_file(), (
        f"Falta el IFC versionado: {IFC_FOUNDATION}. "
        "Genera con: python scripts/make_foundation.py --forzar"
    )
    resumen = resumen_geometrico(IFC_FOUNDATION)
    assert len(resumen) == 5
    assert all(g.volumen_m3 > 0.0 for g in resumen)

    modelo = ifcopenshell.open(str(IFC_FOUNDATION))
    productos = productos_vertida(modelo)
    assert len(productos) == 5
    for producto in productos:
        assert PSET_FOUNDATION in ifcopenshell.util.element.get_psets(producto)


def test_regeneration_produce_modelo_equivalente(tmp_path):
    ruta = tmp_path / "foundation.ifc"
    guardar_foundation(ruta)
    modelo_viejo = ifcopenshell.open(str(ruta))
    guardar_foundation(ruta)
    modelo_nuevo = ifcopenshell.open(str(ruta))
    assert modelo_viejo.schema == modelo_nuevo.schema
    assert len(modelo_nuevo.by_type("IfcFooting")) == 5
    nombres_viejos = sorted(p.Name for p in _productos_vertida(modelo_viejo))
    nombres_nuevos = sorted(p.Name for p in _productos_vertida(modelo_nuevo))
    assert nombres_viejos == nombres_nuevos
