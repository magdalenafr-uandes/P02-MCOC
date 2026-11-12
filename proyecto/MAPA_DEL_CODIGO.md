# Mapa del código — dónde está cada cosa

Índice para responder rápido en una revisión. Cada concepto está marcado en el
código con un comentario **`[MAPA:…]`**. Para llegar a la línea exacta:

- **VS Code:** `Ctrl+Shift+F` y buscar, por ejemplo, `MAPA:robin`.
- **Terminal:** `git grep -n "MAPA:robin"`.

Las etiquetas no se desordenan aunque el código cambie. El test
`tests/test_mapa_codigo.py` falla si este mapa nombra una etiqueta que ya no existe.

## 1. El caso base en 5 pasos (lo que corre de verdad)

Ciclo diario estimado desde CSV y horas locales: `caso/ciclo_diario.py`,
`MAPA:ciclo-diario`. Controles de inicio y fechas de vertida en el visor;
traducción a `simulacion.inicio` e `inicio_h` en `pipeline.py`.
Ver `docs/ciclo_diario.md` para la procedencia y las limitaciones del escenario.

Moldaje visible en la reproducción 3D: `pipeline.py`, `MAPA:visor-moldaje`,
exporta inicio, retiro absoluto y resistencia por vertida. El botón del visor
colorea las caras laterales expuestas mientras ese moldaje está activo.

Indicadores de comparación y sondas fijas: `indicadores.py`, `MAPA:indicadores-visor`.
Se exportan en `resultado.json`: picos, diferencial por vertida a la profundidad
del criterio, sondas del núcleo/borde y temperaturas de piezas previas en cada colocación.

```text
configs/e07_caso_base.yaml   todos los parámetros del caso (material, T, moldaje, malla, clima)
        │  caso/config.py         valida el YAML y lo combina con el IFC          [MAPA:prioridad-ifc-yaml]
        ▼
geometry/foundation.ifc      geometría + pset por vertida
        │  bim/mallas_ifc.py      lee las mallas trianguladas                     [MAPA:lectura-ifc]
        ▼
bim/voxelizador.py           IFC -> voxeles con vertida_id, suelo y caras         [MAPA:voxel-pertenece]
        ▼
thermal/etapas.py            simulación por etapas: activación, hidratación,     [MAPA:activacion-vertidas]
                             moldaje, clima y criterios
        │  thermal/bordes.py     qué ve cada cara: sol-aire, moldaje/aislación    [MAPA:sol-aire]
        │  caso/clima.py         snapshots de pronóstico y su respaldo           [MAPA:completar-pronostico]
        ▼
thermal/voxel.py             motor: balance de voxel, bordes, estabilidad        [MAPA:balance-voxel]
```

Se ejecuta con `scripts/pipeline_e07.py` (CLI), `scripts/comparar_e08.py`
(base vs. variante) o el visor E08 (`Abrir visualizador.cmd`). Los tres usan el
mismo motor (`SimuladorEtapas`).

## 2. "¿Dónde está…?" (preguntas del profesor)

### Física del voxel y solver

| Pregunta | Archivo | Etiqueta |
|---|---|---|
| Balance de un voxel | `thermal/voxel.py` | `MAPA:balance-voxel` |
| Signo del flujo (positivo entra) | `thermal/voxel.py` | `MAPA:flujo-signos` |
| Paso explícito T^{n+1} | `thermal/voxel.py` | `MAPA:euler-explicito` |
| Criterio de estabilidad Δt ≤ C/ΣG | `thermal/voxel.py` | `MAPA:estabilidad` |
| Cómo se elige Δt en el caso real | `thermal/etapas.py` | `MAPA:estabilidad-caso` |
| Dos materiales (media armónica) | `thermal/voxel.py` | `MAPA:media-armonica` |
| k, ρ, cp de cada voxel (hormigón/suelo/vacío) | `thermal/etapas.py` | `MAPA:propiedades-por-voxel` |
| Voxel aún no vertido (vacío) | `thermal/etapas.py` | `MAPA:vacio` |
| Balance global de energía | `thermal/etapas.py` | `MAPA:balance-energia` |

### Condiciones de borde

| Pregunta | Archivo | Etiqueta |
|---|---|---|
| Dirichlet (T impuesta) | `thermal/voxel.py` | `MAPA:dirichlet` |
| Neumann / adiabática (flujo impuesto) | `thermal/voxel.py` | `MAPA:neumann` |
| Robin (convección) en el motor | `thermal/voxel.py` | `MAPA:robin` |
| Robin en el caso: media celda + moldaje + película | `thermal/etapas.py` | `MAPA:robin-caso` |
| Flujo hacia el ambiente en cada paso | `thermal/etapas.py` | `MAPA:flujo-ambiente` |
| Base de la caja (suelo profundo) | `thermal/etapas.py` | `MAPA:base-suelo` |
| ¿Qué cara es superficie exterior? | `bim/voxelizador.py` | `MAPA:caras-expuestas` |
| Corrección del área en caras inclinadas | `bim/voxelizador.py` | `MAPA:correccion-area` |

