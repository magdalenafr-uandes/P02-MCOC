# Búsqueda local de una alternativa térmica · defensa P02-MCOC

Estado: **pausado por petición del usuario el 17-nov-2026 a las 00:10, America/Santiago**. Se detuvieron las simulaciones largas. Este documento no sustituye la conclusión del PDF congelado anterior: no hay aún una alternativa nueva aceptada en resolución final.

## Qué se cambió

Se mantuvieron IFC, volumen de 636,775 m³, una línea de 40 m³/h, inicio común 19-nov-2026 04:00 America/Santiago, propiedades y curvas M1, pesos 75/25 (sensibilidad 50/50) e historias ERA5. No se agregaron tuberías ni se cambió mezcla, capacidad o umbrales.

Se fijó una familia adicional antes de los pilotos: EPS 100, 150, 200 y 300 mm a 18 °C; EPS 100 y 200 mm a 12 °C. La capa EPS tiene k = 0,035 W/(m·K), continuidad ideal y cubre caras superiores/laterales desde colocación, incluso después del desmolde. No se agrega bajo la fundación ni se corta el contacto térmico con el suelo. Se mantiene durante el horizonte simulado; no se ha validado un retiro brusco posterior.

El mínimo persistente estaba en x− de la primera vertida, cerca del suelo. Aumentar únicamente espesor a 18 °C dejó diferenciales mayores que 20 °C en el piloto SS / ERA5 2024. Reducir la temperatura de colocación disminuye la temperatura máxima del núcleo respecto del suelo; la aislación reduce la pérdida en las caras expuestas.

## Restricción constructiva del preenfriamiento

A 12 °C, el plan supone suministro de hormigón ya acondicionado disponible desde el inicio común y capaz de sostener 40 m³/h. Enfriar 6 K el volumen completo requiere idealmente ρ cₚ V ΔT = 8,894 GJ de extracción térmica (2.471 kWh térmicos), equivalente a 155,2 kW térmicos durante el suministro. Son mínimos ideales sin pérdidas; no potencia eléctrica ni dimensionamiento de una planta. La disponibilidad debe confirmarse. Si el enfriamiento retrasa la primera colocación, ese retraso se suma a D y hay que rehacer el cronograma y clima; no puede ocultarse antes de t0.

D = V/r = 15,919 h es una cota inferior bajo esa capacidad y una sola línea. Un candidato que cumpla y alcance esa cota es el más rápido en esta familia bajo los recursos declarados; no prueba optimalidad frente a otra capacidad. La activación conjunta idealiza la operación de 15,919 h; la sensibilidad con activación sucesiva se conserva como comprobación pendiente.

## Cómo se verificará

1. Seis escenarios por control con máximos e indicadores marginales y unión exacta. Cero fallas es P_F = 0% del modelo discreto, no garantía de confiabilidad real.
2. 336 h de base; extensión a 672 h si hay señal tardía. Nuevas colas históricas ERA5 hasta 20-dic, sin modificar el prefijo de 480 horas usado antes. Ninguna repetición artificial del último día.
3. Sensibilidad espacial: 0,50×0,50×0,10 m; 0,50×0,50×0,05 m; 0,25×0,25×0,05 m. Mantener las mismas entradas por escenario. Si el refinamiento cruza 20 °C, no aceptar ese candidato.
4. Separar reducción del paso temporal y frecuencia de registro. Revisar balance energético y ubicación de máximos; aplicar el umbral sin redondear.
5. Comprobar la representación de colocación sucesiva sin esperas y el mismo D físico. No declarar un control disponible ni una medida de retiro validada sin evidencia.

## Reproducción

Desde la raíz:

```powershell
proyecto/.venv/Scripts/python.exe proyecto/scripts/explorar_defensa.py --estudio proyecto/configs/defensa_extension_clima.yaml --salida proyecto/results/defensa_extension_larga --plan eps200_T12 --horizonte-extendido 672 --procesos 1
proyecto/.venv/Scripts/python.exe proyecto/scripts/explorar_defensa.py --estudio proyecto/configs/defensa_extension_clima.yaml --salida proyecto/results/defensa_extension_larga --plan eps200_T12 --nivel fino --horizonte-extendido 672 --procesos 1
proyecto/.venv/Scripts/python.exe proyecto/scripts/resumir_extension_defensa.py
```

El modo de un proceso evita colas de multiprocessing de Windows. Las claves permiten reanudar sin repetir corridas completas compatibles. Para pausar nuevos cálculos, crear `PAUSAR` en la carpeta de resultados. Los JSON completos son la fuente de la evidencia; no aceptar archivos temporales.

Los resultados anteriores permanecen intactos en `docs/evidencia_defensa`. La extensión se conserva aparte en `docs/evidencia_extension_defensa`; los pilotos y confirmaciones de 100 mm están en `docs/evidencia_extension_pilotos`. El usuario autorizó publicar el cierre en `codex/defensa-final` y enviar correo; comprobar el SHA remoto en el registro de sesión.

## Resultado observado al pausar

