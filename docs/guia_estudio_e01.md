# Guía de estudio — E01

Esta guía resume lo necesario para defender la Entrega 01: física del solver,
decisiones de código, verificación y modelo BIM/IFC. Todo el contenido es
reproducible con los comandos del `README.md`.

## 1. Qué se entrega

1. Un **modelo IFC** con tres vertidas (`Vertida_01`, `Vertida_02`,
   `Vertida_03`), identidad, unidades, estructura espacial, geometría y el
   property set `Pset_HormigonMasivo`.
2. Un **solver térmico 1D** explícito, independiente de Blender.
3. **Tests** y una **figura** que comparan el solver con una solución exacta.
4. Este repositorio reproducible y la explicación oral.

La geometría del IFC es **didáctica**, no oficial. El ciclo de edición en la
interfaz de **Bonsai no fue ejecutado** (no está instalado en el entorno de
desarrollo); se documenta como paso pendiente.

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
- Si se refina con `dt ∝ dx²`, el error temporal también escala como `dx²`; por
  eso la convergencia total observada es de segundo orden. Medimos **1.985**.
- La fuente se suma **una vez por paso** como `dt·Qdot/(rho·cp)` en todos los
  nodos, incluidos los de borde.

### Corrección respecto del script docente `05_calor_interno.py`

En el script original el término `Q0` se sumaba dentro de `r·(...)`, lo que le
da unidades incorrectas para una fuente volumétrica en `W/m³`. La forma
correcta es:

```text
incremento_fuente = dt·Qdot/(rho·cp)   [K]
```

Así, con bordes adiabáticos y fuente uniforme, la temperatura sube
exactamente `Qdot·t/(rho·cp)`. Esto está cubierto por
`test_fuente_uniforme_adiabatica_aumento_lineal`.

## 3. Condiciones de borde

### Dirichlet

Se impone directamente el valor en el nodo extremo:

```text
T_0 = T_borde
```

Es la condición prioritaria de la entrega.

### Neumann adiabática

Solo se implementa `q'' = 0`. Con un nodo fantasma `T_{-1} = T_1`, el flujo en
el borde es nulo. El nodo extremo evoluciona como:

```text
T_0^{n+1} = T_0^n + 2r·(T_1^n - T_0^n) + incremento_fuente
```

El factor `2r` (en vez de `r`) aparece porque el volumen de control del borde
es de ancho `dx/2`. Para la energía se usan pesos `[0.5, 1, ..., 1, 0.5]`, de
modo que la energía discreta es consistente con esos medios volúmenes.

### Robin

Balance sobre medio volumen de control en el borde izquierdo:

```text
rho·cp·(dx/2)·dT_0/dt = k·(T_1 - T_0)/dx + h·(T_ambiente - T_0)
```

Despejando:

```text
dT_0/dt = 2k/(rho·cp·dx²)·(T_1 - T_0)
          + 2h/(rho·cp·dx)·(T_ambiente - T_0)
```

El borde derecho es simétrico. `h` es el coeficiente convectivo
`[W/(m²·K)]` y `T_ambiente` está en `°C`.

## 4. Estabilidad

Para difusión pura, el coeficiente de `T_i^n` en el esquema exige:

```text
r = alpha·dt/dx² <= 1/2  ⇒  dt <= dx²/(2·alpha)
```

Para Robin, el coeficiente del nodo de borde en el balance de medio volumen es:

```text
1 - dt·[2k/(rho·cp·dx²) + 2h/(rho·cp·dx)] >= 0
```

Por lo tanto:

```text
dt <= rho·cp·dx²/(2k + 2h·dx)
```

`limite_estabilidad` toma el mínimo entre la restricción de difusión y las
restricciones Robin de ambos bordes. El solver **rechaza** `dt` mayor que ese
límite con `ValueError`. Esto es una decisión deliberada: evita resultados
oscilantes que parezcan físicos.

## 5. Verificación analítica

Problema:

```text
0 <= x <= L,  T(0,t) = T(L,t) = T0
T(x,0) = T0 + A·sin(pi·x/L)
```

Solución exacta:

```text
T(x,t) = T0 + A·sin(pi·x/L)·exp(-alpha·(pi/L)²·t)
```

Es un caso **no trivial**: la forma espacial se conserva y la amplitud decae.
No se debe usar una curva numérica como si fuera solución analítica.

Parámetros de la figura versionada:

- `L = 1 m`, `nx = 81`, `T0 = 20 °C`, `A = 50 °C`.
- `k = 2.22 W/(m·K)`, `rho = 2400 kg/m³`, `cp = 970 J/(kg·K)`.
- `alpha ≈ 9.536e-07 m²/s`, `dx = 0.0125 m`, `dt = 32.76 s`, `r = 0.200`.
- `t = 24 h`; error `L_inf` final `4.63e-04 °C`.

La figura muestra la analítica (líneas) y la numérica (marcadores) en 0, 6, 12,
18 y 24 h, e incluye parámetros y error en el propio gráfico.

## 6. Tests y qué demuestra cada uno

| Test | Qué demuestra |
|---|---|
| `test_decaimiento_sinusoidal_frente_a_solucion_exacta` | El esquema reproduce la solución exacta con error pequeño. |
| `test_convergencia_espacial_segundo_orden` | Al refinar con `dt ∝ dx²`, el error baja con pendiente ≈ 2. |
| `test_temperatura_uniforme_compatible_con_dirichlet` | No aparecen oscilaciones espurias si todo está a la temperatura de borde. |
| `test_rechaza_paso_temporal_inestable` | La validación de estabilidad funciona. |
| `test_rechaza_parametros_invalidos` | Se rechazan `dx`, `dt`, mallas y propiedades inválidas. |
| `test_conservacion_energia_ambos_bordes_adiabaticos` | Sin flujo en los bordes, la energía discreta se conserva. |
| `test_fuente_uniforme_adiabatica_aumento_lineal` | La fuente volumétrica tiene las unidades y el incremento correctos. |
| `test_robin_enfria_superficie_mas_que_centro` | Robin produce el perfil físico esperado. |
| `test_robin_rechaza_paso_que_viola_su_limite` | Se aplica la restricción más estricta de Robin. |
| `test_generar_y_leer_tres_vertidas` | El IFC se genera con 3 vertidas, GUIDs, geometría, unidades y psets. |
| `test_modelo_ifc_versionado_existe_y_se_lee` | El IFC versionado es legible y consistente. |
| `test_ifc_contiene_estructura_espacial` | Existe la jerarquía Project/Site/Building/Storey y 3 losas. |

## 7. Modelo BIM/IFC

### Conceptos

- **IFC** es un esquema abierto para intercambiar información de construcción.
  Un archivo `.ifc` es texto (STEP/SPF) con entidades instanciadas.
- **GUID** (`GlobalId`): identificador estable del objeto dentro del modelo.
- **IfcSlab**: losa; se usa como clase para cada vertida.
- **Property set**: agrupación de propiedades. Aquí `Pset_HormigonMasivo`.
- **Unidades**: se declaran en `IfcProject.UnitsInContext`. Usamos SI y
  `DEGREE_CELSIUS` para temperatura.
- **Estructura espacial**: `IfcProject` → `IfcSite` → `IfcBuilding` →
  `IfcBuildingStorey`; las losas se contienen en el nivel.

### Qué hace `build_model.py`

1. Crea archivo IFC4 y `IfcProject`.
2. Asigna unidades SI (metro, m², m³, °C).
3. Crea contextos de representación (`Model`, `Body/MODEL_VIEW`).
4. Crea Site, Building y Storey y los agrega con `aggregate.assign_object`.
5. Por cada vertida: crea `IfcSlab`, la contiene en el nivel, le asigna
   placement y una representación de losa, y le agrega el pset con las siete
   propiedades.
6. Escribe el `.ifc`.

### Qué hace `ifc_io.py`

- Abre el IFC con `ifcopenshell.open`.
- Lee proyecto, esquema y unidades.
- Recorre `IfcSlab`, obtiene GUID, clase, geometría y psets con
  `ifcopenshell.util.element.get_psets`.
