# P02-MCOC — Grupo 1 — E01

Repositorio reproducible de la Entrega 01: modelo BIM/IFC de tres vertidas de
hormigón masivo, solver térmico 1D explícito y su verificación analítica.

> **Alcance de esta entrega.** El modelo IFC incluido es un **ejemplo
> didáctico**: tiene tres vertidas con geometría simple, identidad, unidades,
> estructura espacial y propiedades. **No** es la geometría oficial de la
> fundación; esa geometría debe ser entregada o validada por el profesor.
>
> La generación y lectura del IFC se hacen con **IfcOpenShell desde Python**.
> El ciclo de edición en la interfaz de **Bonsai no se ejecutó** en este
> entorno (Blender/Bonsai no está instalado). Las instrucciones para hacerlo
> están en [`docs/guia_estudio_e01.md`](docs/guia_estudio_e01.md) y quedan
> como paso pendiente con evidencia.

## Integrantes

- Juan Pablo Cáceres
- Magdalena Fernández
- Mauricio Lenz

## Contenido

```
E01/
├─ src/mcplan/
│  ├─ thermal/
│  │  ├─ boundaries.py    # PropiedadesTermicas y CondicionBorde
│  │  ├─ solver1d.py      # FTCS 1D, estabilidad, energía
│  │  └─ analytics.py     # solución exacta sinusoidal
│  └─ bim/
│     ├─ build_model.py   # construcción IFC4 con IfcOpenShell
│     └─ ifc_io.py        # lectura de vertidas y propiedades
├─ scripts/
│  ├─ make_ifc.py         # genera el IFC
│  ├─ inspect_ifc.py      # lista nombres, GUIDs, psets y unidades
│  └─ verification_1d.py  # figura numérica vs. analítica
├─ tests/
│  ├─ test_solver1d.py
│  └─ test_ifc.py
├─ geometry/
│  └─ fundacion_e01_ejemplo.ifc
├─ results/figures/
│  └─ verificacion_1d.png
└─ docs/guia_estudio_e01.md
```

## Requisitos

- Python 3.10–3.13 (probado con 3.12.10 en Windows).
- Dependencias: `numpy`, `matplotlib`, `ifcopenshell` y `pytest` (desarrollo).

## Instalación

En PowerShell, desde la raíz del repositorio:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## Uso

```powershell
# 1) Generar el IFC de ejemplo
.\.venv\Scripts\python.exe scripts\make_ifc.py

# 2) Inspeccionar el IFC (nombres, clases, GUIDs, propiedades, unidades)
.\.venv\Scripts\python.exe scripts\inspect_ifc.py

# 3) Generar la figura de verificación 1D
.\.venv\Scripts\python.exe scripts\verification_1d.py

# 4) Ejecutar los tests
.\.venv\Scripts\python.exe -m pytest -q
```

Salidas esperadas:

- `geometry/fundacion_e01_ejemplo.ifc` (IFC4).
- `results/figures/verificacion_1d.png`.
- 12 tests aprobados.

## Solver térmico 1D

Se resuelve, con propiedades constantes y fuente volumétrica uniforme:

```text
rho·cp·∂T/∂t = k·∂²T/∂x² + Qdot
```

Discretización FTCS:

```text
T_i^{n+1} = T_i^n + r·(T_{i+1}^n - 2T_i^n + T_{i-1}^n)
            + dt·Qdot/(rho·cp),
r = alpha·dt/dx²,  alpha = k/(rho·cp).
```

Condiciones de borde:

- **Dirichlet**: temperatura impuesta.
- **Neumann**: solo adiabática (`q'' = 0`), con nodo fantasma.
- **Robin**: balance sobre medio volumen de control,
  `q'' = h·(T_ambiente - T_superficie)`.

Estabilidad:

```text
dt <= dx²/(2·alpha)                      (difusión)
dt <= rho·cp·dx²/(2k + 2h·dx)            (Robin, por borde)
```