- **Punto 1, búsqueda:** terminado para la familia explorada. Solo aumentar EPS a 18 °C no resolvió el piloto. El suministro a 12 °C con EPS de 100 y 200 mm produjo candidatos en malla de barrido.
- **EPS 100 mm / 12 °C:** descartado. La malla fina dio 19,24495; 19,93820; **20,14980 °C** en los tres escenarios SS. La falla de ERA5 2025 ya aporta P_F ≥ 25% con pesos principales, o ≥ 16,67% con pesos alternativos. No puede aceptarse por haber dado cero fallas en barrido/cribado.
- **EPS 200 mm / 12 °C:** candidato provisional. Seis escenarios completos de barrido hasta 672 h, sin picos tardíos y P_T = P_Δ = P_F = 0% en ese nivel; peor Δ = 18,4003 °C. Cero fallas también bajo pesos 50/50, condicionado a los seis escenarios.
- **Sensibilidad de ese candidato, SS/ERA5 2025:** barrido 18,4003 °C; cribado 18,6343 °C; temporal 18,6361 °C; registro 18,6361 °C. Temperatura máxima de aproximadamente 49,64 °C. Al aumentar la frecuencia de registro también se duplicaron los pasos del integrador: estas dos últimas pruebas no aíslan por completo muestreo e integración. Son comprobaciones de estabilidad de la métrica, no una cota demostrada del error.
- **Pronóstico como contraste sin peso:** SS / EPS 200 / 12 °C dio Δ = 18,3440 °C a 672 h, sin señal tardía. No se añadió su peso al cálculo principal.
- **Activación sucesiva:** 5/6 escenarios de barrido completos, sin excedencia en esas filas; peor SS = 18,6347 °C. Falta 22A / ERA5 2025. No hay matriz completa de esta representación.
- **Punto 2, confirmación:** pendiente. No terminó ninguna de las seis filas finas del candidato de 200 mm ni la confirmación horizontal de 0,20 m. Sus procesos se interrumpieron por petición del usuario; no se guardó un resultado parcial como válido. No se afirma factibilidad confirmada ni mínimo factible.

Se conservaron **41 corridas completas nuevas**: 27 en el paquete extendido y 14 en pilotos. Los ZIP, huellas de insumos, claves/configuración, balance y diferencial simultáneo se verificaron. Residuo energético relativo máximo del paquete extendido: 9,04 × 10⁻¹⁶. Las 79 corridas históricas no se modificaron.

## Confirmación fina (17-nov, 01:21–01:50)

Las ocho filas pendientes terminaron con código 0 y horizonte cerrado; ninguna supera 70 °C (T_max ≤ 49,64 °C). Se combinaron con las 27 corridas previas: **35 corridas verificadas**, residuo relativo máximo 9,04 × 10⁻¹⁶.

| Fila EPS 200 / 12 °C | Δ [°C] | Tiempo [s] |
|---|---|---|
| fino SS / ERA5 2023 | 18,4703 | 550 |
| fino SS / ERA5 2024 | 19,2890 | 550 |
| fino SS / ERA5 2025 | **19,4409** | 426 (sola) |
| fino 22A / ERA5 2023 · 2024 · 2025 | 11,06 · 11,60 · 11,74 | 187 · 548 · 491 |
| confirmación 0,20 m, SS / ERA5 2025 | **19,8215** | 689 |
| sucesiva, barrido 22A / ERA5 2025 | 11,3878 | 70 |

- Matriz fina completa: P_T = P_Δ = P_F = 0 % con ambos juegos de pesos. Activación sucesiva: 6/6 en barrido, sin excedencias.
- **Salvedad de malla:** en SS/ERA5 2025, Δ sube con cada refinamiento horizontal: 18,634 (0,5 m) → 19,441 (0,25 m) → 19,822 °C (0,20 m). El último incremento (+0,38 °C por 0,05 m) es proporcionalmente mayor que el anterior (+0,81 °C por 0,25 m), así que no hay régimen asintótico que permita extrapolar un valor convergido. El margen a 0,20 m es 0,18 °C. EPS 200 / 12 °C **cumple en todas las mallas calculadas**, pero no se puede afirmar que el valor convergido quede bajo 20 °C.

## Retomar sin repetir toda la búsqueda

> Actualización 17-nov 01:50: las ocho filas de `pendientes.json` ya están completas (sección anterior). Lo que sigue aplica solo si se agregan filas nuevas.

Primero revisar `docs/evidencia_extension_defensa/pendientes.json`. El siguiente cálculo prioritario es solo SS/ERA5 2025 en fino para EPS 200 / 12 °C. Retirar el marcador `PAUSAR` únicamente cuando se quiera reanudar. No lanzar simultáneamente todas las confirmaciones como en esta sesión: medir primero una corrida. Si esa fila falla, replantear el control antes de completar las demás.

```powershell
proyecto/.venv/Scripts/python.exe proyecto/scripts/explorar_defensa.py --estudio proyecto/configs/defensa_extension_clima.yaml --salida proyecto/results/defensa_extension_larga --plan eps200_T12 --nivel fino --curva M1_SS --clima era5_2025 --horizonte-extendido 672 --procesos 1
```

Las corridas interrumpidas no conservan estado temporal: cada fila pendiente reinicia desde t0. Las filas completas compatibles sí se reutilizan. Mantener pendiente la recomendación y actualizar el PDF solo después de cerrar la verificación y los supuestos de suministro/protección.
