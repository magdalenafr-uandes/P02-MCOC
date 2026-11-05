# [LEGADO] LEGADO E07 inicial: lee configs/hormigon_M1.json. El material del caso base está en configs/e07_caso_base.yaml (hormigones).
# Ver proyecto/MAPA_DEL_CODIGO.md. No editar aquí para cambiar el caso.
"""Carga trazable de propiedades e hidratación de un material homogéneo."""
import json
from pathlib import Path
from .boundaries import PropiedadesTermicas
from .hidratacion import HidratacionAdiabatica


def cargar_hormigon(ruta: str | Path):
    ruta = Path(ruta)
    datos = json.loads(ruta.read_text(encoding='utf-8-sig'))
    if not isinstance(datos.get('material'), str) or not datos['material'].strip() or not datos.get('estado') or not datos.get('fuentes'):
        raise ValueError('El material requiere nombre, estado y fuentes trazables.')
    p = datos['propiedades']
    propiedades = PropiedadesTermicas(p['k_W_m_K'], p['rho_kg_m3'], p['cp_J_kg_K'])
    h = datos['hidratacion']
    hidratacion = HidratacionAdiabatica(h['incremento_K'], h['escala_s'])
    return propiedades, hidratacion, datos
