# Guía E04 — Solver 2D/3D, condiciones de borde, fuentes y BIM

Preparación para la revisión oral del miércoles 28-oct (E04). Complementa
`guia_estudio.md` (1D, IFC, round-trip). Todo lo que aparece aquí se
reproduce con:

```powershell
.\proyecto\.venv\Scripts\python.exe -m pytest proyecto -q
.\proyecto\.venv\Scripts\python.exe proyecto\scripts\verification_2d_3d.py
.\proyecto\.venv\Scripts\python.exe proyecto\scripts\voxelize_foundation.py
```

## 0. Qué hay en el repo para E04 (mapa contra la rúbrica)

| Exigencia E04 | Dónde está | Evidencia |
|---|---|---|
| 2D | `src/mcplan/thermal/voxel.py` (`MallaVoxel` con 2 ejes) | `test_sinusoidal_exacta_converge_segundo_orden[2]`, `e04_convergencia_2d_3d.png` |
| 3D | mismo solver, 3 ejes | `test_sinusoidal_exacta_converge_segundo_orden[3]`, `e04_corte_3d.png` |
| Dirichlet | `dirichlet(T)` | tests sinusoidales y pared compuesta |
| Neumann | `neumann(q)`, `adiabatico()` | `test_neumann_flujo_impuesto_entrega_q_por_area`, `test_superficie_adiabatica_es_plano_de_simetria` |
| Robin | `robin(T_inf, h, R_extra)` | `test_robin_coincide_con_serie_analitica_de_pared`, `test_robin_signo_del_flujo_y_balance`, `test_aislacion_reduce_perdidas` |
| Fuente volumétrica | `SolverVoxel(..., fuente=q)` (escalar, campo o función de t) | `test_fuente_uniforme_adiabatica_eleva_temperatura_linealmente`, `test_fuente_variable_en_el_tiempo_y_por_celda` |
| Dos materiales | `MallaVoxel.desde_materiales` (media armónica) | `test_dos_materiales_estado_estacionario_resistencias_en_serie`, energía con materiales aleatorios |
| Estabilidad | `SolverVoxel.dt_max()` = min C/ΣG | `test_dt_max_*`, `test_inestabilidad_empirica_y_principio_del_maximo`, `e04_estabilidad.png` |
| BIM caso base | `geometry/foundation.ifc`, `Sin_nombre.blend`, `bim/voxelizacion.py` | `test_voxelizacion.py`, `e04_voxelizacion_foundation.png` |

El solver 1D de E01 (`solver1d.py`, malla de **nodos**) se mantiene como
referencia verificada. El solver nuevo usa malla de **centros de celda**,
porque es lo que entrega una voxelización de la geometría BIM.

## 1. Balance de un voxel (escribirlo en la pizarra)

Voxel `i` de lados Δx, Δy, Δz; volumen V = ΔxΔyΔz. Primera ley:

```text
(energía que se acumula) = (calor que entra por conducción) + (calor generado) + (calor que entra por el borde)

ρ cp V dT_i/dt = Σ_j G_ij (T_j − T_i) + q''' V + Q_borde
```

- `C_i = ρ cp V` [J/K]: capacidad térmica del voxel.
- `G_ij = k A_ij / d_ij` [W/K]: conductancia de la cara compartida.
  En x: A = ΔyΔz, d = Δx. En 2D se trabaja por metro de profundidad.
- 3D tiene 6 vecinos; 2D tiene 4.

Con malla uniforme y un solo material se divide por C_i:

```text
dT_i/dt = α [ (T_E − 2T_i + T_W)/Δx² + (T_N − 2T_i + T_S)/Δy² + (T_U − 2T_i + T_D)/Δz² ] + q'''/(ρ cp)
```

Es el Laplaciano en diferencias centradas. El balance y la ecuación diferencial
son la misma cosa, pero el balance sigue siendo válido cuando cambian el material, el borde o la aislación.

Euler explícito, con Fo = αΔt/Δx², en 3D y malla cúbica:

