"""Fuente de calor medida Q(t) del profesor -> curva adiabática θ(t) (MAPA:fuente-medida)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from mcplan.caso.config import ErrorConfiguracion, aplicar_sobrescrituras, leer_config
from mcplan.caso.fuente_calor import MEDIA, elevacion_adiabatica, leer_fuente
from mcplan.thermal.hidratacion import HORA

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "data" / "hidratacion"
ARCHIVO = DATOS / "source_terms.txt"
CONFIG = RAIZ / "configs" / "e07_caso_base.yaml"
RHO_CP = 2400.0 * 970.0
PROBETAS = ("M1_SS", "M2_SS", "M3_SS", "M4_SS", "M1_22A", "M2_22A", "M3_22A", "M4_22A")


def test_archivo_original_trazable():
    meta = json.loads((DATOS / "metadata.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(ARCHIVO.read_bytes()).hexdigest() == meta["sha256"]
    serie = leer_fuente(ARCHIVO)
    assert serie.sha256 == meta["sha256"]
    assert serie.nombres == PROBETAS
    assert serie.t_h[0] == 0.0 and serie.t_h[1] == pytest.approx(1 / 60, rel=1e-3)
    # la campaña 22A termina antes (NaN): se toma Q = 0 después del registro
    assert np.isnan(serie.Q["M1_22A"][-1]) and serie.curva("M1_22A")[-1] == 0.0


def test_integral_conserva_la_energia_medida():
    serie = leer_fuente(ARCHIVO)
    for nombre in (MEDIA, "M3_SS", "M4_22A"):
        Q = serie.curva(nombre)
        t, th = elevacion_adiabatica(serie.t_h, Q, RHO_CP)
        energia = np.trapezoid(Q, serie.t_h * HORA) if hasattr(np, "trapezoid") else np.trapz(Q, serie.t_h * HORA)
        assert th[0] == 0.0 and t[0] == 0.0
        assert np.all(np.diff(th) >= 0.0)
        assert th[-1] * RHO_CP == pytest.approx(energia, rel=1e-9)


def test_media_entre_la_menor_y_la_mayor_probeta():
    serie = leer_fuente(ARCHIVO)
    finales = {n: elevacion_adiabatica(serie.t_h, serie.curva(n), RHO_CP)[1][-1] for n in (MEDIA, *PROBETAS)}
    assert min(finales[p] for p in PROBETAS) < finales[MEDIA] < max(finales[p] for p in PROBETAS)
    assert finales[MEDIA] == pytest.approx(np.mean([finales[p] for p in PROBETAS]), rel=1e-9)


def test_caso_base_usa_la_fuente_medida_y_entrega_el_calor_del_archivo():
    config = leer_config(CONFIG)
    h = config.hormigones["M1"].hidratacion
    assert h.modelo == "tabla"
    serie = leer_fuente(ARCHIVO)
    _, th = elevacion_adiabatica(serie.t_h, serie.curva(MEDIA), h.rho * h.cp)
    assert h.theta_inf_C == pytest.approx(th[-1])
    # a T_ref la potencia del solver reproduce la Q medida (promedio de cada intervalo de la tabla)
    t_med = 30.0 * HORA
    q_solver = float(h.potencia(t_med, h.T_ref_C))
    q_archivo = float(np.mean(np.interp(np.linspace(30.0, 30.25, 16), serie.t_h, serie.curva(MEDIA))))
    assert q_solver == pytest.approx(q_archivo, rel=1e-3)


def test_cambiar_probeta_por_input_y_errores_claros():
    base = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    alta = leer_config(aplicar_sobrescrituras(base, ["hormigones.M1.hidratacion.curva=M3_SS"]), CONFIG.parent)
    baja = leer_config(aplicar_sobrescrituras(base, ["hormigones.M1.hidratacion.curva=M4_22A"]), CONFIG.parent)
    assert alta.hormigones["M1"].hidratacion.theta_inf_C > baja.hormigones["M1"].hidratacion.theta_inf_C
    with pytest.raises(ErrorConfiguracion, match="inexistente"):
        leer_config(aplicar_sobrescrituras(base, ["hormigones.M1.hidratacion.curva=M9"]), CONFIG.parent)
    with pytest.raises(ErrorConfiguracion, match="sobra 'theta_inf_C'"):
        leer_config(aplicar_sobrescrituras(base, ["hormigones.M1.hidratacion.theta_inf_C=45"]), CONFIG.parent)
