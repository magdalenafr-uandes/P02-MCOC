# [LEGADO] LEGADO E07 inicial: voxelizador por contención de puntos. El caso base usa bim/voxelizador.py + bim/mallas_ifc.py.
# Ver proyecto/MAPA_DEL_CODIGO.md. No editar aquí para cambiar el caso.
"""IFC -> grilla en metros, usando centros y ángulo sólido de malla cerrada."""
from dataclasses import dataclass
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
import numpy as np

from .ifc_io import PSET_HORMIGON, productos_vertida
from .voxelizacion import GrillaVertidas


@dataclass(frozen=True)
class SolidoIFC:
    vertida_id: int
    guid: str
    vertices: np.ndarray
    triangulos: np.ndarray
    inicio_s: float
    temperatura_C: float
    tipo_hormigon: str = 'M1'

    @property
    def volumen(self) -> float:
        # Trasladar al origen evita cancelación con coordenadas georreferenciadas.
        a, b, c = (self.vertices - self.vertices.mean(axis=0))[self.triangulos].transpose(1, 0, 2)
        return float(abs(np.einsum('ij,ij->i', a, np.cross(b, c)).sum()) / 6)


def extraer_solidos(ruta: str | Path) -> list[SolidoIFC]:
    modelo = ifcopenshell.open(str(ruta))
    ajustes = ifcopenshell.geom.settings()
    ajustes.set('use-world-coords', True)
    # IfcOpenShell entrega geometría SI por defecto; no convertir otra vez.
    salida = []
    ids = set()
    for producto in productos_vertida(modelo):
        p = ifcopenshell.util.element.get_psets(producto)[PSET_HORMIGON]
        vid = int(p['VertidaID'])
        if vid <= 0 or vid in ids or float(p['VertidaID']) != vid:
            raise ValueError('VertidaID debe ser entero positivo y único.')
        ids.add(vid)
        shape = ifcopenshell.geom.create_shape(ajustes, producto)
        vertices = np.array(shape.geometry.verts).reshape(-1, 3)
        caras = np.array(shape.geometry.faces, dtype=int).reshape(-1, 3)
        if not vertices.size or not caras.size or not np.isfinite(vertices).all():
            raise ValueError(f'Geometría vacía o inválida: {vid}.')
        aristas = np.concatenate([caras[:, [0, 1]], caras[:, [1, 2]], caras[:, [2, 0]]])
        _, conteos = np.unique(np.sort(aristas, axis=1), axis=0, return_counts=True)
        if np.any(conteos != 2):
            raise ValueError(f'La malla de vertida {vid} no es cerrada/manifold.')
        _, inversos = np.unique(np.sort(aristas, axis=1), axis=0, return_inverse=True)
        orientacion = np.bincount(inversos, weights=np.where(aristas[:, 0] < aristas[:, 1], 1, -1))
        if np.any(orientacion != 0):
            raise ValueError(f'Triángulos con orientación inconsistente: {vid}.')
        inicio, temperatura = float(p['Inicio_h']) * 3600, float(p['TemperaturaColocacion_C'])
        if not np.isfinite([inicio, temperatura]).all() or inicio < 0:
            raise ValueError('Inicio o temperatura de colocación inválidos.')
        material = p.get('TipoHormigon')
        if not isinstance(material, str) or not material.strip():
            raise ValueError(f'TipoHormigon ausente o inválido: {vid}.')
        solido = SolidoIFC(vid, producto.GlobalId, vertices, caras, inicio, temperatura, material)
        if solido.volumen <= 0:
            raise ValueError(f'Volumen nulo en vertida {vid}.')
        salida.append(solido)
    if not salida:
        raise ValueError('El IFC no contiene vertidas.')
    return salida


def contiene(solido: SolidoIFC, puntos: np.ndarray, incluir_frontera: bool = True) -> np.ndarray:
    """Número de vueltas por suma de ángulos sólidos; incluye la frontera.

    Requiere triángulos orientados consistentemente. Se procesa por bloques
    para limitar memoria. La tolerancia superficial es relativa al tamaño.
    """
    tri = solido.vertices[solido.triangulos]
    tolerancia = max(np.ptp(solido.vertices, axis=0).max(), 1.) * 1e-10
    normal = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    norma = np.linalg.norm(normal, axis=1)
    if np.any(norma == 0):
        raise ValueError('Triángulo degenerado.')
    resultado = np.zeros(len(puntos), dtype=bool)
    for inicio in range(0, len(puntos), 512):
        p = puntos[inicio:inicio + 512]
        a, b, c = (tri[None] - p[:, None, None]).transpose(2, 0, 1, 3)
        la, lb, lc = (np.linalg.norm(v, axis=-1) for v in (a, b, c))
        det = np.einsum('...i,...i->...', a, np.cross(b, c))
        den = la*lb*lc + np.sum(a*b, axis=-1)*lc + np.sum(b*c, axis=-1)*la + np.sum(c*a, axis=-1)*lb
        dentro = abs((2*np.arctan2(det, den)).sum(axis=1)) > 2*np.pi
        # Punto coplanar dentro de cada triángulo (incluye aristas/vértices).
        n = normal / norma[:, None]
        superficie = abs(np.sum(a*n, axis=-1)) <= tolerancia
        for u, v in ((a, b), (b, c), (c, a)):
            superficie &= np.sum(np.cross(u, v)*n, axis=-1) >= -tolerancia * np.maximum(la, np.maximum(lb, lc))
        en_cara = superficie.any(axis=1)
        resultado[inicio:inicio + len(p)] = (dentro | en_cara) if incluir_frontera else (dentro & ~en_cara)
    return resultado


