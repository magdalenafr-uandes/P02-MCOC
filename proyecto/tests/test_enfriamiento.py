"""Intercambio por tramo, activación con la vertida y balance del estanque."""

from pathlib import Path

import numpy as np
import pytest

from mcplan.pipeline import Pipeline, cargar_plan, configurar_caso
from mcplan.thermal.bordes import Ambiente, CondicionBase
from mcplan.thermal.enfriamiento import AguaRecirculada, Enfriamiento, trazar_circuitos
from mcplan.thermal.etapas import DominioVoxel, Hormigon, Material, ParametrosTiempo, PlanVertida, SimuladorEtapas


def test_circuito_calienta_el_agua_en_serie_y_no_cruza_huecos():
    ids = np.array([1, 1, 0, 1]).reshape((4, 1, 1))
    circuitos = trazar_circuitos(ids, (1, 1, 1), [1], 1.5)[1]
    assert [c.tolist() for c in circuitos] == [[0, 1], [3]]
    agua = AguaRecirculada(Enfriamiento(T_agua_C=15, volumen_estanque_m3=None), 1)
    T = np.array([40., 40., 60., 40.]).reshape(ids.shape)
    fuente = np.zeros_like(T)
    energia = agua.intercambiar(T, fuente, circuitos, dt_s=60, volumen_voxel=1)
    p0 = agua.G_tramo_W_K * 25
    p1 = agua.G_tramo_W_K * (25 - p0 / agua.capacidad_flujo_W_K)
    assert -fuente.ravel() == pytest.approx([p0, p1, 0, p0])
    assert energia == pytest.approx(60 * (2 * p0 + p1))
    assert agua.temperatura_C == 15


def test_enfriamiento_activa_con_colocacion_y_cierra_ambos_balances():
    ids = np.ones((3, 1, 1), dtype=int)
    dominio = DominioVoxel(ids, np.zeros_like(ids, dtype=bool), 0.5)
    material = Material(2, 2400, 1000)
    colocacion = 3600
    tiempo = ParametrosTiempo(7200, guardar_cada_s=colocacion, dt_max_s=1800)
    enfriamiento = Enfriamiento(T_agua_C=15, UA_lineal_W_mK=200, volumen_estanque_m3=0.05)

    def correr(agua=None):
        return SimuladorEtapas(
            dominio, [PlanVertida(1, colocacion, 40, 'M')], {'M': Hormigon(material)},
            Ambiente(30, 0), CondicionBase('adiabatico'), tiempo,
            guardar_campos=True, enfriamiento=agua,
        ).ejecutar()

    base, enfriada = correr(), correr(enfriamiento)
    assert base.enfriamiento is None
    assert base.balance['agua_J'] == 0
    assert np.array_equal(enfriada.campos[0], base.campos[0])
    assert np.array_equal(enfriada.campos[colocacion], base.campos[colocacion])
    assert enfriada.T_final.max() < base.T_final.max()
    assert enfriada.etapas[1]['dt_limite_s'] < base.etapas[1]['dt_limite_s']
    energia = enfriada.balance['agua_J']
    assert energia > 0
    assert energia == pytest.approx(base.balance['E_final_J'] - enfriada.balance['E_final_J'])
    assert enfriada.balance['residuo_J'] == pytest.approx(0, abs=1e-6)
    agua = AguaRecirculada(enfriamiento, dominio.pasos[0])
    final = enfriada.enfriamiento['T_agua_final_C']
    assert final == pytest.approx(15 + energia / agua.capacidad_estanque_J_K)
    assert 15 < final < 40


def test_visor_cambia_de_modelo_y_conserva_el_trazado_yaml(tmp_path):
    proyecto = Path(__file__).resolve().parents[1]
    plan = cargar_plan(proyecto / "configs/e08_demo.yaml")
    plan.update(paso_z_m=.275, final_h=.02, guardar_cada_h=.01, dt_s=20.)
    plan["caso"]["suelo"]["espesor_m"] = .55
    circuitos = plan["caso"]["tuberias"]
    plan["enfriamiento"]["activo"] = True
    with pytest.raises(ValueError, match="Elegir un solo modelo"):
        configurar_caso(plan)

    plan["tuberias_ctrl"]["activas"] = False
    resultado = Pipeline().ejecutar(plan, tmp_path, convergencia=False)
    assert resultado["enfriamiento"]["circuitos"] > 0
    assert resultado["balances"][-1]["agua_J"] > 0
    assert resultado["balances"][-1]["tuberias_J"] == 0
    assert resultado["caso_ejecutado"]["tuberias"] == []

    guardado = resultado["plan"]
    assert guardado["caso"]["tuberias"] == circuitos
    guardado["tuberias_ctrl"]["activas"] = True
    guardado["enfriamiento"]["activo"] = False
    config = configurar_caso(guardado)
    assert len(config.tuberias) == len(circuitos)
    assert config.enfriamiento is None
