"""Tests del solver 2D/3D por balance de voxel (E04).

Batería mínima de la guía de difusión (sección 33): 2D y 3D exactos con
convergencia, energía adiabática, fuente uniforme, Neumann con flujo,
Robin contra solución analítica, dos materiales y estabilidad.
"""

from __future__ import annotations

import numpy as np
import pytest

from mcplan.thermal import (
    MallaVoxel,
    PropiedadesTermicas,
    SolverVoxel,
    adiabatico,
    dirichlet,
    neumann,
    robin,
    solucion_pared_robin,
    solucion_sinusoidal_nd,
)

HORMIGON = PropiedadesTermicas(k=2.22, rho=2400.0, cp=970.0)
SUELO = PropiedadesTermicas(k=1.39, rho=1800.0, cp=1273.0)


def _todas(malla: MallaVoxel, borde) -> dict:
    return {c: borde for c in malla.caras}


def _error_sinusoidal(n: int, dim: int, t_final: float) -> float:
    L = 1.0
    malla = MallaVoxel.uniforme((n,) * dim, (L / n,) * dim, HORMIGON)
    solver = SolverVoxel(malla, _todas(malla, dirichlet(20.0)))
    X = malla.malla_centros()
    T_ini = solucion_sinusoidal_nd(X, 0.0, HORMIGON.alpha, 20.0, 50.0, (L,) * dim)
    n_pasos = int(np.ceil(t_final / (0.9 * solver.dt_max())))
    res = solver.resolver(T_ini, t_final / n_pasos, n_pasos)
    exacta = solucion_sinusoidal_nd(X, t_final, HORMIGON.alpha, 20.0, 50.0, (L,) * dim)
    return float(np.max(np.abs(res.T - exacta)))


@pytest.mark.parametrize("dim, t_final", [(2, 3 * 86400.0), (3, 86400.0)])
def test_sinusoidal_exacta_converge_segundo_orden(dim, t_final):
    e_grueso = _error_sinusoidal(10, dim, t_final)
    e_fino = _error_sinusoidal(20, dim, t_final)
    assert e_fino < 0.05
    orden = np.log2(e_grueso / e_fino)
    assert 1.8 < orden < 2.2


@pytest.mark.parametrize("dim", [2, 3])
def test_energia_se_conserva_con_bordes_adiabaticos(dim):
    rng = np.random.default_rng(0)
    forma = (8,) * dim
    material = (rng.random(forma) > 0.5).astype(int)
    malla = MallaVoxel.desde_materiales((0.1,) * dim, material, {0: HORMIGON, 1: SUELO})
    solver = SolverVoxel(malla, _todas(malla, adiabatico()))
    T_ini = 20.0 + 40.0 * rng.random(forma)
    res = solver.resolver(T_ini, solver.dt_max(), 500)
    assert res.energia[-1] == pytest.approx(res.energia[0], rel=1e-12)
    # sin pérdidas, el campo tiende al promedio ponderado por capacidad
    C = malla.capacidad
    assert np.ptp(res.T) < np.ptp(T_ini)
    assert np.sum(C * res.T) / np.sum(C) == pytest.approx(
        np.sum(C * T_ini) / np.sum(C), rel=1e-12
    )


def test_fuente_uniforme_adiabatica_eleva_temperatura_linealmente():
    malla = MallaVoxel.uniforme((6, 5, 4), (0.2, 0.2, 0.2), HORMIGON)
    q = 1000.0  # W/m³
    solver = SolverVoxel(malla, _todas(malla, adiabatico()), fuente=q)
    dt = 0.5 * solver.dt_max()
    res = solver.resolver(20.0, dt, 400)
    esperado = 20.0 + q * res.tiempos[-1] / (HORMIGON.rho * HORMIGON.cp)
    np.testing.assert_allclose(res.T, esperado, rtol=0, atol=1e-10)
    assert res.calor_fuente_acumulado == pytest.approx(
        q * np.prod((1.2, 1.0, 0.8)) * res.tiempos[-1], rel=1e-12
    )


def test_fuente_variable_en_el_tiempo_y_por_celda():
    malla = MallaVoxel.uniforme((4, 4), (0.25, 0.25), HORMIGON)
    q_campo = np.zeros((4, 4))
    q_campo[1:3, 1:3] = 2000.0
    solver = SolverVoxel(malla, _todas(malla, adiabatico()), fuente=lambda t: q_campo)
    res = solver.resolver(20.0, 0.5 * solver.dt_max(), 200)
    ganancia = res.energia[-1] - res.energia[0]
    assert ganancia == pytest.approx(res.calor_fuente_acumulado, rel=1e-12)
    # la zona con fuente queda más caliente que las esquinas
    assert res.T[1, 1] > res.T[0, 0]