```text
T_i^{n+1} = (1 − 6 Fo) T_i^n + Fo (T_E + T_W + T_N + T_S + T_U + T_D)^n + Δt q'''/(ρ cp)
```

En código (`voxel.py`, `tasa_calor` y `resolver`):

```python
flujo = G * (T[b] - T[a])  # calor de la celda b hacia la a
Q[a] += flujo; Q[b] -= flujo  # lo que entra a una sale de la otra
...
T = T + dt * Q / C
```

Cada cara se procesa una vez y su flujo se suma a una celda y se resta a la otra. Por eso la energía se conserva al
redondeo de máquina, también con dos materiales. El test
`test_energia_se_conserva_con_bordes_adiabaticos` lo verifica con error relativo de 1e-12.

## 2. Estabilidad: derivación

En la actualización explícita el coeficiente de `T_i^n` es

```text
1 − Δt ΣG_i / C_i
```

Si es negativo, una celda más caliente que sus vecinos termina más fría que
ellos en el paso siguiente. Eso es una oscilación sin sentido físico que crece
con cada paso y viola el principio del máximo. Exigir que sea ≥ 0 da:

```text
Δt ≤ C_i / (Σ_j G_ij + G_borde,i)       → dt_max = min_i de lo anterior
```

Casos particulares (malla uniforme, un material, celda interior):

| Dim | ΣG/C | Límite |
|---|---|---|
| 1D | 2α/Δx² | Fo ≤ 1/2 (Schmidt) |
| 2D | 4α/Δx² | Fo ≤ 1/4 |
| 3D | 6α/Δx² | Fo ≤ 1/6 |
| general | 2α(1/Δx²+1/Δy²+1/Δz²) | αΔt Σ 1/Δ² ≤ 1/2 |

**Lo que hay que saber explicar:** el límite lo fija la celda con
**más conductancia por unidad de capacidad**:

- **Dirichlet de media celda.** La superficie está a Δx/2, así que G_b = 2kA/Δx,
  el doble de una cara interior. Una esquina 3D con tres caras Dirichlet
  tiene ΣG = 3·kA/Δx + 3·2kA/Δx y queda Δt ≤ Δx²/(9α), más estricto que
  Δx²/(6α). En 2D la esquina da Δx²/(6α) < Δx²/(4α). La figura
  `e04_estabilidad.png` muestra que usar Fo = 1/4 en 2D con este borde
  hace explotar la solución en las esquinas. El test correspondiente es
  `test_inestabilidad_empirica_y_principio_del_maximo`.
- **Robin.** Agrega G_b = 1/(Δx/(2kA) + 1/(hA)). Con h chico manda la celda
  interior; con h grande manda la esquina convectiva
  (`test_dt_max_dirichlet_y_robin_son_mas_estrictos`).
- **Dos materiales.** Manda el material con mayor α, o el voxel de interfaz.

Orden de magnitud con el hormigón de Ju y Lei: α ≈ 9,5·10⁻⁷ m²/s. Con
Δx = 0,1 m en 3D, Δt ≤ 0,01/(6·9,5·10⁻⁷) ≈ 1750 s ≈ 29 min. Con Δx = 0,05 m
baja a 7 min. **Refinar al doble cuesta 2³ veces más voxeles y 4 veces más pasos, es decir 32 veces más trabajo en 3D.**

Estabilidad no es precisión. Que el esquema no explote no significa que el
error sea chico. Por eso hay estudio de convergencia (§6).

## 3. Flujo y signos

- Convención del código: **positivo es calor que entra a la celda**.
- Ley de Fourier: q = −k ∇T. El calor va de caliente a frío.
  `G (T_j − T_i) > 0` cuando el vecino j está más caliente, así que i se calienta.
- Robin: `Q = G_b (T_inf − T_i)`. Si el hormigón está más caliente que el aire,
  Q < 0 y la estructura pierde calor (`test_robin_signo_del_flujo_y_balance`).
