# Evaluar escenarios en el visor

El HTML incluye su biblioteca de gráficos para funcionar también con servidores
anteriores que solo publican la página. Si se modifica `visor_e08/analisis.js`,
ejecutar `scripts/compilar_visor.py`; `--check` verifica la sincronización.
La biblioteca sigue disponible por separado para sus pruebas unitarias.

## Indicadores y alcance

El panel superior distingue los picos de toda la corrida de los valores del
instante mostrado en la vista 3D. Incluye:

- Temperatura máxima, hora y vertida.
- Mayor diferencial **dentro de una misma vertida**, hora y pieza.
- Ventana entre la primera y última colocación programadas.
- Tiempo observado desde la última colocación hasta el final.

Los límites se leen de `criterios` del caso ejecutado. Se identifican como
criterios docentes: cumplirlos no certifica ausencia de fisuras ni seguridad
de las juntas. El diferencial usa la máxima de cada pieza menos la mínima
estimada en sus caras expuestas, a `profundidad_superficie_m` (25 mm en el caso
base). No resta temperaturas de dos vertidas distintas.

## Gráficos

1. Máximas por vertida, con límite configurado.
2. Diferencial interior–superficie por vertida, con límite configurado.
3. Sondas geométricas fijas del núcleo aproximado y borde lateral. Se muestran
   las coordenadas; el voxel elegido con clic se incorpora en violeta.
4. Comparación entre escenario actual y referencia, eligiendo máxima global
   o el mayor diferencial de las piezas en cada instante.

El selector de eje permite comparar por hora global o por edad de cada
vertida en los primeros tres gráficos. Con edades distintas no se dibuja una
única línea de tiempo actual sobre varias piezas. Las sondas se seleccionan
por geometría, no siguiendo al máximo térmico: el núcleo es la celda más
próxima al centroide de la pieza; el borde es una celda lateral expuesta de la
geometría final, a la cota más próxima al núcleo. Son aproximaciones geométricas,
no posiciones de sensores de obra.

## Colocaciones y juntas

La tabla desplegable informa los intervalos entre inicios, temperatura media,
máxima y de la sonda de núcleo de la pieza cronológicamente anterior. También
muestra la media de las celdas antiguas adyacentes a la nueva vertida y con
qué piezas estará en contacto. Se consulta el campo del evento de colocación,
antes del siguiente paso de cálculo. No se inventan valores fuera del horizonte
ni una precedencia térmica entre vertidas simultáneas.

El modelo incorpora cada vertida instantáneamente: no calcula duración de
bombeo, preparación de juntas, adherencia, armaduras, tensiones ni deslizamiento.
La tabla declara las juntas como **no evaluadas mecánicamente**.

## Comparar el caso actual con intervalos de 24 horas

Cuando se decida ejecutar esa comparación:

1. Ejecutar o recuperar el caso base y pulsar **Fijar actual como referencia**.
2. Cambiar solo los inicios a 0, 24, 48, 72 y 96 h; conservar los demás datos.
3. Ejecutar la variante y revisar tabla, curvas globales y curvas por edad.
4. Revisar advertencias sobre horizonte, edad final de la última vertida,
   malla, material, clima, fecha y protecciones. Una disminución de temperatura
   no determina por sí sola la mejor solución constructiva.

La referencia se conserva en `sessionStorage` de la pestaña, sin los campos
3D. **Guardar resumen JSON** permite conservarla y **Cargar referencia JSON**
acepta un resumen o un resultado con indicadores. Los cambios son diferencias
absolutas actual menos referencia, en K o h; no porcentajes de temperaturas
en Celsius.

## Resultados anteriores

`demo_e08.py --resultado ruta/resultado.json` abre una corrida guardada sin
resolver de nuevo la difusión. Si faltan indicadores, se reconstruyen a partir
de sus fotogramas, caso ejecutado y geometría IFC, verificando su huella y grilla.
Las superficies se recalculan para esos instantes. Se declara que los picos
están limitados al muestreo guardado. La reconstrucción no modifica el archivo
original. Una referencia antigua sin indicadores debe recuperarse de esta
manera y exportarse como resumen nuevo.

En corridas nuevas, las series de máximas y diferenciales usan los registros
del motor; las sondas usan los campos guardados. Ninguna serie constituye
una búsqueda continua entre pasos. Ocultar piezas y cambiar el corte siguen
siendo filtros visuales: no modifican los indicadores del dominio calculado.
