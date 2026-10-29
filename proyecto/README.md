# P02-MCOC — Grupo 1 — Capstone de hormigón masivo

## E06: dossier de verificación y BIM

Entrega del 30 de octubre: [dossier con matriz, convergencias y figuras](docs/e06.md).
Incluye el SHA evaluado, evidencia ejecutada, IFC versionado y simplificaciones.

## E04/E05: solver general y batería térmica

La preparación actual está en [docs/e04_e05.md](docs/e04_e05.md): comandos,
guía oral, fórmulas, mapa del código y límites del avance BIM.
El motor `thermal/voxel.py` resuelve 1D/2D/3D por volúmenes finitos
centrados en celdas, con Dirichlet, Neumann de flujo no nulo, Robin, fuentes
y propiedades por celda. Conserva el solver nodal 1D anterior; `solver_nd.py`
es un adaptador de compatibilidad que usa el mismo motor.

Desde la raíz del repositorio:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File proyecto/scripts/verificar_entregas.ps1
.\proyecto\.venv\Scripts\python.exe proyecto/scripts/verification_nd.py --dim 3 --figura proyecto/results/figures/verificacion_3d.png
```

La geometría IFC existente se conserva y hay voxelización paramétrica preliminar.
No hay todavía acoplamiento automático IFC-solver, hidratación realista ni clima real.

Proyecto continuo para diseñar, justificar y defender un **plan de vertidas de
hormigón masivo**, sustentado en simulación térmica y análisis de
confiabilidad. Este directorio (`proyecto/`) contiene el trabajo activo del
equipo: el modelo BIM/IFC de la fundación, el solver térmico 1D y las
herramientas de verificación. **Foundation es el único modelo activo.**

Los hitos del curso se documentan dentro del mismo proyecto, sin duplicar
código por entrega:

- **E00** (kickoff): paquete raíz del repositorio, CLI `mcplan` y
  `configs/site.yaml` — en la raíz, fuera de esta carpeta.
- **E01**: modelo IFC de la fundación + solver 1D + verificación analítica.
- **E02**: round-trip del IFC con edición manual en Bonsai, verificado con
  `ifc_state`/`ifc_diff`, más la demostración del solver con `--nx` y
  `--dt-scale`.
- **E04**: solver 2D/3D por balance de voxel (Dirichlet, Neumann con flujo,
  Robin con aislación, fuente volumétrica, dos materiales, dt_max = min C/ΣG),
  verificación (convergencia de orden 2, energía, serie de Robin, pared
  compuesta) y voxelización de la fundación. Ver `docs/guia_e04.md`.

> El estado de entrega/evaluación de E01 no se afirma aquí; los hitos son
> referencia organizativa, no constancia de evaluación.

## Integrantes

- Juan Pablo Cáceres
- Magdalena Fernández
- Mauricio Lenz

## Contenido

```
proyecto/
├─ src/mcplan/
│  ├─ thermal/
│  │  ├─ boundaries.py     # PropiedadesTermicas y CondicionBorde
│  │  ├─ solver1d.py       # FTCS 1D, estabilidad, energía
│  │  ├─ voxel.py          # E04: solver 2D/3D por balance de voxel
│  │  └─ analytics.py      # soluciones exactas (sinusoidal 1D/2D/3D, pared Robin)
│  └─ bim/
│     ├─ foundation.py     # generador de la fundación octagonal (5 vertidas)
│     ├─ ifc_io.py         # lectura de vertidas (selección semántica)
│     └─ voxelizacion.py   # E04: fundación -> grilla con vertida_id
├─ scripts/
│  ├─ make_foundation.py   # genera foundation.ifc (protegido con --forzar)
│  ├─ inspect_ifc.py       # inspección unificada: psets + bbox + volúmenes
│  ├─ ifc_state.py         # snapshot JSON por GlobalId
│  ├─ ifc_diff.py          # comparación antes/después por GlobalId
│  ├─ verification_1d.py   # figura numérica vs. analítica (--nx, --dt-scale)
│  ├─ verification_2d_3d.py # E04: convergencia 2D/3D, bordes, estabilidad
│  └─ voxelize_foundation.py # E04: voxelización y error de volumen
├─ tests/
│  ├─ test_solver1d.py     # física del solver
│  ├─ test_foundation.py   # modelo IFC y selección semántica
│  ├─ test_ifc_diff.py     # herramienta snapshot/diff
│  ├─ test_voxel.py        # E04: 2D/3D, Dirichlet/Neumann/Robin, fuente, 2 materiales, estabilidad
│  └─ test_voxelizacion.py # E04: voxelización de la fundación
├─ geometry/foundation.ifc # modelo activo (editado en Bonsai en el hito E02)
├─ results/figures/        # figura de verificación (versionada)
└─ docs/
   ├─ guia_estudio.md      # guía activa para la defensa oral
   └─ evidencia_e02/       # evidencia real del round-trip (post-edición)
