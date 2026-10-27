"""Voxelización de la fundación: error de volumen y vertida_id (G04)."""

from __future__ import annotations

import numpy as np

from mcplan.bim.foundation import VERTIDAS_FOUNDATION, volumen_analitico
from mcplan.bim.voxelizacion import voxelizar


def test_error_de_volumen_disminuye_al_refinar():
    v_total = sum(volumen_analitico(v) for v in VERTIDAS_FOUNDATION)
    errores = []
    for paso in (0.4, 0.2, 0.1):
        g = voxelizar(VERTIDAS_FOUNDATION, paso)
        v_h = sum(g.volumen(v.vertida_id) for v in VERTIDAS_FOUNDATION)
        errores.append(abs(v_h - v_total) / v_total)
    assert errores[-1] < 0.02
    assert errores[-1] < errores[0]


def test_cada_vertida_tiene_su_id_y_estan_apiladas():
    g = voxelizar(VERTIDAS_FOUNDATION, 0.2)
    ids = set(np.unique(g.vertida_id).tolist())
    assert ids == {0, 1, 2, 3, 4, 5}
    z = g.centros(2)
    centro = g.vertida_id.shape[0] // 2
    columna = g.vertida_id[centro, centro, :]
    # en el eje de la fundación las vertidas aparecen en orden 1..5 hacia arriba
    orden = [int(i) for i in columna[columna > 0]]
    assert orden == sorted(orden)
    assert z[np.nonzero(columna == 5)[0][0]] >= 3.3