- Neumann: `q''` positivo significa calor entrando, por ejemplo radiación solar absorbida.
  En la norma matemática −k∇T·n = q_n con n hacia afuera hay un signo
  opuesto. Hay que decir siempre qué convención se usa.
- Balance global verificado: `E_final − E_inicial = Σ Q_borde·Δt + Σ q'''VΔt`
  al redondeo de máquina.

## 4. Superficies adiabáticas

Adiabática significa q'' = 0: no cruza calor. Se usa en tres casos:

1. **Plano de simetría.** Si la geometría, las cargas y los bordes son
   simétricos, el gradiente normal al plano es nulo. En la fundación octogonal
   se puede modelar la mitad o un cuarto con los planos de corte
   adiabáticos. El test `test_superficie_adiabatica_es_plano_de_simetria`
   lo demuestra: media losa con un borde adiabático da el mismo campo que
   la losa completa (error de 1e-10).
2. **Aislación muy buena** (aproximación de R → ∞).
3. **Borde lejano del suelo**, solo si se justifica que está suficientemente lejos.

La implementación es directa: si la cara es adiabática no se agrega
conductancia ni flujo. Ojo con no confundirla con Dirichlet.

## 5. Convección (Robin): cómo se implementa

Calor que sale del centro del voxel hacia el aire. Atraviesa resistencias en
serie: media celda de hormigón, luego moldaje o aislación, luego la película de aire.

```text
R_tot = (Δx/2)/(k A) + R''_extra/A + 1/(h A)        G_b = 1/R_tot
Q = G_b (T_inf − T_i)
```

En el código, `robin(T_inf, h, R_extra)`. Por ejemplo, una aislación de 50 mm con k = 0,04
da R''_extra = 0,05/0,04 = 1,25 m²K/W. Retirar el moldaje equivale a
cambiar R_extra en el tiempo, que es justo una decisión del plan de vertidas.

Validación: pared de espesor 2L con convección por ambas caras contra la
serie analítica de Incropera, θ/θᵢ = Σ Cₙ e^{−ζₙ² Fo} cos(ζₙx/L) con
ζₙ tan ζₙ = Bi. El error es menor a 0,05 °C a los 2 días
(`test_robin_coincide_con_serie_analitica_de_pared`).

**Error típico:** imponer T_aire como Dirichlet en la superficie. Eso equivale a
h → ∞ y fuerza la superficie a la temperatura del aire.

## 6. Verificación 2D/3D y convergencia

Caja de 1 m con Dirichlet 20 °C y perfil inicial 20 + 50·Πsin(πx/L). La
solución exacta decae como exp(−α Σ(π/L)² t). Resultado de
`verification_2d_3d.py`:

| n por eje | 2D error (3 d) | 3D error (1 d) |
|---|---|---|
| 8 | 1,80e-2 °C | 1,03e-1 °C |
| 16 | 4,71e-3 °C | 2,70e-2 °C |
| 32 | 1,19e-3 °C | 6,81e-3 °C |
| 64 | 2,98e-4 °C | — |

El error se divide por cerca de 4 al dividir Δx por 2. Eso es orden 2, como
corresponde a diferencias centradas.

## 7. Fuente volumétrica vs. flujo superficial (unidades)

