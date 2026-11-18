"""Una carga partida entre sólidos conserva volumen, soporte y energía."""

from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from colocacion_progresiva import SimuladorPorTandas, dividir_grilla
from mcplan.bim.voxelizador import DefinicionGrilla, GrillaBIM
from mcplan.thermal.bordes import Ambiente, CondicionBase
from mcplan.thermal.etapas import Hormigon, Material, ParametrosTiempo, PlanVertida


def test_carga_pasa_al_siguiente_solido_sin_reiniciar_cadencia():
    ids = np.broadcast_to([1, 2], (4, 3, 2)).copy()
    grilla = GrillaBIM(DefinicionGrilla((0, 0, 0), (1, 1, 1), ids.shape), ids, np.zeros_like(ids, dtype=bool))
    plan = [PlanVertida(1, 0, 12, "M1", retiro_moldaje_s=72*3600),
            PlanVertida(2, 1080, 12, "M1", retiro_moldaje_s=72*3600)]
    filas = [{"vertida": 1, "volumen_m3": 12}, {"vertida": 2, "volumen_m3": 12}]
    lotes, asignaciones, porciones = dividir_grilla(grilla, plan, filas, 40)

    assert np.all(lotes[:, :, 0] < lotes[:, :, 1])
    assert [p["carga"] for p in porciones] == [1, 2, 2, 3]
    assert [p["volumen_m3"] for p in porciones] == [8, 4, 4, 8]
    assert [p["voxeles"] for p in porciones] == [8, 4, 4, 8]
    assert [p.inicio_s for p in asignaciones] == pytest.approx([0, 720, 1080, 1440])
    assert porciones[-1]["fin_s"] == pytest.approx(2160)
    assert [p.inicio_s+p.retiro_moldaje_s for p in asignaciones] == pytest.approx([259200]*2 + [260280]*2)

    material = Material(2.22, 2400, 970)
    config = SimpleNamespace(malla=SimpleNamespace(corregir_area=False),
                             criterios=SimpleNamespace(profundidad_superficie_m=.025),
                             hormigones={"M1": Hormigon(material)}, ambiente=Ambiente(12, 0),
                             base=CondicionBase("adiabatico"), tiempo=ParametrosTiempo(2160, guardar_cada_s=360),
                             suelo=None, T_suelo_inicial_C=None)
    resultado = SimuladorPorTandas(SimpleNamespace(config=config, grilla=grilla, plan=plan),
                                  lotes, asignaciones, None).ejecutar()

    assert np.all(resultado.activo_final)
    assert set(resultado.T_max_vertida_C) == {1, 2}
    assert np.isnan(resultado.T_max_vertida_C[2][0])
    assert np.isfinite(resultado.T_max_vertida_C[2][resultado.tiempos_s.index(1080)])
    assert resultado.balance["colocacion_J"] == pytest.approx(24*material.rho*material.cp*12)
    assert resultado.balance["residuo_J"] == pytest.approx(0, abs=1e-5)
