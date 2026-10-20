"""Generación de un IFC4 de ejemplo con tres vertidas (E01).

IMPORTANTE
----------
La geometría de este modelo es **didáctica y no oficial**: solo busca tener
tres elementos BIM distintos con identidad, unidades, estructura espacial,
geometría y propiedades. La geometría oficial de la fundación debe ser
entregada o validada por el profesor.

El archivo se genera con IfcOpenShell desde Python. Esto **no** acredita haber
abierto ni editado el modelo en la interfaz de Bonsai.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import ifcopenshell
import ifcopenshell.api
import numpy as np


@dataclass(frozen=True)
class VertidaEjemplo:
    nombre: str
    vertida_id: str
    tipo_hormigon: str
    inicio_planificado: str
    temperatura_colocacion_c: float
    moldaje: str
    aislacion: str
    retiro_moldaje_h: float
    origen_x: float
    largo: float = 4.0
    ancho: float = 3.0
    espesor: float = 1.0


VERTIDAS_EJEMPLO: tuple[VertidaEjemplo, ...] = (
    VertidaEjemplo(
        nombre="Vertida_01",
        vertida_id="V01",
        tipo_hormigon="H30",
        inicio_planificado="2026-11-02T08:00:00",
        temperatura_colocacion_c=18.0,
        moldaje="Metalico",
        aislacion="Poliestireno 50 mm",
        retiro_moldaje_h=48.0,
        origen_x=0.0,
    ),
    VertidaEjemplo(
        nombre="Vertida_02",
        vertida_id="V02",
        tipo_hormigon="H35",
        inicio_planificado="2026-11-02T14:00:00",
        temperatura_colocacion_c=20.0,
        moldaje="Metalico",
        aislacion="Poliestireno 50 mm",
        retiro_moldaje_h=48.0,
        origen_x=4.0,
    ),
    VertidaEjemplo(
        nombre="Vertida_03",
        vertida_id="V03",
        tipo_hormigon="H40",
        inicio_planificado="2026-11-03T08:00:00",
        temperatura_colocacion_c=22.0,
        moldaje="Madera",
        aislacion="Sin aislacion",
        retiro_moldaje_h=72.0,
        origen_x=8.0,
    ),
)


def _unidades_si(modelo: ifcopenshell.file) -> list:
    """Unidades SI del proyecto, incluida temperatura en grados Celsius."""
    return [
        ifcopenshell.api.run(
            "unit.add_si_unit", modelo, unit_type="LENGTHUNIT"
        ),
        ifcopenshell.api.run(
            "unit.add_si_unit", modelo, unit_type="AREAUNIT"
        ),
        ifcopenshell.api.run(
            "unit.add_si_unit", modelo, unit_type="VOLUMEUNIT"
        ),
        modelo.create_entity(
            "IfcSIUnit",
            UnitType="THERMODYNAMICTEMPERATUREUNIT",
            Name="DEGREE_CELSIUS",
            Prefix=None,
        ),
    ]


def construir_modelo(
    vertidas: tuple[VertidaEjemplo, ...] = VERTIDAS_EJEMPLO,
) -> ifcopenshell.file:
    """Construye el modelo IFC4 en memoria."""
    modelo = ifcopenshell.api.run("project.create_file", version="IFC4")

    proyecto = ifcopenshell.api.run(
        "root.create_entity",
        modelo,
        ifc_class="IfcProject",
        name="P02-MCOC Grupo 1 — Fundación de ejemplo E01",
    )
    ifcopenshell.api.run("unit.assign_unit", modelo, units=_unidades_si(modelo))

    contexto_modelo = ifcopenshell.api.run(
        "context.add_context", modelo, context_type="Model"
    )
    contexto_cuerpo = ifcopenshell.api.run(
        "context.add_context",
        modelo,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=contexto_modelo,
    )

    sitio = ifcopenshell.api.run(
        "root.create_entity",
        modelo,
        ifc_class="IfcSite",
        name="Taltal / Zona de Reserva Eólica (referencia docente)",
    )
    edificio = ifcopenshell.api.run(
        "root.create_entity",
        modelo,
        ifc_class="IfcBuilding",
        name="Fundación de hormigón masivo (ejemplo E01)",
    )
    nivel = ifcopenshell.api.run(
        "root.create_entity",
        modelo,
        ifc_class="IfcBuildingStorey",
        name="Nivel de fundación",
    )
    nivel.Elevation = 0.0

    ifcopenshell.api.run(
        "aggregate.assign_object", modelo, relating_object=proyecto, products=[sitio]
    )
    ifcopenshell.api.run(
        "aggregate.assign_object", modelo, relating_object=sitio, products=[edificio]
    )
    ifcopenshell.api.run(
        "aggregate.assign_object", modelo, relating_object=edificio, products=[nivel]
    )

    for vertida in vertidas:
        losa = ifcopenshell.api.run(
            "root.create_entity",
            modelo,
            ifc_class="IfcSlab",
            name=vertida.nombre,
        )
        ifcopenshell.api.run(
            "spatial.assign_container",
            modelo,
            products=[losa],
            relating_structure=nivel,
        )

        matriz = np.eye(4)
        matriz[0, 3] = vertida.origen_x
        ifcopenshell.api.run(
            "geometry.edit_object_placement",
            modelo,
            product=losa,
            matrix=matriz,
        )
        representacion = ifcopenshell.api.run(
            "geometry.add_slab_representation",
            modelo,
            context=contexto_cuerpo,
            depth=vertida.espesor,
            polyline=[
                (0.0, 0.0),
                (vertida.largo, 0.0),
                (vertida.largo, vertida.ancho),
                (0.0, vertida.ancho),
            ],
        )
        ifcopenshell.api.run(
            "geometry.assign_representation",
            modelo,
            product=losa,
            representation=representacion,
        )

        pset = ifcopenshell.api.run(
            "pset.add_pset",
            modelo,
            product=losa,
            name="Pset_HormigonMasivo",
        )
        ifcopenshell.api.run(
            "pset.edit_pset",
            modelo,
            pset=pset,
            properties={
                "VertidaID": vertida.vertida_id,
                "TipoHormigon": vertida.tipo_hormigon,
                "InicioPlanificado": vertida.inicio_planificado,
                "TemperaturaColocacion_C": vertida.temperatura_colocacion_c,
                "Moldaje": vertida.moldaje,
                "Aislacion": vertida.aislacion,
                "RetiroMoldaje_h": vertida.retiro_moldaje_h,
            },
        )

    return modelo


def guardar_modelo(
    ruta: str | Path,
    vertidas: tuple[VertidaEjemplo, ...] = VERTIDAS_EJEMPLO,
) -> Path:
    """Construye y escribe el IFC en ``ruta``. Devuelve la ruta escrita."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    modelo = construir_modelo(vertidas)
    modelo.write(str(ruta))
    return ruta