En el caso real, todas las caras de la caja son adiabáticas en el motor. El
intercambio con el aire entra por las caras expuestas del sólido (`robin-caso`)
y el suelo profundo por la base (`base-suelo`).

### Ambiente, moldaje y clima (E10) — módulo `thermal/bordes.py`

| Pregunta | Archivo | Etiqueta |
|---|---|---|
| ¿Qué término usa la temperatura ambiente? | `thermal/bordes.py` | `MAPA:temperatura-ambiente` |
| T sol-aire: convección + onda larga + sol | `thermal/bordes.py` | `MAPA:sol-aire` |
| ¿Cómo entra el viento? h_c = a + b·v | `thermal/bordes.py` | `MAPA:viento-conveccion` |
| Viento de 10 m a la superficie (perfil logarítmico) | `thermal/bordes.py` | `MAPA:viento-perfil` |
| ¿Qué es un flujo solar? α·G [W/m²] | `thermal/bordes.py` | `MAPA:flujo-solar` |
| Evitar doble conteo radiación/convección | `caso/config.py` | `MAPA:doble-conteo` |
| Resistencia de moldaje/aislación R = e/k | `thermal/bordes.py` | `MAPA:capas-proteccion` |
| ¿Qué cambia al desmoldar? | `thermal/bordes.py` | `MAPA:moldaje-retiro` |
| Aislación después del desmolde | `caso/config.py` | `MAPA:aislacion-desmolde` |
| Metadata del snapshot (forecast/reanálisis/observación) | `caso/clima.py` | `MAPA:snapshot-metadata` |
| Huella del snapshot usado (trazabilidad) | `caso/clima.py` | `MAPA:snapshot-huella` |
| Pronóstico que no cubre los 14 días: respaldo | `caso/clima.py` | `MAPA:completar-pronostico` |

Scripts: `descargar_clima.py` (cliente Open-Meteo, nunca sobrescribe) y
`listar_clima.py` (qué cubre cada snapshot de la ventana de la obra y con qué
anticipación). Respuestas completas: `docs/e10.md`.

No confundir con `thermal/boundaries.py`: ese archivo (E01) guarda
`PropiedadesTermicas` (k, ρ, cp; la usa `voxel.py`) y la `CondicionBorde` del
solver 1D legado. Los bordes del caso real están en `thermal/bordes.py`.

### Fuentes, hidratación y criterios