| Concepto | Símbolo | Unidad | Dónde entra | Ejemplo |
|---|---|---|---|---|
| Fuente volumétrica | q''' | W/m³ | `+ q''' · V` en todas las celdas del material | calor de hidratación (W3) |
| Flujo superficial | q'' | W/m² | `+ q'' · A` solo en celdas de borde | radiación solar absorbida |
| Convección | h(T_inf − T) | W/m² | `+ G_b (T_inf − T)` en el borde | aire, viento |

- La convección **no** es una fuente: depende de la temperatura de la superficie y
  puede tener cualquier signo.
- Chequeo de unidades: Δt q'''/(ρ cp) = s·(W/m³)/(J/(m³K)) = K.
- Test: con todos los bordes adiabáticos y q''' uniforme, T = T₀ + q''' t/(ρ cp)
  exacto en todas las celdas. Es la curva de elevación adiabática.
  Por ejemplo, 150 W/m³ durante 7 días dan 150·604800/(2400·970) ≈ 39 °C.
- La fuente puede ser un campo por celda (solo en el hormigón, no en el suelo) o una
  función del tiempo. Eso deja preparada la hidratación.

## 8. Dos materiales

Cada voxel guarda sus propios k, ρ y cp (`material_id` → propiedades). En la
cara entre i y j el flujo cruza **dos medias celdas en serie**:

```text
R = (Δx/2)/(k_i A) + (Δx/2)/(k_j A)   ⇒   k_cara = 2 k_i k_j / (k_i + k_j)   (media armónica)
```

- La media aritmética sobreestima el paso de calor cuando un material es aislante.
  Con k→0 en un lado la armónica da 0, que es lo correcto.
- La capacidad C_i es la de cada voxel. El calor almacenado sigue a cada material.
- Validación: en la pared compuesta (k = 1 y k = 4) el flujo estacionario es
  ΔT/(L₁/k₁ + L₂/k₂) y el perfil lineal por tramos, con error de 1e-6
  (`test_dos_materiales_estado_estacionario_resistencias_en_serie`).
- Ya se usa hormigón sobre suelo (Ju y Lei: k_suelo = 1,39 W/mK,
  ρ = 1800, cp = 1273) en `e04_bordes_dominan.png`. Luego vendrán vertida
  nueva/vertida antigua, moldaje y aislación.

## 9. Por qué las condiciones de borde pueden dominar el resultado

Figura `e04_bordes_dominan.png`: sección de 3,3 m de hormigón sobre 2 m de
suelo, fuente constante de 150 W/m³ (ilustrativa, todavía no es hidratación),
7 días. Solo cambia la cara superior:

| Cara superior | T núcleo | T superficial | ΔT núcleo−sup |
|---|---|---|---|
| Adiabática | 56,3 °C | 57,0 °C | ≈ 0 |
| Robin h=10, T∞=20 | 55,4 °C | 31,9 °C | ≈ 23,5 °C |
| Robin + aislación 50 mm | 56,1 °C | 51,6 °C | ≈ 4,5 °C |
| Dirichlet 20 °C (error) | 54,8 °C | 22,8 °C | ≈ 32 °C |

Lectura:

- En un elemento masivo el **núcleo** casi no cambia: el tiempo de difusión
  L²/α ≈ 1,65²/9,5·10⁻⁷ s ≈ 33 días es mucho mayor que 7 días, así que el núcleo
  se comporta casi adiabático.
- La **superficie** y por lo tanto el **diferencial** (criterio de 20 °C)
  dependen casi exclusivamente del borde. Según la hipótesis, la misma estructura
  "cumple" o "no cumple".
- Por eso aislación, moldaje, hora de vertida y clima son variables de
  diseño. Una mala hipótesis de borde (Dirichlet = T_aire) sobrestima el
  diferencial.

## 10. Método de Schmidt (Anexo 4 ICH)

**Leer el anexo antes de la revisión.** Esta sección resume solo lo que
aparece en las guías del curso. El método de Schmidt es el explícito en
diferencias finitas con Fo = 1/2 en 1D:

```text
T_i^{n+1} = (1 − 2·½) T_i^n + ½ (T_{i−1} + T_{i+1})^n = (T_{i−1}^n + T_{i+1}^n)/2
```

La nueva temperatura es el promedio de los vecinos, lo que permite hacerlo a mano o gráficamente. Eso
fija Δt = Δx²/(2α). Es justo el borde de la estabilidad, por eso no tiene margen.
En 2D el análogo es Fo = 1/4 (promedio de 4 vecinos) y en 3D Fo = 1/6
(promedio de 6). Según la guía G05, el anexo indica que se aplica en 1D/2D/3D
con secuencia constructiva, aislación y otros materiales. Nuestro solver es
la generalización por balance (C/ΣG), que no obliga a Fo fijo y admite
bordes y materiales heterogéneos.

## 11. Avance BIM del caso base

- `geometry/foundation.ifc`: IFC4, octágono de 18 m entre caras, espesor 1,10 m
  en el borde y 3,30 m en el centro, pedestal de Ø 7 m × 1 m. Son 5 `IfcFooting`
  (Vertida_01..05) con el pset `UANDES_HormigonMasivo` (VertidaID, Inicio_h,
  TemperaturaColocacion_C, TipoHormigon, Moldaje, Aislacion,
  RetiroMoldaje_h). Fue editado en Bonsai en E02 (`docs/evidencia_e02/`).
- `Sin_nombre.blend`: archivo de Blender/Bonsai. **Para la revisión hay que abrirlo y mostrar
  el modelo y el árbol de propiedades.**
- **Nuevo en E04:** `bim/voxelizacion.py` lleva la fundación a la grilla del
  solver, asignando `vertida_id` por voxel según la regla del centro del voxel de la guía G04.
  `scripts/voxelize_foundation.py`:

| Δx | voxeles activos | e_V total |
|---|---|---|
| 0,40 m | 10 011 | 0,62 % |
| 0,20 m | 78 756 | 1,06 % |
| 0,10 m | 638 747 | 0,31 % |

  El error **total** es bajo, pero el error **por vertida** puede ser de 8 a 10 % en
  las vertidas 1–2. Pasa porque su espesor (0,55 m) no es múltiplo de Δz
  y la interfaz entre vertidas cae a mitad de voxel. **Conclusión de diseño:** usar
  un Δz que divida los espesores (0,55, 1,10 y 1,00 m), por ejemplo Δz = 0,05 m, o
  una malla anisótropa (el solver ya acepta Δx ≠ Δz).
- Pendiente para W3: leer las mallas trianguladas directamente desde el IFC
  (IfcOpenShell), activar las vertidas en el tiempo y llevar el `vertida_id` al solver.

## 12. Preguntas probables (respuesta corta)

- **¿Por qué la estabilidad no depende de la fuente?** La fuente no multiplica a
  T_i, así que no cambia el coeficiente (1 − ΔtΣG/C). Sí afecta la precisión.
- **¿Qué pasa si Δt > dt_max?** El coeficiente de T_i se vuelve negativo, aparecen
  oscilaciones damero que crecen geométricamente y se viola el principio del máximo.
  El solver lo rechaza con ValueError, salvo `verificar_estabilidad=False`.
- **¿Por qué centros de celda y no nodos?** Así sale de la voxelización. Cada
  voxel es un volumen de control con material propio, y los bordes quedan en
  las caras.
- **¿Cómo se trata el suelo?** Como segundo material modelado explícitamente,
  con Dirichlet a la temperatura del suelo profundo en una frontera lejana. La
  alternativa es una condición efectiva justificada.
- **¿Un borde Dirichlet conserva energía?** No. Entrega o extrae lo que haga
  falta para mantener T. El código lo contabiliza en `calor_borde_acumulado`.
- **¿Cómo se agrega radiación solar?** Como Neumann `q'' = a·G_solar`
  (absortividad × irradiancia), sumado a la convección en la misma cara.
  Se suman los dos flujos.

## 13. Checklist antes de la revisión

- [ ] `pytest proyecto -q` en verde, local y en GitHub Actions.
- [ ] Ejecutar `verification_2d_3d.py` y `voxelize_foundation.py` y abrir las figuras.
- [ ] Leer la sección de Schmidt del Anexo 4 del ICH.
- [ ] Abrir `Sin_nombre.blend` y `foundation.ifc` en Bonsai y tener las vertidas y el pset a la vista.
- [ ] Ensayar en pizarra: balance del voxel (§1), derivación de la estabilidad (§2), Robin
      con resistencias (§5) y la media armónica (§8).
- [ ] Declarar en Canvas el repositorio y el **SHA** del commit evaluado.
