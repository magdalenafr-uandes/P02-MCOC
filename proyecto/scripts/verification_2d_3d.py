"""Figuras reproducibles de E04: solver 2D/3D por balance de voxel.

Genera en ``results/figures/``:

1. ``e04_convergencia_2d_3d.png``  — error vs. Δx (orden 2) contra la solución
   sinusoidal exacta en 2D y 3D, y el campo 2D numérico vs. exacto.
2. ``e04_corte_3d.png``            — corte a media altura del caso 3D.
3. ``e04_bordes_dominan.png``      — misma sección de hormigón (3.3 m sobre
   2 m de suelo, dos materiales) con fuente volumétrica constante y cuatro
   hipótesis distintas en la cara superior.
4. ``e04_estabilidad.png`` — monotonía, estabilidad sin monotonía y crecimiento.

Uso:
    python scripts/verification_2d_3d.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from mcplan.thermal import (
    MallaVoxel,
    PropiedadesTermicas,
    SolverVoxel,
    adiabatico,
    dirichlet,
    robin,
    solucion_sinusoidal_nd,
)

RAIZ = Path(__file__).resolve().parents[1]
FIG = RAIZ / "results" / "figures"
HORMIGON = PropiedadesTermicas(k=2.22, rho=2400.0, cp=970.0)  # Ju y Lei (2019)
SUELO = PropiedadesTermicas(k=1.39, rho=1800.0, cp=1273.0)  # Ju y Lei (2019)
DIA = 86400.0


def _sinusoidal(n: int, dim: int, t_final: float):
    L = 1.0
    malla = MallaVoxel.uniforme((n,) * dim, (L / n,) * dim, HORMIGON)
    solver = SolverVoxel(malla, {c: dirichlet(20.0) for c in malla.caras})
    X = malla.malla_centros()
    T_ini = solucion_sinusoidal_nd(X, 0.0, HORMIGON.alpha, 20.0, 50.0, (L,) * dim)
    n_pasos = int(np.ceil(t_final / (0.9 * solver.dt_max())))
    res = solver.resolver(T_ini, t_final / n_pasos, n_pasos)
    exacta = solucion_sinusoidal_nd(X, t_final, HORMIGON.alpha, 20.0, 50.0, (L,) * dim)
    return malla, res.T, exacta, float(np.max(np.abs(res.T - exacta)))


def figura_convergencia() -> None:
    fig, ejes = plt.subplots(1, 3, figsize=(15, 4.4))
    for dim, t_final, marca in ((2, 3 * DIA, "o-"), (3, DIA, "s-")):
        ns = (8, 16, 32, 64) if dim == 2 else (8, 16, 32)
        dxs, errs = [], []
        for n in ns:
            *_, e = _sinusoidal(n, dim, t_final)
            dxs.append(1.0 / n)
            errs.append(e)
            print(f"{dim}D  n={n:3d}  dx={1/n:.4f} m  error_inf={e:.3e} °C")
        orden = np.polyfit(np.log(dxs), np.log(errs), 1)[0]
        ejes[0].loglog(dxs, errs, marca, label=f"{dim}D (pendiente {orden:.2f})")
    d = np.array([1 / 64, 1 / 8])
    ejes[0].loglog(d, 0.5 * errs[-1] * (d / d[0]) ** 2, "k--", label="referencia O(Δx²)")
    ejes[0].set_xlabel("Δx [m]")
    ejes[0].set_ylabel("error máximo [°C]")
    ejes[0].set_title("Convergencia vs. solución exacta")
    ejes[0].legend()

    malla, T, exacta, e = _sinusoidal(32, 2, 3 * DIA)
    ext = [0, 1, 0, 1]
    for ax, campo, titulo in ((ejes[1], T, "Numérica 2D"), (ejes[2], exacta, "Exacta 2D")):
        im = ax.imshow(campo.T, origin="lower", extent=ext, vmin=20, vmax=exacta.max())
        ax.set_title(f"{titulo}, t = 3 días")
        ax.set_xlabel("x [m]")
        ax.set_ylabel("y [m]")
        fig.colorbar(im, ax=ax, label="T [°C]")
    fig.suptitle(f"Hormigón α = {HORMIGON.alpha:.2e} m²/s, Dirichlet 20 °C; error 2D (32²) = {e:.2e} °C")
    fig.tight_layout()
    fig.savefig(FIG / "e04_convergencia_2d_3d.png", dpi=150)
    plt.close(fig)


def figura_corte_3d() -> None:
    malla, T, exacta, e = _sinusoidal(32, 3, DIA)
    k = malla.forma[2] // 2
    fig, ejes = plt.subplots(1, 2, figsize=(10, 4.2))
    for ax, campo, titulo in ((ejes[0], T, "Numérica"), (ejes[1], campo_err := np.abs(T - exacta), "|error|")):
        im = ax.imshow(campo[:, :, k].T, origin="lower", extent=[0, 1, 0, 1])
        ax.set_title(f"3D {titulo}, corte z = {malla.centros(2)[k]:.3f} m")
        ax.set_xlabel("x [m]")
        ax.set_ylabel("y [m]")
        fig.colorbar(im, ax=ax, label="°C")
    fig.suptitle(f"Caso 3D 32³ voxeles, t = 1 día, error máx = {e:.2e} °C")
    fig.tight_layout()
    fig.savefig(FIG / "e04_corte_3d.png", dpi=150)
    plt.close(fig)


def figura_bordes_dominan() -> None:
    """Sección vertical: 3.3 m de hormigón sobre 2 m de suelo (x de 0 a 3 m).

    x- es plano de simetría (adiabático), x+ adiabático (franja central),
    z- Dirichlet a 18 °C (suelo profundo). La fuente es constante e
    ilustrativa (NO es todavía el calor de hidratación).
    """
    dz = dx = 0.1
    nz_suelo, nz_horm, nx = 20, 33, 30
    material = np.zeros((nx, nz_suelo + nz_horm), dtype=int)
    material[:, nz_suelo:] = 1
    malla = MallaVoxel.desde_materiales((dx, dz), material, {0: SUELO, 1: HORMIGON})
    q = np.where(material == 1, 150.0, 0.0)  # W/m³ solo en el hormigón
    T_ini = 18.0
    casos = {
        "Superior adiabática": adiabatico(),
        "Robin h=10, T∞=20 °C": robin(20.0, 10.0),
        "Robin + aislación 50 mm (k=0.04)": robin(20.0, 10.0, R_extra=0.05 / 0.04),
        "Dirichlet 20 °C (¡error típico!)": dirichlet(20.0),
    }
    t_final = 7 * DIA
    i_nucleo = nz_suelo + nz_horm // 2
    fig, ejes = plt.subplots(1, 3, figsize=(16, 4.6))
    campos = {}
    for nombre, superior in casos.items():
        bordes = {"x-": adiabatico(), "x+": adiabatico(), "y-": dirichlet(18.0), "y+": superior}
        solver = SolverVoxel(malla, bordes, fuente=q)
        dt = 0.9 * solver.dt_max()
        n = int(np.ceil(t_final / dt))
        dt = t_final / n
        res = solver.resolver(T_ini, dt, n, guardar_cada=max(1, n // 140))
        t = np.array(list(res.instantaneas)) / DIA
        nucleo = [c[0, i_nucleo] for c in res.instantaneas.values()]
        sup = [solver.temperatura_superficie(c)["y+"][0] for c in res.instantaneas.values()]
        linea, = ejes[0].plot(t, nucleo, label=nombre)
        ejes[0].plot(t, sup, "--", color=linea.get_color())
        ejes[1].plot(t, np.array(nucleo) - np.array(sup), color=linea.get_color(), label=nombre)
        campos[nombre] = res.T
        print(f"{nombre:36s} T_núcleo={nucleo[-1]:6.2f} °C  T_sup={sup[-1]:6.2f} °C  dt={dt:.0f} s")
    ejes[0].set_title("Núcleo (—) y superficie del sólido (--)")
    ejes[0].set_xlabel("t [días]")
    ejes[0].set_ylabel("T [°C]")
    ejes[0].legend(fontsize=8)
    ejes[1].axhline(20.0, color="k", lw=0.8, ls=":")
    ejes[1].set_title("Diferencial núcleo − superficie")
    ejes[1].set_xlabel("t [días]")
    ejes[1].set_ylabel("ΔT [°C]")
    z = malla.centros(1) - nz_suelo * dz
    for nombre, T in campos.items():
        ejes[2].plot(T[0], z, label=nombre)
    ejes[2].axhline(0.0, color="k", lw=0.8)
    ejes[2].text(0.02, 0.03, "suelo", transform=ejes[2].transAxes)
    ejes[2].set_title("Perfil vertical a los 7 días")
    ejes[2].set_xlabel("T [°C]")
    ejes[2].set_ylabel("z [m] (0 = base del hormigón)")
    fig.suptitle("Misma fuente (150 W/m³ constante, ilustrativa), mismos materiales: solo cambia la condición de la cara superior")
    fig.tight_layout()
    fig.savefig(FIG / "e04_bordes_dominan.png", dpi=150)
    plt.close(fig)


def figura_estabilidad() -> None:
    malla = MallaVoxel.uniforme((20, 20), (0.1, 0.1), HORMIGON)
    solver = SolverVoxel(malla, {c: dirichlet(20.0) for c in malla.caras})
    rng = np.random.default_rng(1)
    T_ini = 20.0 + 30.0 * rng.random(malla.forma)
    dt_lim = solver.dt_max()
    dt_fourier = 0.25 * 0.1**2 / HORMIGON.alpha
    fig, ejes = plt.subplots(1, 3, figsize=(16, 4.2))
    for ax, dt, titulo in (
        (ejes[0], dt_lim, f"Monótono: dt = C/ΣG = {dt_lim:.0f} s"),
        (ejes[1], dt_fourier, f"Estable, sin garantía de monotonía\ndt = dx²/(4α) = {dt_fourier:.0f} s"),
        (ejes[2], 1.1 * dt_fourier, f"Inestable: dt = 1.1·dx²/(4α)\n= {1.1 * dt_fourier:.0f} s"),
    ):
        res = solver.resolver(T_ini, dt, 60, verificar_estabilidad=False)
        im = ax.imshow(res.T.T, origin="lower", cmap="coolwarm")
        ax.set_title(f"{titulo}\nT ∈ [{res.T.min():.3g}, {res.T.max():.3g}] °C")
        fig.colorbar(im, ax=ax)
    fig.suptitle("Caja homogénea 2D: límite suficiente monótono dx²/(6α); límite espectral dx²/(4α)")
    fig.tight_layout()
    fig.savefig(FIG / "e04_estabilidad.png", dpi=150)
    plt.close(fig)


def main() -> int:
    FIG.mkdir(parents=True, exist_ok=True)
    figura_convergencia()
    figura_corte_3d()
    figura_bordes_dominan()
    figura_estabilidad()
    print(f"Figuras en {FIG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
