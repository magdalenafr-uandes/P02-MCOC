# Guía de estudio — Capstone (fundación, solver 1D, IFC)

> Para E04/E05, consultar [e04_e05.md](e04_e05.md): solver general 2D/3D,
> Neumann no nulo, balances, estabilidad, dos materiales y comandos de tests.
> Las secciones siguientes conservan el contexto de las entregas E01/E02.

Guía activa para la defensa oral del trabajo del equipo. Explica el modelo
`foundation`, el solver y las herramientas actuales de `proyecto/`. Todo es
reproducible con los comandos del `README.md`. El histórico de entregas
anteriores está en Git; aquí solo se documenta el trabajo vigente.

## 1. Qué es el proyecto y qué son los hitos

El equipo desarrolla un **plan de vertidas de hormigón masivo**. El código
vive una sola vez, en `proyecto/`. **E01** y **E02** son hitos del mismo
proyecto, no copias por entrega:

- **E01**: modelo IFC de la fundación (`geometry/foundation.ifc`), lectores
  Python con IfcOpenShell, solver térmico 1D explícito y su verificación
  analítica.
- **E02**: round-trip del IFC —edición manual en Bonsai, verificada con
  `ifc_state`/`ifc_diff` por GlobalId— y demostración del solver con
  `--nx` y `--dt-scale`. Son dos bloques **independientes** (ver §5 y §8).

El estado de entrega/evaluación de E01 no se afirma: no forma parte de lo
verificable desde el repositorio.

## 2. Ecuación y discretización

Ecuación de difusión térmica con fuente volumétrica uniforme:

```text
rho·cp·∂T/∂t = k·∂²T/∂x² + Qdot
```

Con `alpha = k/(rho·cp)`:

```text
∂T/∂t = alpha·∂²T/∂x² + Qdot/(rho·cp)
```

FTCS (Forward-Time, Centered-Space):

```text
T_i^{n+1} = T_i^n + r·(T_{i+1}^n - 2T_i^n + T_{i-1}^n)
            + dt·Qdot/(rho·cp)
r = alpha·dt/dx²
```

- El término de difusión es explícito y centrado: error espacial `O(dx²)`.
- El avance temporal es de Euler explícito: error temporal `O(dt)`.
- Si se refina con `dt ∝ dx²`, el error total escala como `dx²` (segundo
  orden); el test `test_convergencia_espacial_segundo_orden` lo mide.
- La fuente se suma una vez por paso como `dt·Qdot/(rho·cp)` en nodos
  interiores y bordes Neumann/Robin. En Dirichlet el extremo mantiene la
  temperatura impuesta. (Corrección respecto del script docente
  `05_calor_interno.py`, que sumaba `Q0` dentro de `r·(...)` con unidades
  incorrectas para una fuente en `W/m³`.)

## 3. Condiciones de borde

### Dirichlet

Se impone el valor en el nodo extremo: `T_0 = T_borde`. El solver valida
que la condición inicial sea compatible (tolerancia 1e-10 °C) **antes** de
integrar, incluso con cero pasos.

### Neumann adiabática

Solo `q'' = 0`, con nodo fantasma `T_{-1} = T_1`:

```text
T_0^{n+1} = T_0^n + 2r·(T_1^n - T_0^n) + incremento_fuente
```

El factor `2r` aparece porque el volumen de control del borde tiene ancho
`dx/2`. La energía discreta usa pesos `[0.5, 1, …, 1, 0.5]` (medios
volúmenes).

### Robin

Balance sobre medio volumen de control:

```text
rho·cp·(dx/2)·dT_0/dt = k·(T_1 - T_0)/dx + h·(T_amb - T_0)
```

```text
dT_0/dt = 2k/(rho·cp·dx²)·(T_1 - T_0) + 2h/(rho·cp·dx)·(T_amb - T_0)
```

`h` [W/(m²·K)], `T_amb` en °C.

## 4. Estabilidad — dos restricciones distintas

**Difusión pura / Dirichlet.** El coeficiente de `T_i^n` exige
`r = alpha·dt/dx² ≤ 1/2`, es decir:

```text
dt ≤ dt_max = dx²/(2·alpha)
```

