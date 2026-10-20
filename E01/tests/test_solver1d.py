"""Tests físicos del solver térmico 1D (E01)."""

from __future__ import annotations

import numpy as np
import pytest

from mcplan.thermal import (
    CondicionBorde,
    PropiedadesTermicas,
    energia_1d,
    limite_estabilidad,
    resolver_1d,
    solucion_sinusoidal,
)

PROPS = PropiedadesTermicas(k=2.22, rho=2400.0, cp=970.0)
L = 1.0
T0 = 20.0
A = 50.0


def _caso_sinusoidal(nx: int, t_final: float, r_objetivo: float = 0.40):
    x = np.linspace(0.0, L, nx)
    dx = x[1] - x[0]
    dt_objetivo = r_objetivo * dx**2 / PROPS.alpha
    n_pasos = int(np.ceil(t_final / dt_objetivo))
    dt = t_final / n_pasos

    T_inicial = T0 + A * np.sin(np.pi * x / L)
    T_inicial[0] = T0
    T_inicial[-1] = T0
    borde = CondicionBorde("dirichlet", valor=T0)
    resultado = resolver_1d(
        T_inicial, PROPS, dx, dt, n_pasos, borde, borde
    )
    exacta = solucion_sinusoidal(x, t_final, PROPS.alpha, T0, A, L)
    return np.max(np.abs(resultado.T - exacta)), x, dx, dt, resultado


def test_decaimiento_sinusoidal_frente_a_solucion_exacta():
    error, x, dx, dt, resultado = _caso_sinusoidal(101, 6.0 * 3600.0)
    exacta = solucion_sinusoidal(x, 6.0 * 3600.0, PROPS.alpha, T0, A, L)

    assert np.allclose(resultado.T[0], T0, atol=1e-12)
    assert np.allclose(resultado.T[-1], T0, atol=1e-12)
    assert np.max(np.abs(resultado.T - T0)) < A
    assert error < 2.0e-3, f"Error L_inf demasiado alto: {error:.3e} °C"


def test_convergencia_espacial_segundo_orden():
    resoluciones = [21, 41, 81, 161]
    errores = []
    dxs = []
    for nx in resoluciones:
        error, _, dx, _, _ = _caso_sinusoidal(nx, 12.0 * 3600.0, 0.35)
        errores.append(error)
        dxs.append(dx)

    errores = np.array(errores)
    dxs = np.array(dxs)
    pendiente = np.polyfit(np.log(dxs), np.log(errores), 1)[0]

    assert np.all(np.diff(errores) < 0.0), "El error debe bajar al refinar."
    assert 1.7 < pendiente < 2.3, f"Pendiente de convergencia inesperada: {pendiente:.3f}"


def test_temperatura_uniforme_compatible_con_dirichlet():
    nx = 41
    x = np.linspace(0.0, L, nx)
    dx = x[1] - x[0]
    borde = CondicionBorde("dirichlet", valor=25.0)
    dt = 0.4 * limite_estabilidad(PROPS, dx, borde, borde)

    resultado = resolver_1d(
        np.full(nx, 25.0), PROPS, dx, dt, 100, borde, borde
    )
    assert np.allclose(resultado.T, 25.0, atol=1e-12)


def test_rechaza_paso_temporal_inestable():
    props = PropiedadesTermicas(k=1.0, rho=1.0, cp=1.0)
    borde = CondicionBorde("dirichlet", valor=0.0)
    dx = 0.1
    dt_max = dx**2 / (2.0 * props.alpha)
    with pytest.raises(ValueError, match="inestable"):
        resolver_1d(
            np.zeros(11), props, dx, dt_max * 1.2, 10, borde, borde
        )


def test_rechaza_parametros_invalidos():
    borde = CondicionBorde("dirichlet", valor=0.0)
    with pytest.raises(ValueError):
        resolver_1d(np.zeros(11), PROPS, 0.0, 1.0, 1, borde, borde)
    with pytest.raises(ValueError):
        resolver_1d(np.zeros(11), PROPS, 0.1, 0.0, 1, borde, borde)
    with pytest.raises(ValueError):
        resolver_1d(np.zeros(2), PROPS, 0.1, 0.1, 1, borde, borde)
    with pytest.raises(ValueError):
        PropiedadesTermicas(k=0.0, rho=2400.0, cp=970.0)
    with pytest.raises(ValueError):
        CondicionBorde("neumann", valor=10.0)


