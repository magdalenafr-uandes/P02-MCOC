"""Los controles nuevos deben llegar al plan IFC y mantenerse tras desmoldar."""
import importlib.util
from pathlib import Path
import sys

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
spec = importlib.util.spec_from_file_location("extension_defensa", RAIZ / "scripts/explorar_defensa.py")
extension = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extension)

from mcplan.caso.config import leer_config, resolver_plan


def test_prefrio_y_aislacion_se_aplican_sin_modificar_el_material_ni_el_ifc():
    base = extension.cargar_yaml(RAIZ / "configs/e07_caso_base.yaml")
    estudio = extension.cargar_yaml(RAIZ / "configs/defensa.yaml")
    control = dict(espesor_m=.2, T_colocacion_C=12, activacion="conjunta")
    caso = extension.preparar_extension(base, estudio, control, estudio["climas"]["era5_2024"],
                                        "M1_SS", estudio["niveles"]["barrido"],
                                        [dict(vertida=1, activacion_h=0)])
    config = leer_config(caso, RAIZ / "configs")
    plan, = resolver_plan(config, [(1, "piloto", {"Inicio_h": 24, "TemperaturaColocacion_C": 18,
                                                  "TipoHormigon": "M1"})])
    assert plan.T_colocacion_C == 12 and plan.inicio_s == 0
    assert plan.resistencia(0, "lateral") == pytest.approx(.2 / .035 + .018 / .15)
    assert plan.resistencia(100 * 3600, "lateral") == pytest.approx(.2 / .035)
    assert plan.resistencia(100 * 3600, "superior") == pytest.approx(.2 / .035)
    assert plan.resistencia(100 * 3600, "inferior") == 0  # no se aísla artificialmente el suelo
    assert caso["hormigones"]["M1"]["hidratacion"]["curva"] == "M1_SS"
    assert caso["hormigones"]["M1"]["k_W_mK"] == base["hormigones"]["M1"]["k_W_mK"]
    assert "eps_extension" not in base["protecciones"]
