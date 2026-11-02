"""Visualización 3D de la grilla y de la simulación por etapas (guía G06).

Dos salidas, ninguna con dependencias nuevas:

- **VTK para ParaView**: un ``ImageData`` (``.vti``) por instante con
  ``temperatura``, ``vertida_id`` y ``material`` como datos de celda, más un
  ``.pvd`` con la serie temporal (tiempo en horas). Es el formato que propone
  G06 (``pyvista.ImageData(...).save``); se escribe directamente en XML de
  VTK con datos binarios en base64, sin instalar PyVista/VTK.
- **Figura 3D (matplotlib)**: las caras exteriores de los voxeles visibles,
  con un corte en el plano y = centro para ver el interior.

Qué está activo en cada instante sale del **plan** (inicio y visibilidad de
cada vertida), igual que en el simulador: la secuencia está en los inputs.
"""

from __future__ import annotations

import base64
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from xml.sax.saxutils import quoteattr

import numpy as np

from .bim.voxelizador import GrillaBIM
from .thermal.etapas import PlanVertida, ResultadoEtapas

HORA = 3600.0
MATERIAL = {"vacio": 0, "hormigon": 1, "suelo": 2}
_TIPOS_VTK = {np.dtype(np.float32): "Float32", np.dtype(np.float64): "Float64",
              np.dtype(np.int16): "Int16", np.dtype(np.int32): "Int32", np.dtype(np.uint8): "UInt8"}


def activo_en(grilla: GrillaBIM, plan: Sequence[PlanVertida], t_s: float) -> np.ndarray:
    """Voxeles de hormigón activo en t: vertidas visibles con inicio <= t."""
    vids = [p.vertida_id for p in plan if p.visible and p.inicio_s <= t_s + 1e-9]
    return np.isin(grilla.vertida_id, vids)


def material_en(grilla: GrillaBIM, plan: Sequence[PlanVertida], t_s: float) -> np.ndarray:
    m = np.zeros(grilla.forma, dtype=np.uint8)
    m[grilla.es_suelo] = MATERIAL["suelo"]
    m[activo_en(grilla, plan, t_s)] = MATERIAL["hormigon"]
    return m


# --- VTK ------------------------------------------------------------------------------

def _data_array(nombre: str, valores: np.ndarray) -> str:
    plano = np.ascontiguousarray(valores.ravel(order="F"))  # VTK: x varía más rápido
    tipo = _TIPOS_VTK.get(plano.dtype)
    if tipo is None:
        raise ValueError(f"{nombre}: tipo {plano.dtype} no soportado para VTK.")
    crudo = plano.astype(plano.dtype.newbyteorder("<"), copy=False).tobytes()
    datos = base64.b64encode(struct.pack("<Q", len(crudo)) + crudo).decode("ascii")
    return f'<DataArray type="{tipo}" Name={quoteattr(nombre)} format="binary">{datos}</DataArray>'


def escribir_vti(ruta: str | Path, grilla: GrillaBIM, campos_celda: Mapping[str, np.ndarray]) -> Path:
    """Escribe un ImageData (.vti) con datos de celda; abre en ParaView."""
    ruta = Path(ruta)
    nx, ny, nz = grilla.forma
    for nombre, v in campos_celda.items():
        if v.shape != grilla.forma:
            raise ValueError(f"{nombre}: forma {v.shape} distinta de la grilla {grilla.forma}.")
    ox, oy, oz = grilla.definicion.origen
    dx, dy, dz = grilla.paso
    arreglos = "".join(_data_array(n, v) for n, v in campos_celda.items())
    xml = (
        '<?xml version="1.0"?>\n'
        '<VTKFile type="ImageData" version="1.0" byte_order="LittleEndian" header_type="UInt64">'
        f'<ImageData WholeExtent="0 {nx} 0 {ny} 0 {nz}" Origin="{ox} {oy} {oz}" Spacing="{dx} {dy} {dz}">'
        f'<Piece Extent="0 {nx} 0 {ny} 0 {nz}"><CellData Scalars="temperatura">{arreglos}</CellData></Piece>'
        "</ImageData></VTKFile>\n"
    )
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(xml, encoding="ascii")
    return ruta


