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
interfaz de **Bonsai sí se ejecutó**: se abrió el IFC en Blender 5.2.2 con
Bonsai, se cambió `TemperaturaColocacion_C` de `Vertida_01` de 18 °C a 19 °C,
se guardó con **Save IFC Project** y se verificó desde Python con
`scripts/inspect_ifc.py`. Ver la sección 8 para el detalle.

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
- La fuente se suma **una vez por paso** como `dt·Qdot/(rho·cp)` en los nodos
  interiores y en los bordes Neumann/Robin. En Dirichlet se mantiene la
  temperatura impuesta, sin sumar la fuente al nodo de borde.

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
| `test_rechaza_propiedades_y_bordes_no_finitos` | Se rechazan NaN e infinitos en propiedades, bordes y espaciamiento. |
| `test_rechaza_inicial_incompatible_con_dirichlet_antes_de_avanzar` | Ambos extremos se validan antes de avanzar, incluso si se piden cero pasos. |
| `test_dirichlet_con_fuente_mantiene_extremos_e_incrementa_interior` | La fuente calienta el interior sin modificar la temperatura impuesta en los extremos. |
| `test_generar_y_leer_tres_vertidas` | El IFC se genera con 3 vertidas, GUIDs, geometría, unidades y psets; el generador conserva `Vertida_01` = 18 °C. |
| `test_modelo_ifc_versionado_existe_y_se_lee` | El IFC versionado es legible y consistente. |
| `test_ifc_versionado_fue_editado_en_bonsai` | El IFC versionado tiene `Vertida_01` = 19 °C, evidencia de la edición en Bonsai. |
| `test_ifc_contiene_estructura_espacial` | Existe la jerarquía Project/Site/Building/Storey y 3 losas. |

## 7. Modelo BIM/IFC

### Conceptos

- **BIM** (*Building Information Modeling*): metodología de trabajo que
  concentra en un modelo digital la geometría **y** la información no geométrica
  (materiales, fechas, propiedades térmicas, etc.) de las piezas de una obra.
  BIM es el **proceso**; el modelo digital es su producto. En este proyecto el
  flujo es `BIM → IFC → geometría y propiedades → solver`, de modo que el IFC
  es el vehículo de intercambio que nuestro código consume.
- **IFC** (*Industry Foundation Classes*): **formato/esquema abierto** con el
  que BIM se intercambia entre herramientas. Un archivo `.ifc` es texto plano
  (sintaxis STEP/SPF) con entidades instanciadas (`#12=IFCSLAB(...)`) y un
  esquema declarado (`IFC4`). IFC facilita el intercambio abierto entre
  herramientas; BIM también puede desarrollarse con otros formatos.
- **GUID** (`GlobalId`): identificador estable del objeto dentro del modelo.
- **IfcSlab**: losa; se usa como clase para cada vertida.
- **Property set**: agrupación de propiedades. Aquí `Pset_HormigonMasivo`.
- **Unidades**: se declaran en `IfcProject.UnitsInContext`. Usamos SI y
  `DEGREE_CELSIUS` para temperatura.
- **Estructura espacial**: `IfcProject` → `IfcSite` → `IfcBuilding` →
  `IfcBuildingStorey`; las losas se contienen en el nivel.

### Blender y Bonsai: qué rol cumple cada uno

- **Blender** es el **modelador geométrico 3D genérico** (escenas, mallas,
  render). Por sí solo no "habla IFC": es un entorno de modelado, no un
  entorno BIM.
- **Bonsai** es la **extensión de Blender que lo convierte en una herramienta
  BIM nativa IFC**: permite crear, abrir, editar y guardar archivos `.ifc`
  con su estructura espacial, property sets y GUIDs. Bonsai trabaja directamente
  sobre el modelo IFC, lo que evita una traducción intermedia a un formato
  propietario; aun así, hay que verificar el resultado de cada edición.
  "Save IFC Project" reescribe el archivo IFC desde el estado del modelo.
- Papel de cada uno **en este proyecto**: Blender + Bonsai se usaron para
  **abrir y editar manualmente** el IFC de ejemplo (completar el ciclo BIM,
  ver §8). El **solver no depende de Blender**: recibe arreglos de temperatura y
  parámetros térmicos en Python. En E01, `ifc_io.py` lee el IFC por separado
  mediante IfcOpenShell; la conexión automática IFC–solver es trabajo futuro.
- **IfcOpenShell**, por el contrario, es una **biblioteca** (no interfaz) para
  leer/escribir IFC desde Python; `build_model.py` la usa para generar el
  modelo y `ifc_io.py` para leerlo.

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

## 8. Ciclo de edición en Bonsai (realizado)

> **Ejecutado por el integrante.** Se completó el ciclo de G02 en la interfaz
> gráfica y se verificó el resultado desde Python. No hay que declararlo como
> pendiente.

Procedimiento realizado:

1. Se instaló/usó **Blender 5.2.2** con la extensión **Bonsai**.
2. Se abrió `geometry/fundacion_e01_ejemplo.ifc`.
3. Se verificó el árbol del modelo: Project → Site → Building → Storey →
   `Vertida_01`, `Vertida_02`, `Vertida_03`.
