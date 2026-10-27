"""Voxeliza la fundación de 5 vertidas y estudia el error de volumen (G04).

Para cada resolución reporta, por vertida, V_h = N_activo·Δx³, el volumen
analítico del sólido y e_V = |V_h - V| / V. Guarda
``results/figures/e04_voxelizacion_foundation.png`` (planta y corte por
vertida_id).

Uso:
    python scripts/voxelize_foundation.py
    python scripts/voxelize_foundation.py --pasos 0.4 0.2 0.1
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from mcplan.bim.foundation import VERTIDAS_FOUNDATION, volumen_analitico
from mcplan.bim.voxelizacion import voxelizar

RAIZ = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pasos", type=float, nargs="+", default=[0.4, 0.2, 0.1])
    args = parser.parse_args()

    v_geom = {v.vertida_id: volumen_analitico(v) for v in VERTIDAS_FOUNDATION}
    print(f"{'Δx [m]':>7} {'voxeles':>10} " + " ".join(f"{'e_V V'+str(i):>9}" for i in v_geom) + f" {'e_V total':>10}")
    grilla = None
    for paso in sorted(args.pasos, reverse=True):
        grilla = voxelizar(VERTIDAS_FOUNDATION, paso)
        errores = [abs(grilla.volumen(i) - v) / v for i, v in v_geom.items()]
        v_h = sum(grilla.volumen(i) for i in v_geom)
        e_tot = abs(v_h - sum(v_geom.values())) / sum(v_geom.values())
        activos = int(np.count_nonzero(grilla.vertida_id))
        print(f"{paso:7.3f} {activos:10d} " + " ".join(f"{100*e:8.2f}%" for e in errores) + f" {100*e_tot:9.2f}%")
    print("Volúmenes analíticos [m³]: " + ", ".join(f"V{i}={v:.1f}" for i, v in v_geom.items()))

    assert grilla is not None
    ids = np.ma.masked_equal(grilla.vertida_id, 0)
    x, z = grilla.centros(0), grilla.centros(2)
    j = ids.shape[1] // 2
    fig, ejes = plt.subplots(1, 2, figsize=(13, 5))
    k = np.searchsorted(z, 0.3)
    m = ejes[0].pcolormesh(x, x, ids[:, :, k].T, cmap="tab10", vmin=0.5, vmax=10.5, shading="auto")
    ejes[0].set_aspect("equal")
    ejes[0].set_title(f"Planta z = {z[k]:.2f} m (Vertida 1)")
    ejes[0].set_xlabel("x [m]")
    ejes[0].set_ylabel("y [m]")
    ejes[1].pcolormesh(x, z, ids[:, j, :].T, cmap="tab10", vmin=0.5, vmax=10.5, shading="auto")
    ejes[1].set_aspect("equal")
    ejes[1].set_title("Corte y = 0 coloreado por vertida_id")
    ejes[1].set_xlabel("x [m]")
    ejes[1].set_ylabel("z [m]")
    fig.colorbar(m, ax=ejes, ticks=range(1, 6), label="vertida_id")
    fig.suptitle(f"Fundación de 5 vertidas voxelizada, Δx = {grilla.paso} m")
    salida = RAIZ / "results" / "figures" / "e04_voxelizacion_foundation.png"
    salida.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(salida, dpi=150)
    plt.close(fig)
    print(f"Figura: {salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
