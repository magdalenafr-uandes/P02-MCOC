# Ensayo de la defensa · Grupo 1

Usar las cifras de la tabla verificada de la campaña. Identificar al comienzo los supuestos de capacidad, disponibilidad de protecciones y pesos de escenarios.

| Tiempo acumulado | Tema | Qué debe quedar claro |
| --- | --- | --- |
| 0:30 | Decisión | Abrir con el resultado: EPS 200 mm y hormigón a 12 °C cumple en 15,92 h con 0% de excedencia en malla fina, pero con margen de 0,18 °C y sin convergencia de malla demostrada. Ninguno de los 10 planes originales cumple. |
| 1:10 | Datos | Vincular el IFC, la fuente Q(t) y los tres bloques meteorológicos con el modelo. Justificar por qué las dos curvas M1 se trataron como escenarios. |
| 2:05 | Método | Mostrar activación y cambio de bordes. Explicar el balance explícito, la restricción temporal y la superficie a 25 mm. |
| 2:50 | Riesgo | Recorrer una fila real. Explicar por qué superar los dos límites en la misma fila sigue siendo una sola falla. |
| 4:00 | Comparación | Los 10 planes originales fallan por diferencial (P conjunta 75–100%). Aclarar el tiempo físico de colocar y el alcance de la búsqueda. |
| 4:50 | Control adicional | EPS 200 mm desde la colocación y mezcla a 12 °C bajan el diferencial bajo 20 °C en los 6 escenarios. EPS 100 mm a 12 °C se descartó porque cruzó el límite al refinar la malla. |
| 5:40 | Mecanismo | Leer las curvas y el campo crítico. Distinguir el instante de máxima temperatura del instante de máximo diferencial. |
| 6:20 | Verificación | Dar el efecto observado de malla, paso de integración y frecuencia de registro. Decir sin redondear que el diferencial del candidato sube al refinar (19,44 → 19,82 °C). |
| 7:00 | Cierre | Repetir la decisión con su salvedad y lo que hay que confirmar en obra (suministro a 12 °C, EPS disponible). |

## Preguntas para repartirse antes del ensayo

- **¿Por qué no se pueden promediar las temperaturas de los escenarios antes de evaluar?** La falla se determina de forma binaria por corrida. Promediar primero puede ocultar excedencias y altera el evento ponderado.
- **¿Qué pasaría si la diferencia por malla cruzara un límite?** La clasificación quedaría indeterminada hasta refinar. Presentar el valor y el margen sin redondear.
- **¿Por qué la vertida única dura aunque se active de golpe?** La simulación idealiza la activación. El cronograma físico usa el volumen del IFC dividido por la capacidad. Se prueba también activación sucesiva dentro de la misma operación continua.
- **¿Por qué el caso antiguo de E12 dio otros máximos?** La referencia histórica usó el archivo de calor anterior, otro inicio y una configuración de métricas distinta. La evidencia de defensa se calcula con los insumos y criterios actuales.
- **¿Qué respaldo tiene el 5%?** Es el umbral docente aplicado al conjunto discreto de escenarios. Los pesos son hipótesis y se estudia su sensibilidad. La aceptación térmica tampoco calcula probabilidad mecánica de fisuración.
- **¿Qué se haría ante una lectura inesperada?** Confirmar sensor y ambiente, comparar ambos indicadores contra las trayectorias, y decidir con el responsable técnico si se ajusta la próxima colocación o protección.
- **¿Por qué recomiendan un plan con 0,18 °C de margen?** Es el único control evaluado que cumple en todas las mallas calculadas y en los 6 escenarios. Lo presentamos como candidato condicionado: el diferencial sube al refinar y no demostramos convergencia. Antes de ejecutar habría que refinar más o sumar margen (más aislación o mezcla más fría).
- **¿Por qué se descartó EPS 100 mm a 12 °C si también pasaba en barrido?** En malla fina, SS/ERA5 2025 dio 20,15 °C. Con esa sola falla, P conjunta ≥ 25%.