def test_neumann_flujo_impuesto_entrega_q_por_area():
    malla = MallaVoxel.uniforme((10, 4, 3), (0.1, 0.25, 0.25), HORMIGON)
    q = 500.0  # W/m², entrando por x-
    bordes = _todas(malla, adiabatico())
    bordes["x-"] = neumann(q)
    solver = SolverVoxel(malla, bordes)
    res = solver.resolver(20.0, 0.9 * solver.dt_max(), 1000)
    area = 1.0 * 0.75
    esperado = q * area * res.tiempos[-1]
    assert res.energia[-1] - res.energia[0] == pytest.approx(esperado, rel=1e-12)
    assert res.calor_borde_acumulado["x-"] == pytest.approx(esperado, rel=1e-12)
    assert res.calor_borde_acumulado["x+"] == 0.0
    # el calor entra por x-: la temperatura decrece hacia x+
    perfil = res.T.mean(axis=(1, 2))
    assert np.all(np.diff(perfil) < 0.0)


def test_superficie_adiabatica_es_plano_de_simetria():
    """Media losa con un borde adiabático == losa completa (simetría)."""
    n = 10
    completa = MallaVoxel.uniforme((2 * n, 3), (0.05, 0.1), HORMIGON)
    b_comp = _todas(completa, adiabatico())
    b_comp["x-"] = robin(15.0, 10.0)
    b_comp["x+"] = robin(15.0, 10.0)
    media = MallaVoxel.uniforme((n, 3), (0.05, 0.1), HORMIGON)
    b_media = _todas(media, adiabatico())
    b_media["x-"] = robin(15.0, 10.0)  # x+ queda adiabático = plano medio
    s1, s2 = SolverVoxel(completa, b_comp), SolverVoxel(media, b_media)
    dt = 0.9 * min(s1.dt_max(), s2.dt_max())
    r1, r2 = s1.resolver(50.0, dt, 2000), s2.resolver(50.0, dt, 2000)
    np.testing.assert_allclose(r1.T[:n], r2.T, atol=1e-10)


def test_robin_coincide_con_serie_analitica_de_pared():
    L = 0.5  # semiespesor [m]
    n = 40
    h, T_i, T_inf = 15.0, 60.0, 20.0
    malla = MallaVoxel.uniforme((n, 3), (2 * L / n, 0.1), HORMIGON)
    bordes = _todas(malla, adiabatico())
    bordes["x-"] = robin(T_inf, h)
    bordes["x+"] = robin(T_inf, h)
    solver = SolverVoxel(malla, bordes)
    t_final = 2 * 86400.0
    n_pasos = int(np.ceil(t_final / (0.9 * solver.dt_max())))
    res = solver.resolver(T_i, t_final / n_pasos, n_pasos)
    x = malla.centros(0) - L
    exacta = solucion_pared_robin(x, t_final, L, HORMIGON.alpha, HORMIGON.k, h, T_i, T_inf)
    assert np.max(np.abs(res.T[:, 1] - exacta)) < 0.05


@pytest.mark.parametrize("T_inf, signo", [(20.0, -1.0), (80.0, 1.0)])
def test_robin_signo_del_flujo_y_balance(T_inf, signo):
    malla = MallaVoxel.uniforme((6, 6, 6), (0.1, 0.1, 0.1), HORMIGON)
    solver = SolverVoxel(malla, _todas(malla, robin(T_inf, 10.0, R_extra=0.05)))
    res = solver.resolver(50.0, 0.9 * solver.dt_max(), 300)
    total_borde = sum(res.calor_borde_acumulado.values())
    assert np.sign(total_borde) == signo
    assert res.energia[-1] - res.energia[0] == pytest.approx(total_borde, rel=1e-10)


def test_aislacion_reduce_perdidas():
    malla = MallaVoxel.uniforme((6, 6), (0.1, 0.1), HORMIGON)
    sin = SolverVoxel(malla, _todas(malla, robin(10.0, 15.0)))
    con = SolverVoxel(malla, _todas(malla, robin(10.0, 15.0, R_extra=0.05 / 0.04)))
    dt = 0.9 * min(sin.dt_max(), con.dt_max())
    r_sin, r_con = sin.resolver(50.0, dt, 500), con.resolver(50.0, dt, 500)
    assert r_con.T.min() > r_sin.T.min()