```

## Requisitos

- Python 3.10–3.13 (probado con 3.12 en Windows).
- Dependencias: `numpy`, `matplotlib`, `ifcopenshell`; `pytest` para tests.

## Instalación (Windows PowerShell)

Este directorio tiene su **propio** `pyproject.toml` (paquete `mcplan` con
NumPy, Matplotlib e IfcOpenShell). La raíz del repositorio tiene **otro**
paquete también llamado `mcplan` (solo PyYAML, con la CLI). **No se instalan
los dos en el mismo entorno virtual.**

Entorno del proyecto (este directorio):

```powershell
py -3.12 -m venv proyecto\.venv
.\proyecto\.venv\Scripts\python.exe -m pip install --upgrade pip
.\proyecto\.venv\Scripts\python.exe -m pip install -e "proyecto[dev]"
```

Entorno de la raíz (E00, solo si se necesita la CLI):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Los comandos siguientes asumen que el directorio de trabajo es `proyecto/`
y que la venv está en `proyecto\.venv`.

## Uso

```powershell
# Tests
.\.venv\Scripts\python.exe -m pytest -q

# Ayuda de cualquier script (los scripts usan argparse: flag --help)
.\.venv\Scripts\python.exe scripts\make_foundation.py --help
.\.venv\Scripts\python.exe scripts\inspect_ifc.py --help
.\.venv\Scripts\python.exe scripts\verification_1d.py --help
.\.venv\Scripts\python.exe scripts\ifc_state.py --help
.\.venv\Scripts\python.exe scripts\ifc_diff.py --help

# Inspección unificada del IFC versionado (5 vertidas, psets, bbox, volúmenes)
.\.venv\Scripts\python.exe scripts\inspect_ifc.py

# Verificación 1D (caso base y variaciones de malla y paso)
# Sin --salida, el caso base regenera la figura versionada
# results/figures/verificacion_1d.png. Las variaciones usan una ruta ignorada
# por git (results/* está ignorado salvo figures/*.png) para no pisarla.
.\.venv\Scripts\python.exe scripts\verification_1d.py
.\.venv\Scripts\python.exe scripts\verification_1d.py --nx 161 --salida results\tmp\verif_nx161.png
.\.venv\Scripts\python.exe scripts\verification_1d.py --dt-scale 0.80 --salida results\tmp\verif_dt080.png
.\.venv\Scripts\python.exe scripts\verification_1d.py --dt-scale 1.20   # rechazado (exit 3), no escribe figura

