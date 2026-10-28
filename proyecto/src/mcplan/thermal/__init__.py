"""Solver nodal histórico y solver de voxels 1D/2D/3D del equipo."""
from .analytics import solucion_pared_robin, solucion_sinusoidal, solucion_sinusoidal_nd
from .boundaries import CondicionBorde, PropiedadesTermicas
from .solver1d import energia_1d, limite_estabilidad, resolver_1d
from .voxel import (BordeCara, MallaVoxel, ResultadoVoxel, SolverVoxel,
                    adiabatico, dirichlet, neumann, robin)
from .solver_nd import MallaTermica, ResultadoND

__all__ = ["BordeCara", "CondicionBorde", "MallaVoxel", "PropiedadesTermicas",
           "ResultadoVoxel", "SolverVoxel", "adiabatico", "dirichlet", "energia_1d",
           "limite_estabilidad", "neumann", "resolver_1d", "robin",
           "solucion_pared_robin", "solucion_sinusoidal", "solucion_sinusoidal_nd",
           "MallaTermica", "ResultadoND"]
