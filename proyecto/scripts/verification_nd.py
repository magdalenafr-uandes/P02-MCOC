"""Laboratorio E04/E05: un caso por ejecución y parámetros modificables.

Motor SolverVoxel. Neumann --flujo POSITIVO ENTRANDO, igual que voxel.py.
"""
import argparse
from pathlib import Path
import numpy as np
from mcplan.thermal import (MallaVoxel, SolverVoxel, adiabatico, dirichlet,
                            neumann, robin, solucion_sinusoidal_nd)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--caso',choices=['sinusoidal','adiabatico','fuente','neumann','robin','materiales'],default='sinusoidal')
    p.add_argument('--dim',type=int,choices=[1,2,3],default=2)
    p.add_argument('--n',type=int,default=16,help='Celdas por eje')
    p.add_argument('--longitudes',type=float,nargs='+',help='Una longitud por eje [m]')
    p.add_argument('--tiempo',type=float,default=21600.,help='Segundos')
    p.add_argument('--dt',type=float,help='Paso solicitado; se ajusta al tiempo final sin superarlo')
    p.add_argument('--seguridad',type=float,default=.6,help='Fracción del límite monótono (0,1]')
    p.add_argument('--k',type=float,default=2.22)
    p.add_argument('--rho',type=float,default=2400.)
    p.add_argument('--cp',type=float,default=970.)
    p.add_argument('--inicial',type=float,default=20.)
    p.add_argument('--amplitud',type=float,default=50.)
    p.add_argument('--fuente',type=float,default=1000.,help='W/m³; caso fuente')
    p.add_argument('--flujo',type=float,default=100.,help='W/m² ENTRANDO en x+; caso Neumann')
    p.add_argument('--h',type=float,default=12.)
    p.add_argument('--ambiente',type=float,default=20.)
    p.add_argument('--resistencia',type=float,default=0.,help='R_extra [m² K/W]; caso Robin')
    p.add_argument('--caliente',type=float,default=80.,help='Dirichlet x- en Robin/materiales')
    p.add_argument('--k2',type=float,default=5.,help='Segundo material en mitad derecha')
    p.add_argument('--figura',type=Path,help='PNG; en 3D muestra corte central en z')
    a=p.parse_args()
    L=a.longitudes if a.longitudes is not None else [1.]*a.dim
    if len(L)!=a.dim:
        p.error('--longitudes necesita una longitud por eje')
    try:
        if not np.isfinite(a.tiempo) or a.tiempo<0:
            raise ValueError('Tiempo finito no negativo.')
        if any(not np.isfinite(l) or l<=0 for l in L):
            raise ValueError('Longitudes positivas y finitas.')
        if not np.isfinite(a.seguridad) or not 0<a.seguridad<=1:
            raise ValueError('Seguridad debe estar en (0,1].')
        if a.caso=='materiales' and a.n%2:
            raise ValueError('Materiales necesita --n par: interfaz en Lx/2.')
        k=a.k
        if a.caso=='materiales':
            k=np.full((a.n,)*a.dim,a.k)
            k[a.n//2:]=a.k2
        m=MallaVoxel((a.n,)*a.dim,tuple(l/a.n for l in L),k,a.rho,a.cp)
        bordes={c:adiabatico() for c in m.caras}
        if a.caso=='sinusoidal':
            bordes={c:dirichlet(a.inicial) for c in m.caras}
        elif a.caso=='neumann':
            bordes['x+']=neumann(a.flujo)
        elif a.caso in ('robin','materiales'):
            bordes['x-']=dirichlet(a.caliente)
            bordes['x+']=robin(a.ambiente,a.h,a.resistencia) if a.caso=='robin' else dirichlet(a.ambiente)
        fuente=a.fuente if a.caso=='fuente' else 0.
        solver=SolverVoxel(m,bordes,fuente)
        X=m.malla_centros()
        T=np.full(m.forma,a.inicial)
        exacta=None
        if a.caso=='sinusoidal':
            alpha=a.k/(a.rho*a.cp)
            T=solucion_sinusoidal_nd(X,0.,alpha,a.inicial,a.amplitud,tuple(L))
            exacta=solucion_sinusoidal_nd(X,a.tiempo,alpha,a.inicial,a.amplitud,tuple(L))
        elif a.caso=='adiabatico':
            T+=a.amplitud*np.exp(-sum(((x-.35*l)/(.12*l))**2 for x,l in zip(X,L)))
        elif a.caso=='fuente':
            exacta=np.full(m.forma,a.inicial+fuente*a.tiempo/(a.rho*a.cp))
        limite=solver.dt_max()
        solicitado=a.dt if a.dt is not None else a.seguridad*limite
        if not np.isfinite(solicitado) or solicitado<=0:
            raise ValueError('dt positivo y finito.')
        if solicitado>limite*(1+1e-12):
            raise ValueError(f'Paso inestable según criterio conservador: dt={solicitado:g}, dt_max={limite:g} s')
        pasos=int(np.ceil(a.tiempo/solicitado))
        dt=a.tiempo/pasos if pasos else solicitado
        r=solver.resolver(T,dt,pasos)
        borde=sum(r.calor_borde_acumulado.values())
        cambio=r.energia[-1]-r.energia[0]
        residuo=cambio-r.calor_fuente_acumulado-borde
        print(f'Caso={a.caso}, dim={a.dim}, celdas={m.forma}, dx={m.paso} m')
        print('Signos: calor de borde y Neumann positivos ENTRANDO al sólido.')
        print(f't={a.tiempo:g} s; pasos={pasos}; dt={dt if pasos else 0.:.8g}; límite monótono={limite:.8g} s')
        print(f'Tmin={r.T.min():.8g}; Tmax={r.T.max():.8g} °C')
        print(f'Efinal-Einicial={cambio:.10g}; fuente={r.calor_fuente_acumulado:.10g}; borde entrante={borde:.10g}')
        print(f'Residuo balance={residuo:.6e} (J en 3D; J/m en 2D; J/m² en 1D)')
        if exacta is not None:
            print(f'Error máximo={np.max(abs(r.T-exacta)):.8g} °C')
        Ts=solver.temperatura_superficie(r.T)['x+']
        print(f'Superficie x+: mín={np.min(Ts):.8g}, máx={np.max(Ts):.8g} °C')
        if a.caso in ('robin','materiales'):
            # Referencia estacionaria: no se declara exacta la solución transitoria.
            if a.caso=='robin':
                q=(a.caliente-a.ambiente)/(L[0]/a.k+a.resistencia+1/a.h)
                estacionaria=a.caliente-q*X[0]/a.k
            else:
                q=(a.caliente-a.ambiente)/(.5*L[0]/a.k+.5*L[0]/a.k2)
                estacionaria=a.caliente-q*(np.minimum(X[0],L[0]/2)/a.k+np.maximum(X[0]-L[0]/2,0)/a.k2)
            print(f'Distancia a referencia ESTACIONARIA={np.max(abs(r.T-estacionaria)):.8g} °C (no es error transitorio)')
        if a.figura:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            a.figura.parent.mkdir(parents=True,exist_ok=True)
            fig,ax=plt.subplots(figsize=(8,5),layout='constrained')
            if a.dim==1:
                ax.plot(m.centros(0),r.T,label='Numérica')
                if exacta is not None:
                    ax.plot(m.centros(0),exacta,'--',label='Exacta')
                if a.caso in ('robin','materiales'):
                    ax.plot(m.centros(0),estacionaria,':',label='Referencia estacionaria')
                ax.set_ylabel('Temperatura [°C]'); ax.legend()
            else:
                campo=r.T if a.dim==2 else r.T[:,:,a.n//2]
                im=ax.imshow(campo.T,origin='lower',extent=[0,L[0],0,L[1]],aspect='equal',cmap='inferno')
                fig.colorbar(im,ax=ax,label='Temperatura [°C]'); ax.set_ylabel('y [m]')
            ax.set_xlabel('x [m]')
            corte=f'; z={m.centros(2)[a.n//2]:.3g} m' if a.dim==3 else ''
            ax.set_title(f'{a.caso} {a.dim}D; t={a.tiempo:g} s{corte}')
            fig.savefig(a.figura,dpi=160); plt.close(fig)
            print(f'Figura: {a.figura}')
    except (ValueError,ZeroDivisionError) as exc:
        p.exit(2,f'Error: {exc}\n')


if __name__=='__main__':
    main()