**Robin.** El coeficiente del nodo de borde en el balance de medio volumen
(incluye conducción interna **y** convección con el ambiente) exige:

```text
dt ≤ rho·cp·dx² / (2k + 2h·dx)
```

`limite_estabilidad` (`solver1d.py`) devuelve `min` entre la restricción de
difusión y las restricciones Robin de los bordes que sean Robin. El caso de
verificación §5 usa solo Dirichlet, así que ahí rige la primera. El solver
**rechaza** con `ValueError` un `dt` mayor que el límite, antes de
cualquier paso: no existe "corrida inestable" que graficar, porque el
código no integra ese caso. `verification_1d.py --dt-scale 1.20` demuestra
el rechazo (mensaje + código de salida 3).

## 5. Verificación analítica y demos de Δx/Δt (Bloque B de E02)

Problema:

```text
0 ≤ x ≤ L,  T(0,t) = T(L,t) = T0
T(x,0) = T0 + A·sin(pi·x/L)
```

Solución exacta:

```text
T(x,t) = T0 + A·sin(pi·x/L)·exp(-alpha·(pi/L)²·t)
```

Caso conservado sin cambios térmicos:

- `L = 1 m`, `T0 = 20 °C`, `A = 50 °C`, `Qdot = 0`, `t = 24 h`.
- `k = 2.22 W/(m·K)`, `rho = 2400 kg/m³`, `cp = 970 J/(kg·K)`
  (`alpha ≈ 9.54e-7 m²/s`); guía del curso §31 (Ju & Lei, 2019).
- Defecto: `nx = 81`, `dt = 0.40·dt_max` con `n_pasos = ceil(t/dt)`; valores
  efectivos impresos por corrida.

Demos (el script imprime `dx`, `dt_max`, dt efectivo, `r`, `n_pasos` y
error `L_inf`):

| Comando | Qué demuestra |
|---|---|
| `verification_1d.py` | Caso base: error pequeño contra la exacta |
| `verification_1d.py --nx 41` / `--nx 161` | Dependencia de Δx |
| `verification_1d.py --dt-scale 0.80` | Paso mayor, aún estable; reporta error observado |
| `verification_1d.py --dt-scale 1.20` | `dt > dt_max`: rechazo (exit 3), sin integración |

No se afirma monotonicidad del error vs `dt`: la guía registra lo observado
en las corridas reales que se ejecuten y documenten.

## 6. Tests y qué demuestra cada uno

| Suite | Demuestra |
|---|---|
| `test_solver1d.py` | Decaimiento sinusoidal vs. exacta; convergencia 2.0 con `dt ∝ dx²`; estabilidad (incl. límite Robin); conservación de energía; fuente uniforme; Robin físico; rechazos de entradas inválidas |
| `test_foundation.py` | 5 `IfcFooting` con pset `UANDES_HormigonMasivo`; estructura espacial; bbox 18 m / pedestal Ø7 m; volúmenes malla vs. analítico (1e-9) vs. guía (1 %); **selección semántica robusta al cambio de nombre**; el archivo versionado existe y es consistente **sin fijar valores de propiedades** |
| `test_ifc_diff.py` | La herramienta snapshot/diff no reporta el mismo archivo; detecta cambio de propiedad (18→19); detecta cambio geométrico (altura→volumen/bbox); códigos de salida CLI 0/1; redondeo JSON del snapshot |

## 7. Modelo BIM/IFC de la fundación

### Conceptos

- **BIM**: metodología que concentra geometría e información no geométrica
  en un modelo digital de la obra. El flujo del capstone es
  `BIM → IFC → geometría y propiedades → voxelización → solver`; por ahora
  los dos primeros eslabones están implementados y verificados por
  separado.
- **IFC**: formato abierto (esquema + texto STEP) con que BIM se intercambia.
  Un `.ifc` contiene entidades instanciadas (`#12=IFCFOOTING(...)`) y un
  esquema declarado (aquí IFC4).
- **GUID** (`GlobalId`): identificador estable del objeto; es la clave con
  la que `ifc_diff` compara estados.
- **IfcFooting**: clase IFC de cimentación; la usamos para cada vertida.
- **Property set**: agrupación de propiedades; aquí `UANDES_HormigonMasivo`
  (el prefijo `Pset_` está reservado por buildingSMART para sets
  estandarizados).