| Pregunta | Archivo | Etiqueta |
|---|---|---|
| Fuente volumétrica en el motor (W/m³ · V) | `thermal/voxel.py` | `MAPA:fuente-volumetrica` |
| Calor de hidratación en cada voxel | `thermal/etapas.py` | `MAPA:hidratacion-fuente` |
| Datos medidos Q(t) del profesor → θ(t) | `caso/fuente_calor.py` | `MAPA:fuente-medida` |
| Modelos de hidratación (exponencial, Schindler, tabla) | `thermal/hidratacion.py` | `MAPA:hidratacion-modelos` |
| Potencia q''' = ρ cp dθ/dt | `thermal/hidratacion.py` | `MAPA:hidratacion-potencia` |
| Calor de un paso sin explotar (incremento exacto de θ, acotado por θ∞) | `thermal/hidratacion.py` | `MAPA:hidratacion-paso` |
| Paso que resuelve la cinética (≤ 1 K de θ por paso, `simulacion.dtheta_max_paso_K`) | `thermal/etapas.py` | `MAPA:paso-hidratacion` |
| Efecto de la temperatura (Arrhenius) | `thermal/hidratacion.py` | `MAPA:arrhenius` |
| Edad equivalente (madurez) | `thermal/etapas.py` | `MAPA:edad-equivalente` |
| θ∞ desde la dosificación | `thermal/hidratacion.py` | `MAPA:dosificacion` |
| Activación de una vertida nueva | `thermal/etapas.py` | `MAPA:activacion-vertidas` |
| T "superficial" a 25 mm | `thermal/etapas.py` | `MAPA:superficie-25mm` |
| ΔT núcleo − superficie | `thermal/etapas.py` | `MAPA:criterio-deltaT` |
| Dónde ocurren T_max y ΔT_max (celda del núcleo y de la superficie) | `thermal/etapas.py` | `MAPA:ubicacion-maximos` |
| Caso determinista de 14 días y su diagnóstico (E12) | `scripts/e12_determinista.py` | — (ver `docs/e12.md`) |

### Tuberías de enfriamiento — módulo `thermal/tuberias.py`

La pared del tubo es **Dirichlet** (T = T_agua). Cada celda que cruza un tubo cede
P = G·(T_celda − T_agua) con la conductancia de pozo G = 2πkL/ln(r_eq/r)
(r_eq = 0,14·√(Δa²+Δb²)): la energía extraída varía con la temperatura del hormigón.

| Pregunta | Archivo | Etiqueta |
|---|---|---|
| Pared del tubo a T_agua y conductancia G | `thermal/tuberias.py` | `MAPA:tuberia-dirichlet` |
| Dónde pasan los tubos (cota, separación, recubrimiento) | `thermal/tuberias.py` | `MAPA:tuberia-trazado` |
| Calor que extrae el agua en cada paso (y su energía) | `thermal/etapas.py` | `MAPA:tuberia-energia` |
| Lectura de los circuitos desde el YAML | `caso/config.py` | `MAPA:config-tuberias` |
| Controles de tuberías en el visor | `pipeline.py` | `MAPA:visor-tuberias` |

Supuestos y modelo alternativo (agua que se calienta, NTU): `docs/enfriamiento_tuberias.md`.

### BIM, voxelización y datos

| Pregunta | Archivo | Etiqueta |
|---|---|---|
| Lectura del IFC (mallas + pset) | `bim/mallas_ifc.py` | `MAPA:lectura-ifc` |
| Caja de cálculo (márgenes, suelo, Δx/Δz) | `bim/voxelizador.py` | `MAPA:grilla` |
| ¿Cuándo un voxel pertenece al sólido? | `bim/voxelizador.py` | `MAPA:voxel-pertenece` |
| Geometría en planta (radios) | `bim/foundation.py` | `MAPA:geometria-planta` |
| Espesor y cota de cada vertida | `bim/foundation.py` | `MAPA:geometria-espesores` |
| Prioridad YAML > IFC | `caso/config.py` | `MAPA:prioridad-ifc-yaml` |
| Lectura del material desde el YAML | `caso/config.py` | `MAPA:config-hormigon` |
| Lectura del suelo desde el YAML | `caso/config.py` | `MAPA:config-suelo` |
| Clima real (snapshot) | `caso/clima.py` | `MAPA:clima` |
| Orquestación config → IFC → grilla → simulación | `caso/pipeline.py` | `MAPA:pipeline` |
| Cómo `--set` / `--variante` cambian el YAML | `caso/config.py` | `MAPA:sobrescrituras` |
| Visor E08 → mismo YAML y motor que la CLI | `pipeline.py` | `MAPA:visor-adaptador` |
| Visor: moldaje, desmolde, aislación y snapshot de clima | `pipeline.py` | `MAPA:visor-proteccion-clima` |

Las rutas son relativas a `proyecto/src/mcplan/`.

## 3. "Cambia X" (cambios en vivo)

**Regla:** ningún parámetro del caso está escrito en el solver. Todo se
cambia en `configs/e07_caso_base.yaml`, editando el archivo o sin tocarlo con
`--set`. Una clave mal escrita da error en vez de ignorarse.

Desde `proyecto/`:

```powershell
# base vs. variante en una sola figura (modo rápido, ~12 s)
.venv\Scripts\python.exe scripts\comparar_e08.py --variante hormigones.M1.k_W_mK=2.5
# caso completo con el cambio (~100 s)
.venv\Scripts\python.exe scripts\pipeline_e07.py --set hormigones.M1.k_W_mK=2.5
```

| Cambio pedido | Clave en el YAML (`--set` / `--variante`) |
|---|---|
| Conductividad, densidad o calor específico del hormigón | `hormigones.M1.k_W_mK=2.5`, `hormigones.M1.rho_kg_m3=2350`, `hormigones.M1.cp_J_kgK=1000` |
| Curva de calor medida (probeta) | `hormigones.M1.hidratacion.curva=M3_SS` (`media` o `M1_SS` … `M4_22A`) |
| Volver a la curva pedagógica | `hormigones.M1.hidratacion={modelo: exponencial, theta_inf_C: 45, tau_h: 30, Ea_J_mol: 40000, T_ref_C: 20}` |
| T de colocación de todas las vertidas | `vertidas.defecto.T_colocacion_C=12` |
| T de colocación de una vertida | `vertidas.3.T_colocacion_C=12` |
| Hora de inicio de una vertida | `vertidas.3.inicio_h=20` |
| Ocultar una vertida | `vertidas.5.visible=false` |
| Espesor de la aislación superior | `vertidas.defecto.R_superior_m2K_W=1.25` (R = e/k: 50 mm con k = 0,04 → 1,25; 100 mm → 2,5) |
| Moldaje lateral | `vertidas.defecto.moldaje=madera_18mm` (catálogo `protecciones`) o `vertidas.defecto.R_lateral_m2K_W=0.12` |
| Retiro del moldaje | `vertidas.defecto.retiro_moldaje_h=48` |
| Aislación al desmoldar | `vertidas.defecto.aislacion=manta_50mm`, `"vertidas.defecto.aislacion_caras=[superior, lateral]"`, `vertidas.defecto.aislacion_desde_h=desmolde` |
| Viento / convección | `ambiente.conveccion_viento.altura_superficie_m=2`, `...a_W_m2K=2.8`, `...b_J_m3K=3.0` |
| Sol y cielo | `ambiente.absortividad_solar=0.65`, `ambiente.emisividad=0.9`, `ambiente.factor_solar_lateral=0.3` |
| Otro pronóstico | `clima.snapshot=../data/weather/<carpeta>` (ver `scripts/listar_clima.py`) |
| Material del suelo | `suelo.k_W_mK=1.8`, `suelo.rho_kg_m3`, `suelo.cp_J_kgK` |
| Espesor de suelo modelado | `suelo.espesor_m=4.0` (0 = sin suelo) |
| T del suelo profundo / inicial | `base.T_C=18`, `suelo.T_inicial_C=18` (o `base.tipo=adiabatico`) |
| Temperatura ambiente constante (sin clima real) | `--set clima=null --set "ambiente={T_C: 25, h_W_m2K: 10}"` |
| Tamaño de voxel | `malla.paso_m=0.2`, `malla.paso_z_m=0.05` |
| Duración | `simulacion.duracion_h=168` |
| Criterios | `criterios.T_max_C=70`, `criterios.delta_T_C=20` |
| Sin tuberías de enfriamiento | `tuberias=[]` |
| T del agua / separación / diámetro de un circuito | `tuberias.0.T_agua_C=10`, `tuberias.0.separacion_m=0.75`, `tuberias.0.diametro_m=0.032` |
| Período de circulación del agua | `tuberias.0.desde_h=0`, `tuberias.0.hasta_h=96` (horas desde la colocación) |

Para un cambio permanente, edita el valor en el YAML. El archivo marca cada dato
como `[repo]` (tiene fuente) o `[SUPUESTO]` (valor provisional).

### Espesor o geometría de la fundación

La geometría **no** está en el YAML: sale del IFC. Hay dos caminos:

1. **Bonsai:** editar `geometry/foundation.ifc` y guardarlo. Es el camino BIM.
2. **Código:** editar `VERTIDAS_FOUNDATION` en `bim/foundation.py`
   (`MAPA:geometria-espesores`; los campos son nombre, id, inicio_h, T, hormigón,
   **z_base, altura**, n_lados, radios, rotación). Si cambias la altura de una vertida,
   **sube también el `z_base` de las de encima**. Después genera un IFC
   **nuevo**, sin pisar el editado en Bonsai, y úsalo:

   ```powershell
   .venv\Scripts\python.exe scripts\make_foundation.py --salida geometry\foundation_variante.ifc
   .venv\Scripts\python.exe scripts\pipeline_e07.py --set ifc=../geometry/foundation_variante.ifc
   ```

   Usa un `malla.paso_z_m` que divida los nuevos espesores. Si no, la interfaz
   entre vertidas cae a mitad de voxel y el error de volumen por vertida sube.

## 4. Código legado (no lo uses para cambiar el caso)

Estos archivos están marcados con `# [LEGADO]` en la primera línea. Siguen en el
repo porque los usan tests de entregas anteriores o demos antiguas, pero **el
caso base y el visor E08 no pasan por ellos**:

| Archivo | Qué era | Reemplazo actual |
|---|---|---|
| `thermal/solver1d.py` | solver 1D nodal (E01) | `thermal/voxel.py` |
| `thermal/solver_nd.py`, `thermal/verification.py` | envoltorio de verificación (E05) | `thermal/voxel.py` |
| `thermal/vertidas.py` | primer simulador de vertidas (E07) | `thermal/etapas.py` |
| `thermal/material.py`, `configs/hormigon_M1.json` | material en JSON (E07) | `hormigones` en el YAML |
| `bim/voxel_ifc.py` | primer voxelizador IFC (E07) | `bim/voxelizador.py` |
| `bim/voxelizacion.py` | voxelización analítica (E04) | `bim/voxelizador.py` |
| `configs/e08.json` | plan JSON antiguo del visor | `configs/e08_demo.yaml` |

## 5. Documentación por entrega

E11: `docs/e11.md` y `scripts/demo_e11.py`: snapshot real, serie de borde,
simulación de 48 h, exportación VTK y clipping PyVista con núcleo térmico.

`docs/guia_estudio.md` (E01–E02), `docs/guia_e04.md` y `docs/e04_e05.md`
(solver y bordes), `docs/e06.md`, `docs/e07_e08.md` (pipeline, hidratación,
clima, preguntas E07), `docs/e08.md` (comandos de la demo).
