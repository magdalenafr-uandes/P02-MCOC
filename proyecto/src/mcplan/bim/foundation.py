"""Modelo de fundación docente de 5 vertidas (guía Bonsai del capstone).

Sigue la geometría de la guía ``GUIA_BONSAI_FUNDACION.md``:

- octágono regular de 18 m entre caras opuestas;
- espesor de borde 1.10 m, espesor central 3.30 m;
- pedestal superior de 7.0 m de diámetro y 1.0 m de altura;
- cinco ``IfcFooting`` (``Vertida_01`` .. ``Vertida_05``);
- property set custom ``UANDES_HormigonMasivo`` (el prefijo ``Pset_`` está
  reservado para los sets estandarizados de buildingSMART).

La geometría se construye con IfcOpenShell (prismas = extrusión de perfil
poligonal; troncos octagonales = ``IfcFacetedBrep`` de caras planas). El
resultado puede abrirse y editarse en Bonsai vía ``File > Open IFC Project``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import ifcopenshell
import ifcopenshell.api
import numpy as np

from .ifc_io import productos_vertida

RADIO_EXTERIOR = 9.74153  # m, radio al vértice del octágono (18 m entre caras)
RADIO_INTERIOR = 3.78837  # m, radio al vértice del octágono de 7 m entre caras
RADIO_MEDIO = 6.76495  # m, (RADIO_EXTERIOR + RADIO_INTERIOR) / 2
ROTACION_OCTAGONO_GRADOS = 22.5  # alinea caras (no vértices) con los ejes X/Y
PSET_FOUNDATION = "UANDES_HormigonMasivo"


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


@dataclass(frozen=True)
class VertidaFoundation:
    """Una vertida de la fundación: identidad BIM + geometría prismática."""

    nombre: str
    vertida_id: int
    inicio_h: float
    temperatura_colocacion_c: float
    tipo_hormigon: str
    z_base: float
    altura: float
    n_lados: int
    radio_inferior: float
    radio_superior: float | None  # None => prisma de radio constante
    rotacion_grados: float


VERTIDAS_FOUNDATION: tuple[VertidaFoundation, ...] = (
    VertidaFoundation("Vertida_01", 1, 0.0, 18.0, "M1", 0.00, 0.55, 8, RADIO_EXTERIOR, None, ROTACION_OCTAGONO_GRADOS),
    VertidaFoundation("Vertida_02", 2, 6.0, 18.0, "M1", 0.55, 0.55, 8, RADIO_EXTERIOR, None, ROTACION_OCTAGONO_GRADOS),
    VertidaFoundation("Vertida_03", 3, 12.0, 18.0, "M1", 1.10, 1.10, 8, RADIO_EXTERIOR, RADIO_MEDIO, ROTACION_OCTAGONO_GRADOS),
    VertidaFoundation("Vertida_04", 4, 18.0, 18.0, "M1", 2.20, 1.10, 8, RADIO_MEDIO, RADIO_INTERIOR, ROTACION_OCTAGONO_GRADOS),
    VertidaFoundation("Vertida_05", 5, 24.0, 18.0, "M1", 3.30, 1.00, 48, 3.50, 3.50, 0.0),
)
#VertidaFoundation(nombre, id, inicio_h, temperatura, hormigon,z_base, altura, n_lados,radio_inferior, radio_superior, rotacion)

def _area_poligono(n_lados: int, radio: float) -> float:
    return 0.5 * n_lados * radio**2 * math.sin(2.0 * math.pi / n_lados)


def volumen_analitico(vertida: VertidaFoundation) -> float:
    """Volumen exacto del sólido docente (prisma o tronco de pirámide)."""
    a_inf = _area_poligono(vertida.n_lados, vertida.radio_inferior)
    if vertida.radio_superior is None or math.isclose(
        vertida.radio_superior, vertida.radio_inferior
    ):
        return a_inf * vertida.altura
    a_sup = _area_poligono(vertida.n_lados, vertida.radio_superior)
    return vertida.altura / 3.0 * (a_inf + a_sup + math.sqrt(a_inf * a_sup))


def _puntos_anillo(
    vertida: VertidaFoundation, radio: float, z: float
) -> list[tuple[float, float, float]]:
    angulo0 = math.radians(vertida.rotacion_grados)
    paso = 2.0 * math.pi / vertida.n_lados
    return [
        (
            radio * math.cos(angulo0 + paso * i),
            radio * math.sin(angulo0 + paso * i),
            z,
        )
        for i in range(vertida.n_lados)
    ]


def _crear_prisma(
    modelo: ifcopenshell.file, contexto, vertida: VertidaFoundation
):
    puntos2d = [
        modelo.create_entity("IfcCartesianPoint", (x, y))
        for x, y, _ in _puntos_anillo(vertida, vertida.radio_inferior, 0.0)
    ]
    polilinea = modelo.create_entity(
        "IfcPolyline", Points=puntos2d + [puntos2d[0]]
    )
    perfil = modelo.create_entity(
        "IfcArbitraryClosedProfileDef", ProfileType="AREA", OuterCurve=polilinea
    )
    direccion = modelo.create_entity("IfcDirection", (0.0, 0.0, 1.0))
    solido = modelo.create_entity(
        "IfcExtrudedAreaSolid",
        SweptArea=perfil,
        ExtrudedDirection=direccion,
        Depth=vertida.altura,
    )
    representacion = modelo.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=contexto,
        RepresentationIdentifier="Body",
        RepresentationType="SweptSolid",
        Items=[solido],
    )
    return representacion


def _crear_tronco(
    modelo: ifcopenshell.file, contexto, vertida: VertidaFoundation
):
    assert vertida.radio_superior is not None
    inferiores = [
        modelo.create_entity("IfcCartesianPoint", p)
        for p in _puntos_anillo(vertida, vertida.radio_inferior, 0.0)
    ]
    superiores = [
        modelo.create_entity("IfcCartesianPoint", p)
        for p in _puntos_anillo(vertida, vertida.radio_superior, vertida.altura)
    ]

    def cara(puntos: list) -> object:
        lazo = modelo.create_entity("IfcPolyLoop", Polygon=puntos)
        borde = modelo.create_entity(
            "IfcFaceOuterBound", Bound=lazo, Orientation=True
        )
        return modelo.create_entity("IfcFace", Bounds=[borde])

    n = vertida.n_lados
    caras = [
        cara(list(reversed(inferiores))),
        cara(superiores),
    ]
    for i in range(n):
        j = (i + 1) % n
        caras.append(cara([inferiores[i], inferiores[j], superiores[j], superiores[i]]))

    shell = modelo.create_entity("IfcClosedShell", CfsFaces=caras)
    brep = modelo.create_entity("IfcFacetedBrep", Outer=shell)
    representacion = modelo.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=contexto,
        RepresentationIdentifier="Body",
        RepresentationType="Brep",
        Items=[brep],
    )
    return representacion


def construir_foundation(
    vertidas: tuple[VertidaFoundation, ...] = VERTIDAS_FOUNDATION,
) -> ifcopenshell.file:
    """Construye el modelo IFC4 ``foundation`` en memoria."""
    modelo = ifcopenshell.api.run("project.create_file", version="IFC4")

    proyecto = ifcopenshell.api.run(
        "root.create_entity",
        modelo,
        ifc_class="IfcProject",
        name="P02-MCOC Grupo 1 — Fundación del capstone (guía Bonsai)",
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
        name="Sitio eólico (referencia docente)",
    )
    edificio = ifcopenshell.api.run(
        "root.create_entity",
        modelo,
        ifc_class="IfcBuilding",
        name="Fundación de hormigón masivo",
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
        pieza = ifcopenshell.api.run(
            "root.create_entity",
            modelo,
            ifc_class="IfcFooting",
            name=vertida.nombre,
        )
        ifcopenshell.api.run(
            "spatial.assign_container",
            modelo,
            products=[pieza],
            relating_structure=nivel,
        )

        matriz = np.eye(4)
        matriz[2, 3] = vertida.z_base
        ifcopenshell.api.run(
            "geometry.edit_object_placement",
            modelo,
            product=pieza,
            matrix=matriz,
        )

        if vertida.radio_superior is None or math.isclose(
            vertida.radio_superior, vertida.radio_inferior
        ):
            representacion = _crear_prisma(modelo, contexto_cuerpo, vertida)
        else:
            representacion = _crear_tronco(modelo, contexto_cuerpo, vertida)
        ifcopenshell.api.run(
            "geometry.assign_representation",
            modelo,
            product=pieza,
            representation=representacion,
        )

        ifcopenshell.api.run(
            "pset.add_pset",
            modelo,
            product=pieza,
            name=PSET_FOUNDATION,
        )
        pset = next(
            p for p in pieza.IsDefinedBy
            if p.is_a("IfcRelDefinesByProperties")
            and p.RelatingPropertyDefinition.Name == PSET_FOUNDATION
        ).RelatingPropertyDefinition
        ifcopenshell.api.run(
            "pset.edit_pset",
            modelo,
            pset=pset,
            properties={
                "VertidaID": vertida.vertida_id,
                "Inicio_h": vertida.inicio_h,
                "TemperaturaColocacion_C": vertida.temperatura_colocacion_c,
                "TipoHormigon": vertida.tipo_hormigon,
                "Moldaje": "TBD",
                "Aislacion": "TBD",
                "RetiroMoldaje_h": 72.0,
            },
        )

    return modelo


def guardar_foundation(
    ruta: str | Path,
    vertidas: tuple[VertidaFoundation, ...] = VERTIDAS_FOUNDATION,
) -> Path:
    """Construye y escribe ``foundation.ifc`` en ``ruta``. Devuelve la ruta."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    modelo = construir_foundation(vertidas)
    modelo.write(str(ruta))
    return ruta