def voxelizar_ifc(solidos: list[SolidoIFC], paso: float) -> GrillaVertidas:
    if not np.isfinite(paso) or paso <= 0 or not solidos:
        raise ValueError('Se requieren sólidos y paso positivo finito.')
    if len({s.vertida_id for s in solidos}) != len(solidos) or any(s.vertida_id <= 0 for s in solidos):
        raise ValueError('Los sólidos requieren IDs positivos y únicos.')
    minimo = np.min([s.vertices.min(axis=0) for s in solidos], axis=0)
    maximo = np.max([s.vertices.max(axis=0) for s in solidos], axis=0)
    forma = np.ceil((maximo-minimo)/paso).astype(int)
    ids = np.zeros(tuple(forma), dtype=np.int32)
    centros = [minimo[e] + (np.arange(forma[e])+.5)*paso for e in range(3)]
    for s in sorted(solidos, key=lambda s: s.vertida_id):
        tol = max(np.ptp(s.vertices, axis=0).max(), 1.) * 1e-10
        indices = [np.flatnonzero((c >= s.vertices[:, e].min()-tol) & (c <= s.vertices[:, e].max()+tol)) for e, c in enumerate(centros)]
        if any(len(i) == 0 for i in indices):
            continue
        # Una capa por vez para evitar crear todos los puntos del dominio.
        for iz in indices[2]:
            ix, iy = np.meshgrid(indices[0], indices[1], indexing='ij')
            puntos = np.column_stack((centros[0][ix.ravel()], centros[1][iy.ravel()], np.full(ix.size, centros[2][iz])))
            mascara = contiene(s, puntos)
            x, y = ix.ravel()[mascara], iy.ravel()[mascara]
            ocupados = ids[x, y, iz] != 0
            if ocupados.any():
                # Una frontera compartida se asigna al menor ID; se rechaza
                # un centro estrictamente interior a dos sólidos.
                interiores = contiene(s, puntos[mascara][ocupados], incluir_frontera=False)
                anteriores = ids[x[ocupados], y[ocupados], iz]
                for previo in np.unique(anteriores):
                    otro = next(o for o in solidos if o.vertida_id == previo)
                    mismos = anteriores == previo
                    if np.any(interiores[mismos] & contiene(otro, puntos[mascara][ocupados][mismos], incluir_frontera=False)):
                        raise ValueError('Solape entre vertidas en un centro de voxel.')
            ids[x[~ocupados], y[~ocupados], iz] = s.vertida_id
    return GrillaVertidas(ids, tuple(minimo), paso)


def caras_expuestas(ids: np.ndarray, activos: np.ndarray | None = None) -> dict[str, np.ndarray]:
    """Una máscara por orientación: celda activa sin vecino activo."""
    activos = _mascara_activos(ids, activos)
    resultado = {}
    for eje, letra in enumerate('xyz'):
        for signo, delta in (('-', -1), ('+', 1)):
            vecino = np.roll(activos, -delta, axis=eje)
            borde = [slice(None)]*3
            borde[eje] = 0 if delta == -1 else -1
            vecino[tuple(borde)] = False
            resultado[letra+signo] = activos & ~vecino
    return resultado


def interfaces(ids: np.ndarray, activos: np.ndarray | None = None) -> dict[str, np.ndarray]:
    """Caras entre IDs diferentes; solo orientaciones positivas, sin duplicar."""
    activos = _mascara_activos(ids, activos)
    salida = {}
    for eje, letra in enumerate('xyz'):
        vecino = np.roll(ids, -1, axis=eje)
        m = activos & np.roll(activos, -1, axis=eje) & (ids != vecino)
        sl = [slice(None)]*3
        sl[eje] = -1
        m[tuple(sl)] = False
        salida[letra+'+'] = m
    return salida


def _mascara_activos(ids, activos):
    ids = np.asarray(ids)
    if ids.ndim != 3 or any(n == 0 for n in ids.shape) or not np.issubdtype(ids.dtype, np.integer) or np.any(ids < 0):
        raise ValueError('Se requiere mapa 3D no vacío de IDs enteros no negativos.')
    if activos is not None and np.shape(activos) != ids.shape:
        raise ValueError('La máscara activa debe tener la misma forma que los IDs.')
    return ids > 0 if activos is None else np.asarray(activos, bool) & (ids > 0)