def test_dos_materiales_estado_estacionario_resistencias_en_serie():
    """Pared compuesta: el flujo estacionario es ΔT / (L1/k1 + L2/k2)."""
    a = PropiedadesTermicas(k=1.0, rho=1.0, cp=1.0)
    b = PropiedadesTermicas(k=4.0, rho=1.0, cp=1.0)
    n = 10
    material = np.zeros((2 * n, 2), dtype=int)
    material[n:, :] = 1
    malla = MallaVoxel.desde_materiales((0.1, 0.1), material, {0: a, 1: b})
    bordes = _todas(malla, adiabatico())
    bordes["x-"] = dirichlet(100.0)
    bordes["x+"] = dirichlet(0.0)
    solver = SolverVoxel(malla, bordes)
    res = solver.resolver(50.0, solver.dt_max(), 40000)
    q_exacto = 100.0 / (1.0 / a.k + 1.0 / b.k)  # W/m² con L1 = L2 = 1 m
    area = 0.2
    flujos = solver.calor_borde(res.T)
    assert flujos["x-"] == pytest.approx(q_exacto * area, rel=1e-6)
    assert flujos["x+"] == pytest.approx(-q_exacto * area, rel=1e-6)
    # perfil lineal a tramos, con la interfaz a 100 - q·L1/k1 = 20 °C
    x = malla.centros(0)
    T_exacta = np.where(x < 1.0, 100.0 - q_exacto * x / a.k, q_exacto * (2.0 - x) / b.k)
    np.testing.assert_allclose(res.T[:, 0], T_exacta, atol=1e-5)


def test_dt_max_coincide_con_fourier_en_malla_adiabatica():
    for dim, fo in ((2, 0.25), (3, 1.0 / 6.0)):
        dx = 0.05
        malla = MallaVoxel.uniforme((5,) * dim, (dx,) * dim, HORMIGON)
        solver = SolverVoxel(malla, _todas(malla, adiabatico()))
        assert solver.dt_max() == pytest.approx(fo * dx**2 / HORMIGON.alpha, rel=1e-12)


def test_dt_max_dirichlet_y_robin_son_mas_estrictos():
    dx = 0.05
    malla = MallaVoxel.uniforme((5, 5, 5), (dx,) * 3, HORMIGON)
    base = SolverVoxel(malla, _todas(malla, adiabatico())).dt_max()
    dir_ = SolverVoxel(malla, _todas(malla, dirichlet(20.0))).dt_max()
    rob_suave = SolverVoxel(malla, _todas(malla, robin(20.0, 10.0))).dt_max()
    rob = SolverVoxel(malla, _todas(malla, robin(20.0, 500.0))).dt_max()
    # esquina Dirichlet: sum G = 3 k A/dx + 3 · 2 k A/dx  ->  dx²/(9 alpha)
    assert dir_ == pytest.approx(dx**2 / (9.0 * HORMIGON.alpha), rel=1e-12)
    # con h bajo manda el voxel interior; con h alto manda la esquina convectiva
    assert rob_suave == pytest.approx(base, rel=1e-12)
    assert dir_ < rob < base


def test_paso_inestable_es_rechazado():
    malla = MallaVoxel.uniforme((5, 5), (0.1, 0.1), HORMIGON)
    solver = SolverVoxel(malla, _todas(malla, adiabatico()))
    with pytest.raises(ValueError, match="inestable"):
        solver.resolver(20.0, 1.01 * solver.dt_max(), 10)


def test_inestabilidad_empirica_y_principio_del_maximo():
    malla = MallaVoxel.uniforme((12, 12), (0.1, 0.1), HORMIGON)
    solver = SolverVoxel(malla, _todas(malla, dirichlet(20.0)))
    rng = np.random.default_rng(1)
    T_ini = 20.0 + 30.0 * rng.random(malla.forma)
    estable = solver.resolver(T_ini, solver.dt_max(), 300)
    assert estable.T.min() >= 20.0 - 1e-9 and estable.T.max() <= T_ini.max() + 1e-9
    # Fo=1/4 es el límite espectral de esta caja homogénea, aunque supera
    # el criterio suficiente de monotonía de la esquina. Aquí se supera
    # también el límite espectral (factor 1.2), provocando crecimiento.
    dt_fourier = 0.25 * 0.1**2 / HORMIGON.alpha
    inestable = solver.resolver(T_ini, dt_fourier * 1.2, 300, verificar_estabilidad=False)
    assert np.max(np.abs(inestable.T)) > 1e3


def test_validaciones_de_entrada():
    malla = MallaVoxel.uniforme((3, 3), (0.1, 0.1), HORMIGON)
    with pytest.raises(ValueError, match="exactamente una condición"):
        SolverVoxel(malla, {"x-": adiabatico()})
    with pytest.raises(ValueError):
        robin(20.0, 0.0)
    with pytest.raises(ValueError):
        MallaVoxel((3, 3), (0.1, -0.1), 1.0, 1.0, 1.0)
    with pytest.raises(ValueError, match="sin propiedades"):
        MallaVoxel.desde_materiales((0.1, 0.1), np.array([[0, 2]]), {0: HORMIGON})