- Devuelve un resumen ordenado y comprobable.

### Inspección reproducible

```powershell
.\.venv\Scripts\python.exe scripts\inspect_ifc.py
```

Debe listar tres vertidas, sus GUIDs, fechas, temperaturas de colocación y el
detalle de las siete propiedades.

## 8. Procedimiento manual pendiente en Bonsai

> **No ejecutado en este entorno.** No afirmar que se verificó en Bonsai hasta
> completar estos pasos y guardar evidencia.

1. Instalar Blender 4.2+ (preferir LTS) y la extensión **Bonsai** desde el
   gestor de extensiones de Blender.
2. Abrir Blender y habilitar Bonsai.
3. Cargar `geometry/fundacion_e01_ejemplo.ifc`.
4. Verificar el árbol del modelo: Project → Site → Building → Storey →
   `Vertida_01`, `Vertida_02`, `Vertida_03`.
5. Seleccionar cada losa y revisar:
   - `Name`, `GlobalId` y clase IFC;
   - `Pset_HormigonMasivo` y sus siete propiedades.
6. Editar una propiedad (por ejemplo `TemperaturaColocacion_C`), exportar a un
   IFC nuevo (no sobrescribir el versionado) y volver a inspeccionar con
   `scripts/inspect_ifc.py`.
7. Guardar evidencia: captura de pantalla y, si aplica, el IFC reexportado.
8. Actualizar esta sección y el `README.md` indicando que el ciclo se ejecutó.

## 9. Preguntas probables de la revisión oral

**¿Por qué explícito y no implícito?**
Porque es simple, transparente y suficiente para 1D; permite verificar la
física paso a paso. El costo es la restricción de estabilidad, que validamos
explícitamente.

**¿Qué pasa si `dt` es muy grande?**
El esquema se vuelve inestable y aparecen oscilaciones que crecen. El código lo
impide: calcula `dt_max` y lanza `ValueError` si se supera.

**¿Por qué `r <= 1/2`?**
Es la condición de positividad del coeficiente de `T_i^n` en el esquema
explícito. Si `r > 1/2`, un nodo puede “sobre-corregirse” y oscilar.

**¿Por qué Robin tiene un límite más estricto?**
Porque el nodo de borde pierde calor también por convección; el coeficiente que
multiplica a `T_0` incluye `2h/(rho·cp·dx)`, lo que reduce el `dt` admisible.

**¿Cómo se conserva la energía?**
Con ambos bordes adiabáticos no hay flujo; la suma con pesos de medio volumen
en los extremos se mantiene. El test lo verifica con error relativo < 1e-9.

**¿Cómo se verificó el solver?**
Contra una solución exacta sinusoidal no trivial, midiendo error `L_inf` y
pendiente de convergencia. También con tests de conservación, fuente uniforme
y Robin.

**¿Qué es un GUID?**
El identificador global del objeto IFC. En este modelo cada vertida tiene uno
distinto; se genera al crear el archivo.

**¿El IFC es la geometría oficial?**
No. Es un ejemplo didáctico de tres losas de 4 × 3 × 1 m. La geometría oficial
debe ser validada por el profesor.

**¿Se editó en Bonsai?**
No en este entorno. Se generó y verificó con IfcOpenShell; el procedimiento
manual está documentado y queda pendiente con evidencia.

**¿Cómo se ejecuta sin Blender?**
El paquete `mcplan` y los scripts usan solo Python, NumPy, Matplotlib e
IfcOpenShell. No importan `bpy`.

## 10. Checklist antes de entregar

- [ ] `python -m pytest -q` → 12 tests aprobados.
- [ ] `geometry/fundacion_e01_ejemplo.ifc` presente y legible.
- [ ] `results/figures/verificacion_1d.png` presente.
- [ ] `inspect_ifc.py` muestra 3 vertidas, GUIDs y las 7 propiedades.
- [ ] README y esta guía sin afirmaciones no verificadas sobre Bonsai.
- [ ] URL del repositorio y SHA del commit anotados para Canvas.
- [ ] Ensayo oral: ecuación, estabilidad, Robin, fuente, verificación e IFC.
