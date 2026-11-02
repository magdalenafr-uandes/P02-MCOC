"""Demos E07: geometría IFC, volumen, activación y curva adiabática.

Parámetros térmicos docentes por defecto; ajuste opcional a CSV adiabático.
Ejecutar desde la raíz con proyecto/.venv/Scripts/python.exe proyecto/scripts/demo_e07.py.
"""
from pathlib import Path
import argparse
import csv
import json
import hashlib

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from mcplan.bim.voxel_ifc import extraer_solidos, voxelizar_ifc, caras_expuestas, interfaces
from mcplan.thermal.hidratacion import ajustar_csv
from mcplan.thermal.material import cargar_hormigon
from mcplan.thermal.vertidas import SimuladorVertidas

RAIZ = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--ifc', type=Path, default=RAIZ/'geometry/foundation.ifc')
    parser.add_argument('--pasos', nargs='+', type=float, default=[.4, .2, .1])
    parser.add_argument('--paso-termico', type=float, default=.4, help='Voxel de la demo térmica [m].')
    parser.add_argument('--salida', type=Path, default=RAIZ/'results/e07')
    parser.add_argument('--horas', type=float, default=None, help='Final absoluto [h]; defecto: última vertida + 24 h.')
    parser.add_argument('--material', type=Path, default=RAIZ/'configs/hormigon_M1.json')
    parser.add_argument('--curva-adiabatica', type=Path, help='CSV experimental: edad_h,incremento_K. Ajusta hidratación; no k, rho ni cp.')
    args = parser.parse_args()
    if not args.pasos or any(not np.isfinite(dx) or dx <= 0 for dx in args.pasos):
        parser.error('--pasos requiere valores positivos finitos.')
    props, hidratacion, material = cargar_hormigon(args.material)
    ajuste = None
    if args.curva_adiabatica is not None:
        resultado, ajuste = ajustar_csv(args.curva_adiabatica)
        hidratacion = resultado.modelo
        material['estado'] = 'ajustado_a_curva_adiabatica_aportada_por_usuario'
        material['hidratacion'] = dict(incremento_K=hidratacion.incremento_K, escala_s=hidratacion.escala_s)
        material['fuentes'].append(dict(archivo=ajuste['archivo'], sha256=ajuste['sha256'], datos='Curva aportada; procedencia experimental a validar por el usuario.'))
        for aviso in resultado.advertencias:
            print(f'AVISO DE AJUSTE: {aviso}')
    solidos = extraer_solidos(args.ifc)
    if {s.tipo_hormigon for s in solidos} != {material['material']}:
        raise ValueError('TipoHormigon del IFC no coincide con la configuración del material.')
    args.salida.mkdir(parents=True, exist_ok=True)
    filas, grillas = [], {}
    for dx in sorted(set(args.pasos), reverse=True):
        g = voxelizar_ifc(solidos, dx)
        grillas[dx] = g
        for s in solidos:
            vh = g.volumen(s.vertida_id)
            filas.append(dict(paso_m=dx, vertida_id=s.vertida_id, volumen_ifc_m3=s.volumen,
                              volumen_voxel_m3=vh, error_relativo=abs(vh-s.volumen)/s.volumen))
        vref = sum(s.volumen for s in solidos)
        vh = np.count_nonzero(g.vertida_id)*dx**3
        filas.append(dict(paso_m=dx, vertida_id='total', volumen_ifc_m3=vref,
                          volumen_voxel_m3=vh, error_relativo=abs(vh-vref)/vref))
        print(f'dx={dx:g} m: IFC={vref:.3f} m³, voxeles={vh:.3f} m³, error={abs(vh-vref)/vref:.3%}')
    with (args.salida/'volumenes.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(filas[0]))
        writer.writeheader()
        writer.writerows(filas)

    fig, axes = plt.subplots(2, len(grillas), figsize=(5*len(grillas), 8), squeeze=False)
    for col, (dx, g) in enumerate(grillas.items()):
        ids = np.ma.masked_equal(g.vertida_id, 0)
        x, y, z = [g.centros(e) for e in range(3)]
        for row, horizontal, vertical, datos in ((0, x, y, ids[:, :, 0].T), (1, x, z, ids[:, len(y)//2, :].T)):
            axes[row, col].pcolormesh(horizontal, vertical, datos, cmap='tab10', vmin=.5, vmax=10.5, shading='nearest')
            axes[row, col].set_aspect('equal')
            axes[row, col].set_title(f'{"Planta inferior" if row == 0 else "Corte central"}; dx={dx:g} m')
            axes[row, col].set_xlabel('x [m]')
            axes[row, col].set_ylabel('y [m]' if row == 0 else 'z [m]')
    fig.tight_layout()
    fig.savefig(args.salida/'voxelizacion.png', dpi=140)
    plt.close(fig)

    g = grillas.get(args.paso_termico)
    if g is None:
        g = voxelizar_ifc(solidos, args.paso_termico)
    sim = SimuladorVertidas(g, solidos, props, hidratacion, ambiente_C=20., h=8.)
    final_h = args.horas if args.horas is not None else max(s.inicio_s for s in solidos)/3600 + 24
    if not np.isfinite(final_h) or final_h <= 0:
        raise ValueError('--horas debe ser positivo y finito.')
    tiempos = sorted(set([0., final_h*3600] + list(np.arange(0, final_h*3600, 3600.)) + [s.inicio_s for s in solidos if s.inicio_s <= final_h*3600]))
    historia, cortes = [], []
    eventos = {s.inicio_s for s in solidos}
    for t in tiempos:
        e = sim.avanzar(t, dt_s=600.)
        area = sum(np.count_nonzero(m) for m in caras_expuestas(g.vertida_id, e.activos).values())*g.paso**2
        interfaz = sum(np.count_nonzero(m) for m in interfaces(g.vertida_id, e.activos).values())*g.paso**2
        historia.append(dict(tiempo_h=t/3600, volumen_activo_m3=int(e.activos.sum())*g.paso**3,
                             area_expuesta_m2=area, area_interfaz_m2=interfaz,
                             Tmax_C=float(e.T[e.activos].max()) if e.activos.any() else None,
                             energia_J=e.energia_J, hidratacion_J=e.hidratacion_J,
                             borde_J=e.borde_J, colocacion_J=e.colocacion_J, residuo_energia_J=e.residuo_energia_J))
        if t in eventos or t == tiempos[-1]:
            cortes.append((t, e.T[:, e.T.shape[1]//2, :].T.copy()))
    with (args.salida/'activacion.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(historia[0]))
        writer.writeheader()
        writer.writerows(historia)
    np.savez_compressed(args.salida/'estado_final.npz', vertida_id=g.vertida_id, activos=e.activos,
                        T_C=e.T, edad_s=e.edad_s, origen_m=g.origen, paso_m=g.paso, tiempo_s=e.tiempo_s)
    columnas = min(3, len(cortes))
    filas_fig = (len(cortes)+columnas-1)//columnas
    fig, axes = plt.subplots(filas_fig, columnas, figsize=(4.5*columnas, 1.9*filas_fig), squeeze=False, layout='constrained')
    temperaturas = np.concatenate([c[np.isfinite(c)] for _, c in cortes])
    vmin = float(temperaturas.min()) if temperaturas.size else 0.
    vmax = max(vmin+1, float(temperaturas.max())) if temperaturas.size else 1.
    for ax, (t, corte) in zip(axes.flat, cortes):
        im = ax.pcolormesh(g.centros(0), g.centros(2), np.ma.masked_invalid(corte), shading='nearest', cmap='inferno', vmin=vmin, vmax=vmax)
        ax.set_title(f't={t/3600:g} h')
        ax.set_aspect('equal')
        ax.set_xlabel('x [m]')
        ax.set_ylabel('z [m]')
    for ax in list(axes.flat)[len(cortes):]:
        ax.set_visible(False)
    fig.colorbar(im, ax=list(axes.flat), label='T [°C]')
    fig.suptitle('Activación e hidratación — ' + ('ajuste a curva aportada' if ajuste else 'referencia docente'))
    fig.savefig(args.salida/'activacion.png', dpi=140, bbox_inches='tight')
    plt.close(fig)
    edades = np.linspace(0, 7*86400, 300)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].plot(edades/3600, hidratacion.incremento(edades))
    axes[0].set_ylabel('Incremento adiabático [K]')
    axes[1].plot(edades/3600, hidratacion.qdot(edades, props.rho, props.cp))
    axes[1].set_ylabel('Generación volumétrica [W/m³]')
    for ax in axes:
        ax.set_xlabel('Edad desde colocación [h]')
        ax.grid(alpha=.3)
    fig.suptitle('Modelo sin dependencia de temperatura — ' + ('ajuste a curva aportada' if ajuste else 'referencia docente'))
    fig.tight_layout()
    fig.savefig(args.salida/'hidratacion.png', dpi=140)
    plt.close(fig)
    metadatos = dict(ifc=str(args.ifc.resolve()), material=material, ajuste=ajuste,
                    ifc_sha256=hashlib.sha256(args.ifc.read_bytes()).hexdigest(),
                    incremento_K=hidratacion.incremento_K, escala_s=hidratacion.escala_s,
                    rho_kg_m3=props.rho, cp_J_kg_K=props.cp, k_W_m_K=props.k, ambiente_C=20., h_W_m2_K=8.,
                    paso_termico_m=g.paso, dependencia_temperatura=False,
                    contacto='perfecto entre vertidas activas', borde='Robin uniforme en todas las caras expuestas',
                    vertidas=[dict(vertida_id=s.vertida_id, guid=s.guid, inicio_h=s.inicio_s/3600, temperatura_C=s.temperatura_C) for s in solidos])
    (args.salida/'parametros.json').write_text(json.dumps(metadatos, indent=2, ensure_ascii=False), encoding='utf-8')
    escala_energia = max(abs(e.energia_J), abs(e.colocacion_J)+abs(e.hidratacion_J)+abs(e.borde_J), 1.)
    resumen = dict(tiempo_final_h=e.tiempo_s/3600, Tmax_C=historia[-1]['Tmax_C'],
                   residuo_final_J=e.residuo_energia_J, residuo_final_relativo=abs(e.residuo_energia_J)/escala_energia,
                   residuo_max_abs_J=max(abs(f['residuo_energia_J']) for f in historia),
                   volumenes=filas,
                   alcance='Verificación numérica del modelo base; no validación experimental de M1. Robin uniforme, contacto perfecto y sin dependencia térmica de la cinética.')
    (args.salida/'resumen.json').write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'Demos guardadas en {args.salida}')


if __name__ == '__main__':
    main()