def escribir_serie_vtk(carpeta: str | Path, grilla: GrillaBIM, plan: Sequence[PlanVertida],
                       resultado: ResultadoEtapas, prefijo: str = "temperatura") -> Path:
    """Un .vti por campo guardado y un .pvd con la serie (tiempo en horas)."""
    if not resultado.campos:
        raise ValueError("La simulación no guardó campos: usar simulacion.guardar_campos_cada_h.")
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    ids = grilla.vertida_id.astype(np.int16)
    entradas = []
    for n, t in enumerate(sorted(resultado.campos)):
        material = material_en(grilla, plan, t)
        T = np.where(material > 0, resultado.campos[t], np.nan).astype(np.float32)  # vacío: sin valor
        nombre = f"{prefijo}_{n:04d}.vti"
        escribir_vti(carpeta / nombre, grilla, {"temperatura": T, "vertida_id": ids, "material": material})
        entradas.append(f'<DataSet timestep="{t / HORA:g}" part="0" file="{nombre}"/>')
    pvd = carpeta / f"{prefijo}.pvd"
    pvd.write_text(
        '<?xml version="1.0"?>\n<VTKFile type="Collection" version="0.1" byte_order="LittleEndian">'
        f"<Collection>{''.join(entradas)}</Collection></VTKFile>\n",
        encoding="ascii",
    )
    return pvd


# --- figura 3D --------------------------------------------------------------------------------

def _caras(mascara: np.ndarray, origen: np.ndarray, paso: np.ndarray):
    """Quads de las caras exteriores de una máscara (incluye el borde de la caja)."""
    quads, celdas = [], []
    # Vértices de la cara (+) de cada eje, como desplazamientos de esquina en unidades de celda.
    esquinas = {
        0: np.array([[1, 0, 0], [1, 1, 0], [1, 1, 1], [1, 0, 1]]),
        1: np.array([[0, 1, 0], [1, 1, 0], [1, 1, 1], [0, 1, 1]]),
        2: np.array([[0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]]),
    }
    relleno = np.pad(mascara, 1, constant_values=False)
    for eje in range(3):
        for signo in (1, -1):
            desplazado = np.roll(relleno, -signo, axis=eje)[1:-1, 1:-1, 1:-1]
            expuesta = mascara & ~desplazado
            idx = np.argwhere(expuesta)
            if not len(idx):
                continue
            offs = esquinas[eje].copy()
            if signo < 0:
                offs[:, eje] = 0
            vert = (idx[:, None, :] + offs[None, :, :]) * paso + origen
            quads.append(vert)
            celdas.append(idx)
    if not quads:
        return np.zeros((0, 4, 3)), np.zeros((0, 3), dtype=int)
    return np.concatenate(quads), np.concatenate(celdas)


def dibujar_3d(ax, grilla: GrillaBIM, valores: np.ndarray, visible: np.ndarray, cmap, norm,
               cortar: bool = True, titulo: str = "", exageracion_z: float = 2.0):
    """Caras de los voxeles ``visible`` coloreadas por ``valores``; corte en y = centro.

    Se quita la mitad y < centro, la que mira a la cámara, para que la cara
    del corte muestre el interior. ``exageracion_z`` solo estira el dibujo.
    """
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    mascara = visible.copy()
    if cortar:
        mascara[:, : grilla.forma[1] // 2, :] = False  # media fundación: el corte muestra el interior
    origen = np.asarray(grilla.definicion.origen)
    paso = np.asarray(grilla.paso)
    quads, celdas = _caras(mascara, origen, paso)
    if len(quads):
        colores = cmap(norm(valores[tuple(celdas.T)]))
        ax.add_collection3d(Poly3DCollection(quads, facecolors=colores, edgecolor="none"))
    if visible.any():  # encuadre ajustado a lo dibujable, no a la caja con aire
        idx = np.argwhere(visible)
        lo = origen + paso * idx.min(axis=0)
        hi = origen + paso * (idx.max(axis=0) + 1)
    else:
        lo, hi = origen, origen + paso * np.asarray(grilla.forma)
    ax.set_xlim(lo[0], hi[0])
    ax.set_ylim(lo[1], hi[1])
    ax.set_zlim(lo[2], hi[2])
    ax.set_box_aspect((hi - lo) * np.array([1.0, 1.0, exageracion_z]))
    ax.view_init(elev=22, azim=-62)
    ax.set_axis_off()
    if titulo:
        ax.set_title(titulo, fontsize=10)
    return len(quads)
