"""Servidor local del visor: python visor/servidor.py. Sin dependencias web."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'proyecto' / 'src'))
from mcplan.thermal import PropiedadesTermicas


def avanzar(data):
    """Balance explícito en máscara irregular; bordes en caras escalonadas.

    Adaptador del visor, separado del SolverVoxel cartesiano sin máscara.
    No incluye activación temporal, suelo ni hidratación.
    """
    n, nz = int(data['n']), int(data['nz'])
    if not 2 <= n <= 30 or not 1 <= nz <= 8:
        raise ValueError('Resolución fuera del rango admitido.')
    shape = (nz, n, n)
    T = np.asarray(data['temperature'], dtype=float).reshape(shape)
    mask = np.asarray(data['mask'], dtype=bool).reshape(shape)
    if not np.all(np.isfinite(T)) or not mask.any():
        raise ValueError('Temperaturas o máscara inválidas.')
    props = PropiedadesTermicas(2.22, 2400., 970.)
    ambient, h, flux, source = (float(data[k]) for k in ('ambient', 'h', 'flux', 'source'))
    if not np.all(np.isfinite([ambient, h, flux, source])) or h < 0:
        raise ValueError('Parámetros no válidos.')
    mode = data['mode']
    if mode not in ('robin', 'neumann', 'dirichlet'):
        raise ValueError('Borde desconocido.')
    spacing = (4.3/nz, 18/n, 18/n)
    volume = float(np.prod(spacing))
    C = props.rho * props.cp * volume
    links, borders = [], []
    sumG = np.zeros(shape)
    for axis, d in enumerate(spacing):
        area = volume/d
        G = props.k*area/d
        for side in (-1, 1):
            neighbor = np.roll(mask, -side, axis=axis)
            edge = [slice(None)]*3
            edge[axis] = -1 if side == 1 else 0
            neighbor[tuple(edge)] = False
            internal = mask & neighbor
            exterior = mask & ~neighbor
            gb = 2*G if mode == 'dirichlet' else area/(d/(2*props.k)+1/h) if mode == 'robin' and h > 0 else 0.
            sumG += internal*G + exterior*gb
            links.append((axis, side, internal, G))
            borders.append((exterior, gb, flux*area))
    dt = .8*float(np.min(C/sumG[mask]))
    for _ in range(3):
        power = source*volume*mask.astype(float)
        for axis, side, internal, G in links:
            power += internal*G*(np.roll(T, -side, axis=axis)-T)
        for exterior, gb, q in borders:
            power += exterior*(q if mode == 'neumann' else gb*(ambient-T))
        T = T + dt*power/C
    return {'temperature': T.ravel().tolist(), 'seconds': 3*dt}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_POST(self):
        if self.path != '/api/step':
            self.send_error(404)
            return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size < 2_000_000:
                raise ValueError('Solicitud demasiado grande.')
            result = avanzar(json.loads(self.rfile.read(size)))
            payload = json.dumps(result, allow_nan=False).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(payload)
        except (ValueError, KeyError, TypeError) as exc:
            self.send_error(400, str(exc))


if __name__ == '__main__':
    print('Visor conectado a Python: http://127.0.0.1:8765', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