def test_conservacion_energia_ambos_bordes_adiabaticos():
    nx = 101
    x = np.linspace(0.0, L, nx)
    dx = x[1] - x[0]
    borde = CondicionBorde("neumann")
    dt = 0.4 * limite_estabilidad(PROPS, dx, borde, borde)

    T_inicial = 20.0 + 30.0 * np.exp(-((x - 0.35) / 0.12) ** 2)
    E0 = energia_1d(T_inicial, PROPS, dx)
    resultado = resolver_1d(T_inicial, PROPS, dx, dt, 500, borde, borde)
    E1 = energia_1d(resultado.T, PROPS, dx)

    assert abs((E1 - E0) / E0) < 1e-9


def test_fuente_uniforme_adiabatica_aumento_lineal():
    nx = 51
    dx = L / (nx - 1)
    borde = CondicionBorde("neumann")
    dt = 0.4 * limite_estabilidad(PROPS, dx, borde, borde)
    n_pasos = 10
    fuente = 1000.0  # W/m³

    resultado = resolver_1d(
        np.full(nx, 20.0), PROPS, dx, dt, n_pasos, borde, borde, fuente=fuente
    )
    t_final = n_pasos * dt
    esperado = 20.0 + fuente * t_final / (PROPS.rho * PROPS.cp)

    assert np.allclose(resultado.T, esperado, atol=1e-9)

    E0 = energia_1d(np.full(nx, 20.0), PROPS, dx)
    E1 = energia_1d(resultado.T, PROPS, dx)
    esperado_energia = fuente * L * t_final
    assert abs((E1 - E0) - esperado_energia) / esperado_energia < 1e-9


def test_robin_enfria_superficie_mas_que_centro():
    nx = 81
    dx = L / (nx - 1)
    h = 12.0
    borde = CondicionBorde("robin", valor=20.0, h=h)
    dt = 0.4 * limite_estabilidad(PROPS, dx, borde, borde)

    resultado = resolver_1d(
        np.full(nx, 70.0), PROPS, dx, dt, 200, borde, borde
    )

    superficie = resultado.T[0]
    centro = resultado.T[nx // 2]

    assert superficie < 68.0, "La superficie debería enfriarse."
    assert centro < 70.0, "El centro también debería enfriarse."
    assert superficie < centro, "La superficie debe estar más fría que el centro."


def test_robin_rechaza_paso_que_viola_su_limite():
    nx = 81
    dx = L / (nx - 1)
    h = 12.0
    borde = CondicionBorde("robin", valor=20.0, h=h)
    dt_max = limite_estabilidad(PROPS, dx, borde, borde)
    limite_difusion = dx**2 / (2.0 * PROPS.alpha)

    assert dt_max < limite_difusion, "Robin debe imponer un límite más estricto."
    with pytest.raises(ValueError, match="inestable"):
        resolver_1d(
            np.full(nx, 70.0), PROPS, dx, dt_max * 1.05, 10, borde, borde
        )


def test_rechaza_propiedades_y_bordes_no_finitos():
    for valor in (np.nan, np.inf, -np.inf):
        for campo in ("k", "rho", "cp"):
            parametros = dict(k=2.22, rho=2400.0, cp=970.0)
            parametros[campo] = valor
            with pytest.raises(ValueError):
                PropiedadesTermicas(**parametros)
        for tipo in ("dirichlet", "neumann", "robin"):
            with pytest.raises(ValueError, match="finitos"):
                CondicionBorde(tipo, valor=valor)
        with pytest.raises(ValueError, match="finitos"):
            CondicionBorde("robin", valor=20.0, h=valor)
        borde = CondicionBorde("neumann")
        with pytest.raises(ValueError):
            limite_estabilidad(PROPS, valor, borde, borde)


def test_rechaza_inicial_incompatible_con_dirichlet_antes_de_avanzar():
    borde = CondicionBorde("dirichlet", valor=20.0)
    for inicial in ([100.0, 20.0, 20.0], [20.0, 20.0, 100.0]):
        for pasos in (0, 1):
            with pytest.raises(ValueError, match="incompatible"):
                resolver_1d(np.array(inicial), PROPS, 0.1, 1.0, pasos, borde, borde)


def test_dirichlet_con_fuente_mantiene_extremos_e_incrementa_interior():
    borde = CondicionBorde("dirichlet", valor=20.0)
    inicial = np.full(5, 20.0)
    fuente = 1000.0
    resultado = resolver_1d(
        inicial, PROPS, 0.1, 1.0, 1, borde, borde,
        fuente=fuente, pasos_guardado={0, 1},
    )
    esperado = inicial.copy()
    esperado[1:-1] += fuente / (PROPS.rho * PROPS.cp)
    np.testing.assert_allclose(resultado.T, esperado, rtol=0.0, atol=1e-12)
    np.testing.assert_array_equal(resultado.instantaneas[0], inicial)
