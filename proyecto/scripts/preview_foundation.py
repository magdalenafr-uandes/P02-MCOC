"""Vista del IFC existente, sin regenerar ni modificar el modelo."""
import argparse
from pathlib import Path
import numpy as np
import ifcopenshell
import ifcopenshell.geom
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from mcplan.bim.ifc_io import productos_vertida


def main():
    raiz = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ifc',type=Path,default=raiz/'geometry/foundation.ifc')
    p.add_argument('--salida',type=Path,default=raiz/'results/figures/foundation_e04.png')
    a = p.parse_args()
    modelo = ifcopenshell.open(str(a.ifc))
    settings = ifcopenshell.geom.settings()
    settings.set('use-world-coords',True)
    fig = plt.figure(figsize=(10,7),layout='constrained')
    ax = fig.add_subplot(111,projection='3d')
    puntos = []
    for i,obj in enumerate(productos_vertida(modelo)):
        forma = ifcopenshell.geom.create_shape(settings,obj)
        v = np.asarray(forma.geometry.verts).reshape(-1,3)
        f = np.asarray(forma.geometry.faces).reshape(-1,3)
        color = plt.get_cmap('tab10')(i%10)
        ax.add_collection3d(Poly3DCollection(v[f],facecolor=color,edgecolor='gray',linewidth=.2,alpha=.85))
        ax.plot([],[],[],color=color,label=obj.Name)
        puntos.append(v)
    if not puntos:
        p.error('El IFC no contiene vertidas identificables')
    v = np.concatenate(puntos)
    lo,hi = v.min(axis=0),v.max(axis=0)
    ax.set_xlim(lo[0],hi[0]); ax.set_ylim(lo[1],hi[1]); ax.set_zlim(lo[2],hi[2])
    ax.set_box_aspect(hi-lo)
    ax.set_xlabel('x [m]'); ax.set_ylabel('y [m]'); ax.set_zlabel('z [m]')
    ax.set_title('Fundación IFC existente — cinco vertidas\nGeometría docente; sin acoplamiento automático al solver')
    ax.legend(loc='upper left')
    ax.view_init(elev=22,azim=-55)
    a.salida.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(a.salida,dpi=160)
    plt.close(fig)
    print(a.salida)


if __name__ == '__main__':
    main()
