# Ensayo de la defensa · Grupo 1

Usar las cifras de la tabla verificada de la campaña. Identificar al comienzo los supuestos de capacidad, disponibilidad de protecciones y pesos de escenarios.

| Tiempo acumulado | Tema | Qué debe quedar claro |
| --- | --- | --- |
| 0:30 | Decisión | Presentar EPS 200 mm y hormigón a 12 °C como candidato condicionado. D = 15,92 h con los recursos supuestos. La matriz fina da 0% observado en seis realizaciones y la confirmación singular a 0,20 m deja 0,18 °C de margen. Ninguno de los diez planes originales cumple. |
| 1:10 | Datos | Vincular el IFC, la fuente Q(t) y los tres bloques meteorológicos con el modelo. Justificar por qué las dos curvas M1 se trataron como escenarios. |
| 2:05 | Método | Mostrar activación y cambio de bordes. Explicar el balance explícito, la restricción temporal y la superficie a 25 mm. |
| 2:50 | Riesgo | Recorrer una fila real. Explicar por qué superar los dos límites en la misma fila sigue siendo una sola falla. |
| 4:00 | Comparación | Los 10 planes originales fallan por diferencial (P conjunta 75–100%). Aclarar el tiempo físico de colocar y el alcance de la búsqueda. |
| 4:50 | Control adicional | EPS 200 mm en caras superiores y laterales desde la colocación y mezcla a 12 °C dan un diferencial bajo 20 °C en seis escenarios finos de activación conjunta. La activación sucesiva se comprobó en barrido. EPS 100 mm a 12 °C cruzó el límite al refinar. |
| 5:40 | Mecanismo | Leer las curvas y el campo crítico. Distinguir el instante de máxima temperatura del instante de máximo diferencial. |
| 6:20 | Verificación | Distinguir el efecto de la malla, el paso de integración y la frecuencia de registro. Mostrar cómo sube el diferencial (19,44 → 19,82 °C). La comparación con el límite usa los valores sin redondear. |
| 7:00 | Cierre | Repetir la decisión con su salvedad y lo que hay que confirmar en obra (suministro a 12 °C, EPS disponible). |

## Ensayo con el PDF abierto

Reparto sugerido para la primera pasada: Juan Pablo abre y cubre las páginas 1–3; Magdalena presenta las páginas 4–6; Mauricio explica las páginas 7–9 y cierra. Confirmar el reparto con el grupo. Las páginas 10–14 se reservan para preguntas.

1. Abrir el PDF y las tablas guardadas sin conexión. Hacer una pasada de corrido con cronómetro y anotar el tiempo acumulado al final de las páginas 3, 6 y 9. Procurar cerrar entre 6:40 y 7:00 para tener margen en las transiciones.
2. Dedicar 5 minutos a preguntas. Un integrante hace una pregunta a otro y un tercero comprueba la cifra o el supuesto en las páginas de respaldo. Rotar para que todos practiquen una respuesta técnica.
3. Hacer otra pasada si superan 7:00 o si se confunde el 0% de la matriz fina con la confirmación de una sola fila a 0,20 m. Registrar los tiempos reales y la corrección en [progreso.md](../../progreso.md).

| Registro a completar en el ensayo | Tiempo real | Observación |
| --- | --- | --- |
| Fin página 3 · objetivo 2:05 | | |
| Fin página 6 · objetivo 4:50 | | |
| Fin página 9 · máximo 7:00 | | |
| Preguntas · 5:00 | | |

## Preguntas para repartirse antes del ensayo

- **¿Por qué no se pueden promediar las temperaturas de los escenarios antes de evaluar?** La falla se determina de forma binaria por corrida. Promediar primero puede ocultar excedencias y altera el evento ponderado.
- **¿Qué pasaría si la diferencia por malla cruzara un límite?** La clasificación quedaría indeterminada hasta refinar. Presentar el valor y el margen sin redondear.
- **¿Por qué la vertida única dura aunque se active de golpe?** La simulación idealiza la activación. El cronograma físico usa el volumen del IFC dividido por la capacidad. Se prueba también activación sucesiva dentro de la misma operación continua.
- **¿Por qué el caso antiguo de E12 dio otros máximos?** La referencia histórica usó el archivo de calor anterior, otro inicio y una configuración de métricas distinta. La evidencia de defensa se calcula con los insumos y criterios actuales.
- **¿Qué respaldo tiene el 5%?** Es el umbral docente aplicado al conjunto discreto de escenarios. Los pesos son hipótesis y se estudia su sensibilidad. La aceptación térmica tampoco calcula probabilidad mecánica de fisuración.
- **¿Qué se haría ante una lectura inesperada?** Confirmar sensor y ambiente, comparar ambos indicadores contra las trayectorias, y decidir con el responsable técnico si se ajusta la próxima colocación o protección.
- **¿Por qué recomiendan un plan con 0,18 °C de margen?** Es el único control evaluado que cumple en todas las mallas calculadas y en los 6 escenarios. Lo presentamos como candidato condicionado: el diferencial sube al refinar y no demostramos convergencia. Antes de ejecutar habría que refinar más o sumar margen (más aislación o mezcla más fría).
- **¿Por qué se descartó EPS 100 mm a 12 °C si también pasaba en barrido?** En malla fina, SS/ERA5 2025 dio 20,15 °C. Con esa sola falla, P conjunta ≥ 25%.
- **¿Cómo sostienen 15,92 h con preenfriamiento?** Con 636,775 m³ y 40 m³/h, 15,92 h es la cota física de una línea. El suministro debe llegar a 12 °C desde el inicio y mantener el caudal. Si retrasa la primera colocación, se suma la espera. Los 155,2 kW son extracción térmica ideal, antes de pérdidas y sin dimensionar el equipo.
- **¿Qué se comprobó a 0,20 m?** Solo SS/ERA5 2025, que dio 19,8215 °C. El 0% observado proviene de la matriz de seis filas a 0,25 m. En activación sucesiva se analizaron seis filas en barrido.
