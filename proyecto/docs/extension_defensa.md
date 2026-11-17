# Búsqueda local de una alternativa térmica · defensa P02-MCOC

**Estado al 17 de noviembre de 2026.** El estudio extendido tiene 35 corridas verificadas y cero filas pendientes. El grupo presentará **EPS 200 mm con colocación a 12 °C** como candidato condicionado. La matriz fina de activación conjunta dio 0% de excedencia en los seis escenarios ponderados. La comprobación adicional de una fila a 0,20 m dejó un margen de **0,178 °C**, con convergencia espacial todavía sin demostrar. El barrido inicial de diez planes conserva su conclusión y se documenta aparte. [Comparación base](defensa.md) · [Confirmación fina](#confirmación-fina)

## Qué se cambió

Se mantuvieron IFC, volumen de 636,775 m³, una línea de 40 m³/h, inicio común 19-nov-2026 04:00 America/Santiago, propiedades y curvas M1, pesos 75/25 (sensibilidad 50/50) e historias ERA5. No se agregaron tuberías ni se cambió mezcla, capacidad o umbrales.

Se fijó una familia adicional antes de los pilotos: EPS 100, 150, 200 y 300 mm a 18 °C; EPS 100 y 200 mm a 12 °C. La capa EPS tiene k = 0,035 W/(m·K), continuidad ideal y cubre caras superiores/laterales desde colocación, incluso después del desmolde. No se agrega bajo la fundación ni se corta el contacto térmico con el suelo. Se mantiene durante el horizonte simulado; no se ha validado un retiro brusco posterior.

El mínimo persistente estaba en x− de la primera vertida, cerca del suelo. Aumentar únicamente espesor a 18 °C dejó diferenciales mayores que 20 °C en el piloto SS / ERA5 2024. Reducir la temperatura de colocación disminuye la temperatura máxima del núcleo respecto del suelo; la aislación reduce la pérdida en las caras expuestas.

## Restricción constructiva del preenfriamiento

A 12 °C, el plan supone suministro de hormigón ya acondicionado disponible desde el inicio común y capaz de sostener 40 m³/h. Enfriar 6 K el volumen completo requiere idealmente ρ cₚ V ΔT = 8,894 GJ de extracción térmica (2.471 kWh térmicos), equivalente a 155,2 kW térmicos durante el suministro. Son mínimos ideales sin pérdidas; no potencia eléctrica ni dimensionamiento de una planta. La disponibilidad debe confirmarse. Si el enfriamiento retrasa la primera colocación, ese retraso se suma a D y hay que rehacer el cronograma y clima; no puede ocultarse antes de t0.

D = V/r = 15,919 h es la cota inferior bajo esa capacidad y una sola línea. La activación conjunta idealiza esa operación. La activación sucesiva por sólidos conserva la duración física y se comprobó en los seis escenarios de barrido. Para una decisión de ejecución, queda por probar esa representación en malla fina y confirmar la capacidad de suministro.

## Criterios de verificación

1. Seis escenarios por control con máximos e indicadores marginales y unión exacta. Cero fallas es P_F = 0% del modelo discreto, no garantía de confiabilidad real.
2. 336 h de base; extensión a 672 h si hay señal tardía. Nuevas colas históricas ERA5 hasta 20-dic, sin modificar el prefijo de 480 horas usado antes. Ninguna repetición artificial del último día.
3. Sensibilidad espacial: 0,50×0,50×0,10 m; 0,50×0,50×0,05 m; 0,25×0,25×0,05 m. Mantener las mismas entradas por escenario. Si el refinamiento cruza 20 °C, no aceptar ese candidato.
4. Separar reducción del paso temporal y frecuencia de registro. Revisar balance energético y ubicación de máximos; aplicar el umbral sin redondear.
5. Comprobar la representación de colocación sucesiva sin esperas y el mismo D físico. No declarar un control disponible ni una medida de retiro validada sin evidencia.

## Reproducción sin nuevas simulaciones

Desde la raíz, extraer el ZIP en una carpeta de resultados vacía. Si ya hay resultados, conservarlos y comprobar sus claves antes de copiar.

```powershell
Expand-Archive -LiteralPath proyecto/docs/evidencia_extension_defensa/corridas.zip -DestinationPath proyecto/results/defensa_extension_larga
proyecto/.venv/Scripts/python.exe proyecto/scripts/explorar_defensa.py --estudio proyecto/configs/defensa_extension_clima.yaml --salida proyecto/results/defensa_extension_larga --plan eps200_T12 --nivel fino --horizonte-extendido 672 --procesos 1
```

El resultado esperado es **6 seleccionadas, 0 pendientes** y una tabla regenerada en la carpeta de salida. El modo de un proceso evita las colas de multiprocessing de Windows. Para pausar nuevos cálculos, crear `PAUSAR` en la carpeta de resultados. Para las tablas de la defensa, usar los JSON completos y los CSV publicados.

Los resultados anteriores se conservan en `docs/evidencia_defensa`. La extensión está en `docs/evidencia_extension_defensa` y los pilotos de 100 mm en `docs/evidencia_extension_pilotos`. El SHA de la campaña original es `fc95932` y el de la confirmación de la extensión es `aede6bf`.

## Registro histórico de la pausa · 17 de noviembre, 00:10

- **Punto 1, búsqueda:** terminado para la familia explorada. Solo aumentar EPS a 18 °C no resolvió el piloto. El suministro a 12 °C con EPS de 100 y 200 mm produjo candidatos en malla de barrido.
- **EPS 100 mm / 12 °C:** descartado. La malla fina dio 19,24495; 19,93820; **20,14980 °C** en los tres escenarios SS. La falla de ERA5 2025 ya aporta P_F ≥ 25% con pesos principales, o ≥ 16,67% con pesos alternativos. No puede aceptarse por haber dado cero fallas en barrido/cribado.
- **EPS 200 mm / 12 °C:** candidato provisional. Seis escenarios completos de barrido hasta 672 h, sin picos tardíos y P_T = P_Δ = P_F = 0% en ese nivel; peor Δ = 18,4003 °C. Cero fallas también bajo pesos 50/50, condicionado a los seis escenarios.
- **Sensibilidad de ese candidato, SS/ERA5 2025:** barrido 18,4003 °C; cribado 18,6343 °C; temporal 18,6361 °C; registro 18,6361 °C. Temperatura máxima de aproximadamente 49,64 °C. Al aumentar la frecuencia de registro también se duplicaron los pasos del integrador: estas dos últimas pruebas no aíslan por completo muestreo e integración. Son comprobaciones de estabilidad de la métrica, no una cota demostrada del error.
- **Pronóstico como contraste sin peso:** SS / EPS 200 / 12 °C dio Δ = 18,3440 °C a 672 h, sin señal tardía. No se añadió su peso al cálculo principal.
- **Activación sucesiva:** 5/6 escenarios de barrido completos, sin excedencia en esas filas; peor SS = 18,6347 °C. Falta 22A / ERA5 2025. No hay matriz completa de esta representación.
- **Punto 2, confirmación:** pendiente. No terminó ninguna de las seis filas finas del candidato de 200 mm ni la confirmación horizontal de 0,20 m. Sus procesos se interrumpieron por petición del usuario; no se guardó un resultado parcial como válido. No se afirma factibilidad confirmada ni mínimo factible.

Se conservaron **41 corridas completas nuevas**: 27 en el paquete extendido y 14 en pilotos. Los ZIP, huellas de insumos, claves/configuración, balance y diferencial simultáneo se verificaron. Residuo energético relativo máximo del paquete extendido: 9,04 × 10⁻¹⁶. Las 79 corridas históricas no se modificaron.

## Confirmación fina

Las ocho filas pendientes terminaron entre 01:21 y 01:50 del 17 de noviembre, con código 0 y horizonte cerrado. La temperatura máxima observada fue 49,64 °C. Se combinaron con las 27 corridas previas para un total de **35 corridas verificadas**, con residuo relativo máximo de 9,04 × 10⁻¹⁶.

| Fila EPS 200 / 12 °C | Δ [°C] | Tiempo [s] |
|---|---|---|
| fino SS / ERA5 2023 | 18,4703 | 550 |
| fino SS / ERA5 2024 | 19,2890 | 550 |
| fino SS / ERA5 2025 | **19,4409** | 426 (sola) |
| fino 22A / ERA5 2023 · 2024 · 2025 | 11,06 · 11,60 · 11,74 | 187 · 548 · 491 |
| confirmación 0,20 m, SS / ERA5 2025 | **19,8215** | 689 |
| sucesiva, barrido 22A / ERA5 2025 | 11,3878 | 70 |

- Matriz fina completa: P_T = P_Δ = P_F = 0 % con ambos juegos de pesos. Activación sucesiva: 6/6 en barrido, sin excedencias.
- **Salvedad de malla:** en SS/ERA5 2025, Δ sube con cada refinamiento horizontal: 18,634 (0,5 m) → 19,441 (0,25 m) → 19,822 °C (0,20 m). El último incremento (+0,38 °C por 0,05 m) es proporcionalmente mayor que el anterior (+0,81 °C por 0,25 m). Estas tres mallas dejan sin verificar el régimen asintótico y el valor convergido. El margen a 0,20 m es 0,18 °C. Ahí se cumple el límite de 20 °C para esa única fila.

## Si se amplía el estudio después de la defensa

Las ocho filas del corte histórico ya están completas. La decisión de la defensa es presentar el candidato con la salvedad de malla y conservar las corridas vigentes. Si se requiere validación adicional para obra, la prioridad es comprobar el escenario crítico con activación sucesiva y un refinamiento espacial que permita evaluar el margen, y confirmar suministro, protección y régimen de retiro. Las corridas interrumpidas reinician desde t0 y las completas compatibles se reutilizan por clave.
