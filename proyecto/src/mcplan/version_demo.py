"""Identidad del código/configuración del servidor para reiniciar al actualizar."""
import hashlib
from pathlib import Path


def version_visualizador():
    raiz=Path(__file__).resolve().parents[2]
    archivos=list((raiz/'src/mcplan').rglob('*.py'))+list((raiz/'scripts').glob('*.py'))
    archivos+=list((raiz/'configs').glob('*'))+list((raiz/'visor_e08').glob('*.html'))+list((raiz/'visor_e08').glob('*.js'))
    h=hashlib.sha256()
    for p in sorted(archivos):
        if p.is_file():
            h.update(str(p.relative_to(raiz)).encode('utf-8'))
            h.update(p.read_bytes())
    return h.hexdigest()