El solver valida entradas y **rechaza** un `dt` inestable con `ValueError`; no
depende de Blender ni de `bpy`.

## Verificación

Caso no trivial: barra de 1 m, hormigón `k=2.22 W/(m·K)`, `rho=2400 kg/m³`,
`cp=970 J/(kg·K)`, perfil inicial `T0 + A·sin(pi·x/L)`, Dirichlet `T0` en ambos
extremos. Solución exacta:

```text
T(x,t) = T0 + A·sin(pi·x/L)·exp(-alpha·(pi/L)²·t).
```

Resultados de la corrida versionada (`nx=81`, 24 h):

- `dx = 0.0125 m`, `dt = 32.76 s`, `r = 0.200`.
- Error `L_inf` final: **4.63e-04 °C**.
- Convergencia espacial medida con `dt ∝ dx²`: pendiente **1.985** (esperado 2).

Los tests cubren además:

- conservación de energía con ambos bordes adiabáticos;
- aumento uniforme `T0 + Qdot·t/(rho·cp)` con fuente uniforme;
- enfriamiento Robin (superficie más fría que el centro);
- rechazo de `dt` inestable, incluido el límite más estricto de Robin;
- temperatura uniforme compatible con Dirichlet;
- validación de parámetros.

## Modelo IFC

- Esquema **IFC4**, generado con IfcOpenShell 0.9.
- Unidades SI: metro, metro cuadrado, metro cúbico y **grado Celsius**
  (`IfcSIUnit` con `Name=DEGREE_CELSIUS`).
- Estructura espacial: `IfcProject` → `IfcSite` → `IfcBuilding` →
  `IfcBuildingStorey` → 3 `IfcSlab`.
- Vertidas: `Vertida_01`, `Vertida_02`, `Vertida_03`, cada una con GUID propio
  y geometría de ejemplo de 4 × 3 × 1 m.
- Property set `Pset_HormigonMasivo`:
  `VertidaID`, `TipoHormigon`, `InicioPlanificado`,
  `TemperaturaColocacion_C`, `Moldaje`, `Aislacion`, `RetiroMoldaje_h`.

Los GUID se generan al construir el archivo; el IFC versionado en `geometry/`
es la referencia canónica de esta entrega.

## Reproducibilidad y alcance

- Todo el flujo numérico y BIM corre en Python, sin abrir Blender.
- El IFC se puede regenerar con `scripts/make_ifc.py`.
- Los tests verifican el IFC versionado y la generación desde cero.

### Estado del avance

- **Hecho**: solver térmico 1D, modelo IFC de ejemplo generado y leído con
  IfcOpenShell, figura de verificación y tests reproducibles.
- **Pendiente declarado**: **abrir y editar el IFC en Bonsai** (interfaz
  gráfica de Blender) y **verificar el cambio desde Python** con
  `scripts/inspect_ifc.py` (o `mcplan.bim.leer_modelo`). El ciclo en Bonsai
  **no se ejecutó** en este entorno porque Blender/Bonsai no está instalado.
- El procedimiento manual y el checklist están en la guía de estudio
  [`docs/guia_estudio_e01.md`](docs/guia_estudio_e01.md).

## Atribución

El esquema FTCS y la estructura de los scripts docentes de difusión 1D
(`01_1d_dirichlet_verification.py`, `03_1d_neumann.py`, `04_1d_robin.py`,
`05_calor_interno.py`) provienen del material del curso. En este repositorio se
reorganizaron como paquete, se corrigió el tratamiento de la fuente
volumétrica y se agregaron validaciones, tests y verificación reproducible.

## Documentación de estudio

La guía [`docs/guia_estudio_e01.md`](docs/guia_estudio_e01.md) contiene la
derivación, las decisiones de implementación, preguntas probables de la
revisión oral y el procedimiento manual para Bonsai.