@dataclass(frozen=True)
class GeometriaVertida:
    """BBox y volumen de malla de una vertida (coordenadas de mundo)."""

    nombre: str
    volumen_m3: float
    bbox_min: tuple[float, float, float]
    bbox_max: tuple[float, float, float]


def resumen_geometrico(ruta: str | Path) -> tuple[GeometriaVertida, ...]:
    """Triangula cada vertida del IFC (selección por pset) y reporta bbox y volumen."""
    import ifcopenshell.geom

    modelo = ifcopenshell.open(str(ruta))
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)

    resumen: list[GeometriaVertida] = []
    productos = productos_vertida(modelo)
    for producto in productos:
        forma = ifcopenshell.geom.create_shape(settings, producto)
        verts = np.asarray(forma.geometry.verts, dtype=float).reshape(-1, 3)
        caras = np.asarray(forma.geometry.faces, dtype=np.int64).reshape(-1, 3)
        v0, v1, v2 = verts[caras[:, 0]], verts[caras[:, 1]], verts[caras[:, 2]]
        volumen = float(
            abs(np.einsum("ij,ij->i", v0, np.cross(v1, v2)).sum()) / 6.0
        )
        resumen.append(
            GeometriaVertida(
                nombre=producto.Name,
                volumen_m3=volumen,
                bbox_min=tuple(np.round(verts.min(axis=0), 4)),
                bbox_max=tuple(np.round(verts.max(axis=0), 4)),
            )
        )
    return tuple(resumen)