### Blender y Bonsai

- **Blender** es el modelador 3D genérico; por sí solo no es una herramienta
  BIM.
- **Bonsai** es la extensión que lo convierte en una herramienta BIM con IFC
  nativo: abrir, editar y guardar `.ifc` con psets, GUIDs y estructura
  espacial. "Save IFC Project" reescribe el archivo desde el estado del
  modelo; cada edición debe verificarse.
- **IfcOpenShell** es una biblioteca (no interfaz) para leer/escribir IFC
  desde Python: `foundation.py` genera el modelo y `ifc_io.py` lo lee. El
  solver no depende de Blender ni importa `bpy`.

### Qué hace `foundation.py`

1. Crea el archivo IFC4 y el `IfcProject`.
2. Asigna unidades SI (m, m², m³, °C).
3. Crea los contextos de representación (`Model`, `Body/MODEL_VIEW`).
4. Crea Site, Building y Storey y los agrega con `aggregate.assign_object`.
5. Por cada una de las 5 vertidas (prismas octagonales y troncos; pedestal
   de 48 lados): crea `IfcFooting`, lo contiene en el nivel, le asigna
   placement y representación, y le agrega el pset con sus 7 propiedades.

### Qué hace `ifc_io.py` (selección semántica)

- Abre el IFC, lee proyecto, esquema y unidades.
- **Selecciona vertidas**: todo `IfcProduct` con pset
  `UANDES_HormigonMasivo` que incluya `VertidaID`. El nombre no es filtro.
- **Verifica la clase**: espera `IfcFooting`; si difiere, advierte sin
  descartar (Bonsai puede convertir la clase al editar).
- Ordena por `VertidaID` y devuelve un resumen comprobable.

### Inspección unificada

```powershell
.\.venv\Scripts\python.exe scripts\inspect_ifc.py
```

Lista las 5 vertidas (clase, GUID, propiedades), bbox en coordenadas de
mundo, volumen de malla vs. analítico y vs. la tabla de la guía (tol. 1 %).

## 8. Round-trip en Bonsai (Bloque A de E02)

Procedimiento (la edición es manual en la GUI; la verificación, con Python):

1. Snapshot antes:
   `ifc_state.py geometry/foundation.ifc --salida docs/evidencia_e02/roundtrip_antes.json`.
2. En Bonsai: **File > Open IFC Project**, ubicar `Vertida_01` por GUID,
   editar pset `UANDES_HormigonMasivo` → `TemperaturaColocacion_C`:
   **18 → 19 °C** (modificación de demostración; el 18 °C inicial está
   verificado en el archivo generado), **Save IFC Project**.
3. Diff:
   `ifc_diff.py docs/evidencia_e02/roundtrip_antes.json geometry/foundation.ifc`
   (códigos: 0 sin diferencias, 1 con diferencias, 2 error).
4. Revisar el reporte completo. Se esperaba la propiedad cambiada en ese
   GUID; si el guardado de Bonsai introduce cambios adicionales
   (metadatos, unidades, orden, representación), se muestran y se
   documentan en `docs/evidencia_e02/` — no se promete un único cambio.

Tolerancias geométricas: `|a−b| ≤ tol_abs + tol_rel·max(|a|,|b|)`, defecto
`tol_abs = 1e-4` (0,1 mm en coordenadas; 1e-4 m³ en volumen) y
`tol_rel = 1e-6`. **Alcance limitado**: bbox y volumen no detectan todo
cambio geométrico (p. ej. rotaciones de sólidos simétricos que conservan
envolvente y volumen); las propiedades del pset se comparan en lo exacto.

No hay test que "pruebe" la edición en Bonsai con un valor fijo: la
evidencia son los JSON reales y el diff.

## 9. Preguntas probables de la revisión oral

**¿Qué es BIM y qué es IFC?**
BIM es la metodología; IFC es el formato abierto de intercambio. Ver §7.

**¿Qué rol cumple Blender y qué agrega Bonsai?**
Blender modela 3D genérico; Bonsai lo vuelve herramienta BIM con IFC
nativo (abrir, editar, guardar con psets, GUIDs y estructura espacial).
Ver §7.

