"""E11: el pronóstico real alimenta el borde sin respaldo ni extrapolación."""
import importlib.util
from pathlib import Path

import numpy as np


def _demo():
    ruta = Path(__file__).resolve().parents[1] / "scripts/demo_e11.py"
    spec = importlib.util.spec_from_file_location("demo_e11", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_pronostico_real_alimenta_bc():
    from mcplan.caso.clima import leer_snapshot
    mod = _demo()
    c = mod.configurar()
    s = leer_snapshot(mod.RAIZ / "data/weather/2026-11-07T2001_pronostico")
    assert s.tiempos[0] <= c.inicio
    for h in (0, 6, 24, 48):
        t = c.inicio.timestamp() + h * 3600
        idx = next(i for i, d in enumerate(s.tiempos) if d.timestamp() == t)
        assert c.ambiente.temperatura(h * 3600) == s.T_C[idx]
    assert c.tiempo.duracion_s == 48 * 3600
    assert "COLA" not in c.nota_clima
    assert c.ambiente.h_conveccion(0) > 0
    assert np.isfinite(c.ambiente.condiciones(0)[1]["superior"])
