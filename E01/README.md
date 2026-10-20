# P02-MCOC — Grupo 1 — E01

Repositorio reproducible de la Entrega 01: modelo BIM/IFC de tres vertidas de
hormigón masivo, solver térmico 1D explícito y su verificación analítica.

> **Alcance de esta entrega.** El modelo IFC incluido es un **ejemplo
> didáctico**: tiene tres vertidas con geometría simple, identidad, unidades,
> estructura espacial y propiedades. **No** es la geometría oficial de la
> fundación; esa geometría debe ser entregada o validada por el profesor.
>
> El modelo IFC se **genera y lee con IfcOpenShell desde Python** y además se
> **abrió y editó manualmente en Bonsai** (Blender + Bonsai), completando el
> ciclo BIM pedido. Conviven dos archivos con roles distintos:
> el **generador** `src/mcplan/bim/build_model.py` conserva los valores
> originales de ejemplo (`Vertida_01` = 18 °C), mientras que el **IFC
> versionado** `geometry/fundacion_e01_ejemplo.ifc` es el resultado de la
> edición en Bonsai (`Vertida_01` = 19 °C). Ver
> [Ciclo BIM en Bonsai](#ciclo-bim-en-bonsai).

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

En PowerShell. `E01/` tiene su **propio** `pyproject.toml` (es el paquete
`mcplan` de esta entrega, con NumPy, Matplotlib e IfcOpenShell); no es el mismo
paquete que el de la raíz del repositorio, así que **no instales los dos en el
mismo entorno virtual**.

Opción A — desde la **raíz del repositorio clonado**:

```powershell
py -3.12 -m venv .venv-e01
.\.venv-e01\Scripts\python.exe -m pip install --upgrade pip
.\.venv-e01\Scripts\python.exe -m pip install -e "E01[dev]"
```

Opción B — desde **dentro de esta subcarpeta** (`P02-MCOC\E01`):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Los comandos de la sección **Uso** asumen que el directorio de trabajo actual
es `P02-MCOC\E01` y que el entorno virtual creado está en `.venv` dentro de
esa misma carpeta (Opción B). Si usas la Opción A, reemplaza
`.\.venv\Scripts\python.exe` por `..\.venv-e01\Scripts\python.exe`.

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
- 13 tests aprobados.

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

Los GUID se generan al construir el archivo. El IFC versionado en `geometry/`
es la referencia canónica de esta entrega y corresponde a la versión **editada
en Bonsai** (`Vertida_01` = 19 °C), no a la salida directa del generador.

## Reproducibilidad y alcance

- El solver térmico y la lectura/generación del IFC corren en Python, sin abrir
  Blender.
- El ciclo de **edición** del IFC sí se realizó en Blender con Bonsai; ver
  [Ciclo BIM en Bonsai](#ciclo-bim-en-bonsai).
- `scripts/make_ifc.py` regenera el IFC de ejemplo con los valores originales
  del generador, por lo que **sobrescribiría la edición de Bonsai**.
- Los tests verifican tanto la generación desde cero como el IFC versionado
  editado en Bonsai.

### Estado del avance

- **Hecho**: solver térmico 1D, modelo IFC de ejemplo generado y leído con
  IfcOpenShell, figura de verificación, tests reproducibles y **ciclo de
  edición del IFC en Bonsai** completado y verificado desde Python.
- **Hecho**: apertura y edición manual del IFC en **Blender 5.2.2 con
  Bonsai**, cambio de `TemperaturaColocacion_C` de `Vertida_01` de 18 °C a
  19 °C, guardado con **Save IFC Project** y verificación del resultado con
  `scripts/inspect_ifc.py`.
- **Pendiente real**: ninguna parte de E01 queda sin ejecutar. Lo que resta es
  de la entrega, no del ciclo: revisar visualmente la figura, ensayar la
  defensa oral y declarar el SHA final en Canvas.

## Ciclo BIM en Bonsai

El modelo versionado en `geometry/fundacion_e01_ejemplo.ifc` pasó por dos
etapas, y conviene no confundirlas:

1. **Generación en Python.** `src/mcplan/bim/build_model.py` construye el IFC4
   con IfcOpenShell y valores de ejemplo. Para `Vertida_01`,
   `TemperaturaColocacion_C = 18 °C`. Este generador **no se modificó**.
2. **Edición manual en Bonsai.** El integrante abrió el archivo en Blender
   5.2.2 con Bonsai, cambió `TemperaturaColocacion_C` de `Vertida_01` a
   **19 °C**, y lo guardó con **Save IFC Project**. El archivo guardado quedó
   con autoría `Bonsai 0.9.0-post1` en su encabezado.

El IFC versionado en `geometry/` es la versión **editada en Bonsai** (19 °C).
El generador conserva el valor original (18 °C), de modo que regenerar con
`scripts/make_ifc.py` produce 18 °C y **sobrescribiría** la edición. Por eso el
test `test_ifc_versionado_fue_editado_en_bonsai` fija esa diferencia.

Verificación del cambio desde Python:

```powershell
.\.venv\Scripts\python.exe scripts\inspect_ifc.py
```

Salida esperada: `Vertida_01` con `TemperaturaColocacion_C: 19`.

### Procedimiento seguido en Bonsai

1. Abrir Blender 5.2.2 y habilitar Bonsai.
2. Abrir `geometry/fundacion_e01_ejemplo.ifc`.
3. Seleccionar `Vertida_01` y editar `Pset_HormigonMasivo` →
   `TemperaturaColocacion_C`: 18 → 19 °C.
4. **Save IFC Project** sobre el mismo archivo.
5. Verificar con `scripts/inspect_ifc.py` que persiste el valor 19 °C.

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