# Snapshot y comparación por GlobalId
.\.venv\Scripts\python.exe scripts\ifc_state.py geometry\foundation.ifc
.\.venv\Scripts\python.exe scripts\ifc_state.py geometry\foundation.ifc --salida docs\evidencia_e02\roundtrip_antes.json
.\.venv\Scripts\python.exe scripts\ifc_diff.py docs\evidencia_e02\roundtrip_antes.json geometry\foundation.ifc
```

> **No regeneres `geometry/foundation.ifc` sin `--forzar`.** El archivo
> versionado puede contener la edición manual de Bonsai del round-trip
> E02; regenerarlo la borraría. `make_foundation.py` se niega a
> sobrescribirlo salvo que se pida explícitamente.

## Las dos demostraciones de E02 (por separado)

El hito E02 se demuestra en **dos bloques independientes**; ninguno depende
del otro, y ninguno exige un caso físico 1D de la fundación:

**Bloque A — flujo foundation / Bonsai / IFC / Python.** El modelo
`geometry/foundation.ifc` se abre y edita en Bonsai (interfaz manual), y el
resultado se verifica con Python (`ifc_state` + `ifc_diff`, por GlobalId).
La edición y su verificación se documentan con evidencia real en
`docs/evidencia_e02/`. El acoplamiento automático IFC → solver
(voxelización) es desarrollo futuro del capstone, no requisito de E02.

**Bloque B — verificación del solver 1D.** El caso sinusoidal se compara
contra su solución analítica exacta; `--nx` y `--dt-scale` permiten
demostrar la dependencia de Δx y Δt (valores efectivos impresos en cada
corrida). El solver rechaza con una excepción los pasos inestables; la
demostración de ese rechazo es el mensaje y el código de salida, no una
gráfica de inestabilidad.

## Solver térmico 1D

Ecuación (propiedades constantes, fuente volumétrica uniforme):

```text
rho·cp·∂T/∂t = k·∂²T/∂x² + Qdot
```

Discretización FTCS con `r = alpha·dt/dx²`, `alpha = k/(rho·cp)`.
Condiciones de borde: Dirichlet (valor impuesto), Neumann (flujo normal saliente,
incluido cero adiabático) y Robin (balance sobre medio volumen de control).

Estabilidad — dos restricciones distintas:

| Caso | Restricción |
|---|---|
| Difusión pura / Dirichlet | `r = alpha·dt/dx² ≤ 1/2`, es decir `dt ≤ dx²/(2·alpha)` |
| Robin (borde con convección) | `dt ≤ rho·cp·dx² / (2k + 2h·dx)` — balance de conducción + convección del medio volumen de borde; puede ser más estricta que la anterior |

`limite_estabilidad` devuelve el mínimo aplicable. `resolver_1d` **lanza
`ValueError`** si `dt` lo supera, antes de integrar: no produce una
solución oscilante que parezca física.

## Verificación (Bloque B)

Caso sinusoidal (sin cambios respecto de la referencia del curso):

- Barra `L = 1 m`, Dirichlet `T0 = 20 °C` en ambos extremos,
  perfil inicial `T(x,0) = 20 + 50·sin(pi·x/L)` °C, difusión pura
  (`Qdot = 0`), `t = 24 h`.
- Hormigón: `k = 2.22 W/(m·K)`, `rho = 2400 kg/m³`, `cp = 970 J/(kg·K)`
  (`alpha ≈ 9.54e-7 m²/s`). Parámetros de la guía del curso (§31; Ju & Lei,
  2019). No se ajustan condiciones térmicas por la migración del proyecto.
- Solución exacta: `T(x,t) = T0 + A·sin(pi·x/L)·exp(-alpha·(pi/L)²·t)`.

El script imprime siempre los **valores efectivos** `dx`, `dt_max`,
`dt` (tras redondear el número de pasos a `n_pasos = ceil(t/dt)`), `r` y
`n_pasos`, además del error `L_inf`. Con `--dt-scale > 1` el paso supera
`dt_max` y el script reporta el rechazo y termina con código de salida `3`.

La relación entre `dt` y el error no se afirma monótona: la guía registra
solo lo observado en las corridas ejecutadas.

## Modelo IFC (`geometry/foundation.ifc`)

- Esquema **IFC4**, generado con IfcOpenShell 0.9, según la geometría
  docente de la guía Bonsai del capstone (fundación eólica inspirada en
  Ju & Lei, 2019).
- Geometría: octágono regular de 18 m entre caras opuestas; espesores de
  borde 1.10 m con transición en dos troncos octagonales; pedestal central
  de Ø7 m × 1.0 m (base z = 3.30 m, tope z = 4.30 m).
- Cinco `IfcFooting` (`Vertida_01` .. `Vertida_05`) con property set
  **`UANDES_HormigonMasivo`** (el prefijo `Pset_` está reservado por
  buildingSMART). Campos: `VertidaID`, `TipoHormigon`, `Inicio_h`,
  `TemperaturaColocacion_C`, `Moldaje`, `Aislacion`, `RetiroMoldaje_h`.
- Unidades SI con temperatura en `DEGREE_CELSIUS`.

Volúmenes (malla vs. analítico vs. tabla de la guía, sección 19):

| Vertida | Volumen [m³] |
|---|---:|
| Vertida_01 | 147.63 |
| Vertida_02 | 147.63 |
| Vertida_03 | 214.22 |
| Vertida_04 | 88.92 |
| Vertida_05 | 38.37* |
| **Total** | **636.77** |

\* El pedestal se modela como polígono regular de 48 lados; la guía reporta
38.48 (cilindro exacto), diferencia dentro de la tolerancia del 1 % que
aplica `inspect_ifc.py`.

**Selección de vertidas (lectores Python):** un producto es vertida si lleva
el pset `UANDES_HormigonMasivo` con `VertidaID` (criterio semántico). La
clase `IfcFooting` se verifica y su ausencia se reporta como advertencia sin
descartar el objeto (Bonsai puede convertir la clase al editar). El nombre
solo se usa como etiqueta, nunca como filtro.

## Round-trip con Bonsai (Bloque A)

Flujo documentado (la edición es manual; la verificación, con Python):

1. `ifc_state.py geometry/foundation.ifc --salida docs/evidencia_e02/roundtrip_antes.json`
2. En Bonsai: **File > Open IFC Project** sobre `geometry/foundation.ifc`,
   identificar `Vertida_01` por su GUID (aparece en el snapshot), editar
   `UANDES_HormigonMasivo` → `TemperaturaColocacion_C`: **18 → 19 °C**
   (modificación de demostración; el valor inicial 18 °C está verificado en
   el archivo generado), y **Save IFC Project**.
3. `ifc_state.py` de nuevo (o directamente) y
   `ifc_diff.py docs/evidencia_e02/roundtrip_antes.json geometry/foundation.ifc`
4. Revisar el reporte. La modificación esperada es la de la temperatura en
   ese GUID, pero **el guardado en Bonsai puede introducir cambios
   adicionales** (metadatos, unidades, orden, representación): el diff los
   muestra y se documentan; no se asume de antemano un único cambio.

**Tolerancias de la comparación geométrica.** `ifc_diff` compara bbox
(coordenadas, metros) y volumen (m³) con `|a−b| ≤ tol_abs + tol_rel·max(|a|,|b|)`,
por defecto `tol_abs = 1e-4` (0,1 mm; 1e-4 m³) y `tol_rel = 1e-6`, ajustables
por CLI. Estas tolerancias absorben ruido numérico de re-triangulación; no
definen qué es "cambio de diseño". **Alcance limitado (documentado):** bbox y
volumen no detectan todo cambio geométrico — p. ej. rotar un sólido simétrico
conservando envolvente y volumen. Las propiedades del pset se comparan de
forma exacta e independiente.

Códigos de salida de `ifc_diff`: `0` sin diferencias, `1` con diferencias,
`2` error.

No existe ningún test que afirme que un valor fijo demuestra una edición en
Bonsai: la evidencia del round-trip son los JSON reales de
`docs/evidencia_e02/` y el diff correspondiente.

## Reproducibilidad y alcance

- El solver y la lectura/generación del IFC corren en Python, sin Blender.
- La edición del IFC se hace manualmente en Blender + Bonsai y se verifica
  con las herramientas de este directorio.
- El IFC versionado es la referencia canónica; su SHA256 se registró antes
  y después de la reorganización del repositorio (sin regeneración).

## Atribución

El esquema FTCS y la estructura de los scripts docentes de difusión 1D del
curso (verificados y corregidos aquí: comparación con la solución exacta,
criterio de estabilidad Robin y discretización de la fuente) son la base del
módulo `thermal`. La geometría de la fundación sigue
`GUIA_BONSAI_FUNDACION.md` del curso (Ju & Lei, 2019 como referencia
física).

## Documentación de estudio

Guía activa: [`docs/guia_estudio.md`](docs/guia_estudio.md).
Evidencia del round-trip: [`docs/evidencia_e02/`](docs/evidencia_e02/).
