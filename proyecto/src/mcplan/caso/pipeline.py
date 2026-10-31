"""Pipeline BIM -> grilla -> simulación por etapas (E07/E08).

    config (YAML)  ─┐
                    ├─> resolver_plan ─> PlanVertida[]
    IFC ─> extraer_vertidas ─> SolidoVertida[]  ─┘
                    └─> definir_grilla + voxelizar_solidos ─> GrillaBIM
                                                   └─> SimuladorEtapas ─> ResultadoEtapas

Cada etapa es una función pura de sus entradas; este módulo solo las encadena.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..bim.mallas_ifc import SolidoVertida, extraer_vertidas
from ..bim.voxelizador import (
    GrillaBIM,
    area_expuesta,
    caras_expuestas,
    definir_grilla,
    pesos_area,
    resumen_volumetrico,
    voxelizar_solidos,
)
from ..thermal.etapas import DominioVoxel, PlanVertida, ResultadoEtapas, SimuladorEtapas
from .config import ConfigCaso, resolver_plan


@dataclass
class ResultadoPipeline:
    config: ConfigCaso
    solidos: list[SolidoVertida]
    plan: list[PlanVertida]
    grilla: GrillaBIM
    volumetria: list[dict[str, float]]
    area_exterior_m2: dict[str, float]  # staircase
    area_exterior_corregida_m2: dict[str, float]  # con w = 1/||n||₁
    simulacion: ResultadoEtapas | None = None


def construir_grilla(config: ConfigCaso, solidos: list[SolidoVertida]) -> GrillaBIM:
    m = config.malla
    definicion = definir_grilla(solidos, m.pasos, m.margen_lateral_m, m.margen_superior_m, m.espesor_suelo_m)
    return voxelizar_solidos(solidos, definicion)


def ejecutar_pipeline(config: ConfigCaso, simular: bool = True) -> ResultadoPipeline:
    solidos = extraer_vertidas(config.ruta_ifc)
    plan = resolver_plan(config, [(s.vertida_id, s.nombre, s.propiedades) for s in solidos])
    visibles = {p.vertida_id for p in plan if p.visible}
    if not visibles:
        raise ValueError("Ninguna vertida visible: revisar 'visible' en la configuración.")
    solidos = [s for s in solidos if s.vertida_id in visibles]
    grilla = construir_grilla(config, solidos)
    if grilla.voxeles_solapados:
        raise ValueError(f"{grilla.voxeles_solapados} voxeles caen en dos vertidas: revisar el IFC.")

    hormigon = grilla.vertida_id > 0
    expuestas = caras_expuestas(hormigon | grilla.es_suelo)
    pesos = pesos_area(solidos, grilla)
    resultado = ResultadoPipeline(
        config, solidos, plan, grilla, resumen_volumetrico(solidos, grilla),
        area_expuesta(expuestas, grilla.paso, mascara=hormigon),
        area_expuesta(expuestas, grilla.paso, mascara=hormigon, pesos=pesos),
    )
    if simular:
        resultado.simulacion = SimuladorEtapas(
            DominioVoxel(
                grilla.vertida_id, grilla.es_suelo, grilla.paso,
                pesos if config.malla.corregir_area else None,
            ),
            [p for p in plan if p.visible],
            config.hormigones,
            config.ambiente,
            config.base,
            config.tiempo,
            config.suelo,
            config.T_suelo_inicial_C,
            config.guardar_campos,
        ).ejecutar()
    return resultado