4. Se revisaron `Name`, `GlobalId`, clase IFC y `Pset_HormigonMasivo`.
5. Se editó `TemperaturaColocacion_C` de `Vertida_01`: de **18 °C a 19 °C**.
6. Se guardó con **Save IFC Project** sobre el mismo archivo.
7. Se verificó desde Python que el cambio persiste:

   ```powershell
   .\.venv\Scripts\python.exe scripts\inspect_ifc.py
   ```

   Salida: `Vertida_01` con `TemperaturaColocacion_C: 19`.
8. El encabezado del IFC versionado quedó con autoría `Bonsai 0.9.0-post1`.

Diferencia clave que hay que saber explicar:

- **Generador (`build_model.py`)**: valores originales de ejemplo,
  `Vertida_01` = 18 °C. No se modificó.
- **IFC versionado (`geometry/…ifc`)**: versión editada en Bonsai,
  `Vertida_01` = 19 °C.
- Por eso **no hay que regenerar** con `scripts/make_ifc.py` sobre el archivo
  versionado: eso borraría la edición de Bonsai. El script ahora protege ese
  archivo: escribe por defecto en `geometry/fundacion_e01_generada.ifc` y se
  niega a sobrescribir el versionado salvo `--forzar`.
- El test `test_ifc_versionado_fue_editado_en_bonsai` deja fijada esa
  diferencia.

## 9. Preguntas probables de la revisión oral

**¿Qué es BIM y qué es IFC?**
BIM es la **metodología** de concentrar geometría e información en un modelo
digital vivo de la obra; IFC es el **formato abierto** (esquema + archivo de
texto) con que ese modelo se intercambia entre herramientas. Ver §7.

**¿Qué rol cumple Blender y qué agrega Bonsai?**
Blender es el modelador 3D genérico; Bonsai es la extensión que lo vuelve
herramienta BIM con IFC nativo (abrir, editar y guardar `.ifc`,
con psets, GUIDs y estructura espacial, verificando el resultado). Ver §7.

**¿Por qué el solver no depende de Blender?**
Porque el solver recibe temperaturas y parámetros numéricos y se ejecuta
con Python y NumPy; no utiliza el estado de Blender ni importa `bpy`.
En E01, la lectura del IFC con IfcOpenShell es un módulo separado: todavía
no alimenta automáticamente al solver. El flujo IFC–solver es la meta futura.

**¿Qué significan k, rho, cp y alfa?**
- `k` [W/(m·K)]: conductividad térmica; cuánta energía por unidad de tiempo
  y área pasa por gradiente de temperatura unitario. El hormigón de la
  verificación usa `k = 2.22`.
- `rho` [kg/m³]: densidad; cuánta masa hay por volumen (`2400` para hormigón).
- `cp` [J/(kg·K)]: calor específico; cuánta energía por unidad de masa eleva
  la temperatura en 1 K (`970`).
- `alfa = k/(rho·cp)` [m²/s]: difusividad térmica; **rapidez con la que la
  temperatura se nivela**. Combina conducción (`k`) contra capacidad de
  almacenamiento (`rho·cp`). En la verificación, `alfa ≈ 9.54e-7 m²/s`.

**¿Cuál es el balance de energía de la ecuación?**
En un volumen de control 1D: entrada neta por conducción (`k·∂²T/∂x²`) más
generación interna (`Qdot`) iguala el almacenamiento (`rho·cp·∂T/∂t`). La
ecuación resuelta es exactamente ese balance punto a punto. Integrada sobre
toda la barra con ambos bordes adiabáticos, la energía total solo cambia por
la fuente; ese es el invariant del test de conservación.

**¿Qué es la condición inicial?**
La distribución de temperatura `T(x, 0)` que se necesita para arrancar un
problema **evolutivo** (parabólico): sin ella la solución no está definida.
Las condiciones de borde (Dirichlet/Neumann/Robin) acotan el espacio; la
condición inicial da el estado de partida en el tiempo. En la verificación
usamos `T(x,0) = T0 + A·sin(pi·x/L)`; en el solver, el arreglo `T_inicial`. Si un extremo contradice su
temperatura Dirichlet, el solver rechaza la entrada antes de calcular.

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
Sí. Se abrió el IFC en Blender 5.2.2 con Bonsai, se cambió
`TemperaturaColocacion_C` de `Vertida_01` de 18 °C a 19 °C, se guardó con
**Save IFC Project** y se verificó el cambio desde Python con
`scripts/inspect_ifc.py`. El generador en Python conserva el valor original de
18 °C; el IFC versionado es la versión editada (19 °C).

**¿Cómo se ejecuta el solver sin Blender?**
El paquete `mcplan` y los scripts usan solo Python, NumPy, Matplotlib e
IfcOpenShell. No importan `bpy`. La edición BIM en Bonsai es un paso aparte que
ya se realizó manualmente.

## 10. Checklist antes de entregar

- [ ] Entorno de E01 instalado con `pip install -e "E01[dev]"` (o `".[dev]"` desde `E01/`).
- [ ] `python -m pytest -q` (en `E01/`) → 16 tests aprobados.
- [ ] `geometry/fundacion_e01_ejemplo.ifc` presente y legible (versión Bonsai, `Vertida_01` = 19 °C).
- [ ] `results/figures/verificacion_1d.png` presente.
- [ ] `inspect_ifc.py` muestra 3 vertidas, GUIDs y las 7 propiedades.
- [ ] README (raíz y E01) y esta guía reflejan el ciclo en Bonsai como realizado.
- [ ] URL del repositorio y SHA del commit anotados para Canvas.
- [ ] Ensayo oral: ecuación, estabilidad, Robin, fuente, verificación e IFC.
