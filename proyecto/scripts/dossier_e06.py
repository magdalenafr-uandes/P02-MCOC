"""Genera métricas y figuras E06 desde el motor real, sin modificar el IFC."""
from pathlib import Path
import json
import hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mcplan.thermal import (MallaVoxel, PropiedadesTermicas, SolverVoxel,
                            adiabatico, dirichlet, robin, solucion_pared_robin)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/evidencia_e06'
FIG = ROOT / 'results/figures'
P = PropiedadesTermicas(k=2.22, rho=2400., cp=970.)


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    data = {}
    # Modo propio discreto: lambda_h=4 alpha/dx² sin²(pi/(2n)).
    # Espacio: dt fijo muy pequeño. Tiempo: n fijo y exacta semidiscreta.
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout='constrained')
    for mode, ax in zip(('espacial', 'temporal'), axes):
        rows = []
        for value in ((10, 20, 40) if mode == 'espacial' else (160, 320, 640, 1280)):
            n = value if mode == 'espacial' else 20
            steps = 20000 if mode == 'espacial' else value
            t = 21600.
            dt = t / steps
            m = MallaVoxel.uniforme((n,), (1/n,), P)
            s = SolverVoxel(m, {c: dirichlet(20.) for c in m.caras})
            profile = np.sin(np.pi*m.centros(0))
            r = s.resolver(20+50*profile, dt, steps)
            lam = P.alpha*np.pi**2 if mode == 'espacial' else 4*P.alpha*n*n*np.sin(np.pi/(2*n))**2
            exact = 20+50*profile*np.exp(-lam*t)
            rows.append({'n': n, 'dt_s': dt, 'dx_m': 1/n,
                         'error_C': float(np.max(np.abs(r.T-exact)))})
        key = 'dx_m' if mode == 'espacial' else 'dt_s'
        for prev, cur in zip(rows, rows[1:]):
            cur['orden'] = float(np.log(prev['error_C']/cur['error_C'])/np.log(prev[key]/cur[key]))
        data[mode] = rows
        ax.loglog([r[key] for r in rows], [r['error_C'] for r in rows], 'o-')
        ax.set(xlabel=key, ylabel='Error máximo [°C]', title=f'Convergencia {mode}')
        ax.grid(True, which='both', alpha=.3)
    fig.savefig(FIG/'e06_convergencia.png', dpi=170)
    plt.close(fig)
    m = MallaVoxel.uniforme((8, 8, 8), (.1,)*3, P)
    s = SolverVoxel(m, {c: adiabatico() for c in m.caras})
    initial = 20+40*np.random.default_rng(0).random(m.forma)
    r = s.resolver(initial, s.dt_max()*.9, 500)
    data['energia_rel'] = float(np.max(np.abs(np.asarray(r.energia)-r.energia[0]))/abs(r.energia[0]))
    q = 1000.
    s = SolverVoxel(m, {c: adiabatico() for c in m.caras}, fuente=q)
    r = s.resolver(20., s.dt_max()*.5, 400)
    expected = 20+q*r.tiempos[-1]/(P.rho*P.cp)
    data['fuente_error_C'] = float(np.max(np.abs(r.T-expected)))
    data['fuente_balance_rel'] = float(abs(r.energia[-1]-r.energia[0]-r.calor_fuente_acumulado)/abs(r.calor_fuente_acumulado))
    m = MallaVoxel.uniforme((40, 3), (.025, .1), P)
    b = {c: adiabatico() for c in m.caras}
    b['x-'] = b['x+'] = robin(20., 15.)
    s = SolverVoxel(m, b)
    steps = int(np.ceil(172800/(.9*s.dt_max())))
    r = s.resolver(60., 172800/steps, steps)
    x = m.centros(0)-.5
    exact = solucion_pared_robin(x, 172800., .5, P.alpha, P.k, 15., 60., 20.)
    data['robin_error_C'] = float(np.max(np.abs(r.T[:, 1]-exact)))
    fig, ax = plt.subplots(figsize=(6, 4), layout='constrained')
    ax.plot(x, exact, label='Serie analítica')
    ax.plot(x, r.T[:, 1], '.', label='Volúmenes finitos')
    ax.set(xlabel='x desde centro [m]', ylabel='T [°C]', title='Robin: pared de 1 m, t = 48 h')
    ax.legend(); ax.grid(alpha=.3)
    fig.savefig(FIG/'e06_robin.png', dpi=170)
    plt.close(fig)
    data['ifc_sha256'] = hashlib.sha256((ROOT/'geometry/foundation.ifc').read_bytes()).hexdigest()
    assert all(1.8 < r['orden'] < 2.2 for r in data['espacial'][1:])
    assert all(.95 < r['orden'] < 1.05 for r in data['temporal'][1:])
    assert data['energia_rel'] < 1e-12
    assert data['fuente_error_C'] < 1e-10 and data['fuente_balance_rel'] < 1e-12
    assert data['robin_error_C'] < .05
    (OUT/'metricas.json').write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(data, indent=2))


if __name__ == '__main__':
    run()