**¿Por qué el solver no depende de Blender?**
Recibe temperaturas y parámetros numéricos; corre con Python y NumPy sin
importar `bpy`. La lectura del IFC con IfcOpenShell es un módulo separado;
la conexión automática IFC → solver (voxelización) es trabajo futuro.

**¿Qué significan k, rho, cp y alfa?**
`k` [W/(m·K)] conductividad; `rho` [kg/m³] densidad; `cp` [J/(kg·K)]
calor específico; `alpha = k/(rho·cp)` [m²/s] difusividad: rapidez con que
la temperatura se nivela. En la verificación, `alpha ≈ 9.54e-7 m²/s`.

**¿Cuál es el balance de energía de la ecuación?**
Entrada neta por conducción más generación interna iguala el almacenamiento
`rho·cp·∂T/∂t`. Integrada con bordes adiabáticos, la energía total solo
cambia por la fuente (invariante del test de conservación).

**¿Qué es la condición inicial?**
El estado de partida `T(x,0)` de un problema evolutivo; sin ella la
solución no está definida. Si un extremo contradice su Dirichlet, el solver
rechaza antes de avanzar.

**¿Por qué explícito y no implícito?**
Simple, transparente y suficiente para 1D; permite verificar la física paso
a paso. El costo es la restricción de estabilidad, validada explícitamente.

**¿Qué pasa si `dt` es muy grande?**
El esquema se volvería inestable; el código lo impide: calcula `dt_max` y
lanza `ValueError` antes de integrar. La demo con `--dt-scale 1.20` muestra
el rechazo (código de salida 3).

**¿Por qué `r ≤ 1/2`?**
Es la condición de positividad del coeficiente de `T_i^n` en el esquema
explícito (difusión pura).

**¿Por qué Robin tiene un límite aparte y más estricto?**
El nodo de borde intercambia calor también por convección; su coeficiente
incluye `2h/(rho·cp·dx)`, lo que reduce el `dt` admisible. Ver §4.

**¿Cómo se conserva la energía?**
Con ambos bordes adiabáticos no hay flujo; la suma con pesos de medio
volumen en los extremos se mantiene (test con error relativo < 1e-9).

**¿Cómo se verificó el solver?**
Contra la solución exacta sinusoidal (error `L_inf` y convergencia), más
tests de conservación, fuente uniforme y Robin.

**¿Qué es un GUID?**
El identificador global del objeto IFC; cada vertida tiene uno propio. Es
la clave del diff del round-trip.

**¿Cómo se seleccionan las vertidas al leer el IFC?**
Por pset semántico (`UANDES_HormigonMasivo` con `VertidaID`), no por
nombre; la clase `IfcFooting` se verifica con advertencia. Ver §7.

**¿El IFC es la geometría oficial?**
No: es la geometría docente de la guía Bonsai del capstone (inspirada en
Ju & Lei, 2019). La geometría oficial, si corresponde, debe validarla el
profesor.

**¿Se editó en Bonsai?**
El round-trip de E02 se realiza manualmente en Bonsai y se verifica con
`ifc_state`/`ifc_diff`; la evidencia (JSONs y diff) queda en
`docs/evidencia_e02/`. No se declara completado sin esa verificación.

**¿Cómo se ejecuta el solver sin Blender?**
El paquete `mcplan` y los scripts usan solo Python, NumPy, Matplotlib e
IfcOpenShell; no importan `bpy`.

## 10. Checklist antes de la defensa

- [ ] Entorno de `proyecto/` instalado (`pip install -e "proyecto[dev]"`).
- [ ] `python -m pytest -q` en verde.
- [ ] `inspect_ifc.py` lista 5 vertidas con pset, bbox y volúmenes.
- [ ] `verification_1d.py` base + `--nx 161` + `--dt-scale 0.80` ejecutan y
      reportan valores efectivos; `--dt-scale 1.20` termina con exit 3.
- [ ] Round-trip de E02: snapshot antes, edición manual en Bonsai, diff y
      evidencia en `docs/evidencia_e02/` (no declarar sin hacerlo).
- [ ] README (raíz y `proyecto/`) y esta guía reflejan el estado real.
- [ ] URL del repositorio y SHA del commit anotados para Canvas.
- [ ] Ensayo oral con esta guía.
