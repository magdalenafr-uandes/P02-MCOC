# Progreso de la defensa final · P02-MCOC, Grupo 1

Actualizado el 16 de noviembre de 2026 · America/Santiago.

**Paso actual:** 1 de 10, fijar los datos constructivos del cronograma. Se revisaron las tres pautas y se contrastaron con el repositorio. La campaña de simulaciones para la defensa sigue pendiente.

**Para retomar:** confirmar la hora de inicio del jueves 19, la capacidad de colocación en m³/h, la simultaneidad, las esperas mínimas y los controles disponibles. Pedir al grupo el respaldo de esos datos o registrar los supuestos con su fuente y el efecto que deberá evaluarse. Con eso, calcular la duración de cada vertida y cerrar el paso 1. Los pasos 2 a 4 pueden prepararse en paralelo.

## Decisión que debe sostener la defensa

Elegir el plan de menor duración entre los evaluados cuya probabilidad conjunta de superar **70 °C de temperatura máxima o 20 °C de diferencial** sea **≤ 5%** bajo un modelo de incertidumbre declarado. Medir la duración desde el inicio común hasta el fin de la última colocación, incluidas las esperas. Informar el enfriamiento posterior por separado.

- **E13, miércoles 18 de noviembre.** Llevar una corrida completa de vertida única, el repositorio ejecutable, los datos trazables, verificación inicial y hasta tres consultas. Si una corrida queda bloqueada, llevar el error reproducible y el último caso funcional.
- **Defensa, jueves 19 de noviembre.** Reservar 7 minutos para la exposición y 5 para las preguntas. Entregar el PDF con respaldo, el SHA de defensa y la evidencia precalculada disponible sin internet.
- **F01.** El enunciado dice viernes 20 y E13 indica un traslado al lunes siguiente. Confirmar el plazo vigente en Canvas y coordinar la aprobación del Centro de Escritura. Conservar el SHA de defensa y documentar cualquier corrección posterior.

## Avances confirmados

| Avance | Verificación y evidencia | Pendiente relacionado |
| --- | --- | --- |
| `93c1bc8` · E12 determinista documentado | El [informe E12](proyecto/docs/e12.md) y su [resumen](proyecto/docs/evidencia_e12/resumen.json) identifican el commit de la corrida `b26c103`, los insumos, máximos y balance. | Es evidencia histórica. Usó el inicio del 27 de noviembre, los datos anteriores de calor y el diferencial por vertida. Recalcular para la defensa. |
| `4bde04f` · Visores y enfriamiento integrados | Se verificaron las suites de Python, las 23 pruebas del visor y una solicitud de cálculo al servidor Python de la demo. E08 permite elegir circuitos del YAML o circuitos automáticos con caudal configurable. | Confirmar qué enfriamiento estará disponible y fijar criterios comparables para todos los planes. |
| `b863beb` · Carga del caso base en E08 | La prueba HTTP comprobó que se puede seleccionar y ejecutar el caso base desde un plan alternativo. En el visor local se comprobó que seguía disponible la corrida restaurada de 168 h y que el perfil base cargaba cinco vertidas y 48 h. | La campaña de defensa debe configurar explícitamente **336 h** desde el inicio común. |
| `5ef8f5e` · Nuevos datos de calor | La copia y el archivo entregado tienen SHA-256 `182b4a500dd02060b89dc452f007a379c7ab6cdc569e67de59a04c00d3497956`. Pasaron 259 pruebas del proyecto y 5 de la CLI raíz. La curva activa `M2_22A` da **35,4 K** de elevación adiabática con las propiedades del caso. [Datos](proyecto/data/hidratacion/source_terms.txt) · [Metadatos](proyecto/data/hidratacion/metadata.json) · [Gráfico](proyecto/results/figures/fuente_calor_medida.png) | Confirmar qué significan `M1–M4` y las campañas `SS` y `22A`. El archivo identifica menor confianza para `22A`. La elección actual del YAML no fija la mezcla ni los pesos de la defensa. |
| Diagnóstico de la defensa | Se leyeron las tres pautas y se inspeccionaron el [YAML base](proyecto/configs/e07_caso_base.yaml), [el solver](proyecto/src/mcplan/thermal/etapas.py) y las fechas de los archivos meteorológicos. El solver ya expone `delta_T_C` global y una métrica por vertida. El YAML aún parte el 27 de noviembre a las 04:00. | Conectar la métrica oficial a la comparación, cerrar los insumos del nuevo inicio y producir resultados de defensa. |
| 16 de noviembre · Registro inicial | Se comprobó que los diez pasos están numerados, los siete enlaces locales existen y los cinco commits citados están disponibles. | Mantener el registro al día después de cada avance verificado o bloqueo. |

## Secuencia de trabajo y cómo verificar cada paso

| Paso | Estado | Acción | Evidencia para cerrarlo |
| --- | --- | --- | --- |
| **1. Cronograma y recursos** | **En curso** | Fijar hora del 19 de noviembre, capacidad, simultaneidad, esperas y controles. Calcular inicios, fines, duraciones y retiros. | Tabla que conserva geometría, volumen y recursos. Cada duración tiene cálculo y dato o supuesto trazable. |
| **2. Hidratación** | Parcial | Completar la comparabilidad de las ocho curvas, decidir cuáles son admisibles y justificar cinética, interpolación y cola. | Gráfico, unidades, integral de cada curva y justificación de material y cinética. Documentar si se usa una curva completa común a todas las vertidas de una realización. |
| **3. Clima** | Pendiente | Preparar y congelar historias para Taltal desde el nuevo inicio. Preservar coherencia entre temperatura, viento y radiación. | Archivos con huella, sitio, fuente, fecha, zona, unidades y cobertura comprobada. El pronóstico del 12 llega al 27 de noviembre y el respaldo 2025, desplazado un año, comienza el 26 de noviembre. Evaluarlos para la nueva ventana antes de usarlos. |
| **4. Métricas y extracción** | Parcial | Conectar la métrica global del solver a la comparación. Extraer máximos con hora y ubicación. Conservar el diferencial por vertida para diagnóstico. | Prueba que distingue el máximo global del máximo por vertida, verifica el dominio activo, la superficie a 25 mm y la comparación en el mismo instante. Revisar que la frecuencia de registro capture los máximos. |
| **5. Vertida única y costo** | Pendiente | Ejecutar una operación continua equivalente al volumen total. Documentar la aproximación térmica de activación y contabilizar duración física. Medir costo de una corrida. | Configuración, resultado completo, balance, máximos, tiempo de ejecución y SHA. Si se agrupan sólidos del IFC, comprobar el volumen y la coherencia de circuitos y bordes. |
| **6. Familia de planes y pesos** | Pendiente | Fijar alternativas construibles, rango y paso de búsqueda. Declarar curvas, clima, pesos y dependencias antes de comparar. | Catálogo versionado, pesos no negativos que suman uno y justificación de supuestos. Una misma familia de escenarios se usa en todos los planes. |
| **7. Verificación numérica** | Pendiente para la defensa | Recuperar un caso conocido verificable, comprobar balance y comparar dos mallas y dos pasos temporales por separado. | Tabla de diferencias para ambas métricas y efecto sobre la clasificación. Refinar los casos cuyo margen pueda cambiar la decisión o declararlos indeterminados. |
| **8. Campaña y selección** | Pendiente | Ejecutar y guardar una fila por plan y escenario. Calcular marginales y unión. Revisar sensibilidad a los pesos y horizonte. | Filas reproducibles con peso, máximos, ubicaciones, horas e indicadores. Tabla agregada con vertida única, propuesta y alternativas competitivas más rápida y más lenta cuando existan. Elegir el menor tiempo factible entre los evaluados o documentar que ninguno cumple. |
| **9. Evidencia y control en obra** | Pendiente | Preparar cronogramas, curvas con umbrales, cortes comparables, duración vs. riesgo, plan de sensores y contingencias. Congelar SHA e insumos. | Resultados que se abren sin conexión y comandos verificables para un caso y para la comparación. |
| **10. PDF y ensayo** | Pendiente | Armar presentación con respaldo y ensayar exposición y preguntas. | PDF revisado, exposición de hasta 7 minutos y todos los integrantes preparados para explicar física, verificación, riesgo y recomendación. |

Para el paso 4, calcular en cada instante `T_max_activo(t) − T_min_superficie_25mm(t)` y luego maximizar en el tiempo. Para el paso 8, una fila falla si supera cualquiera de los dos límites y cuenta una vez aunque supere ambos. Evaluar el 5% con valores sin redondear. Usar 14 días desde el inicio común y extender si quedan máximos tardíos o temperaturas crecientes, informando ambos horizontes.

Las consultas prioritarias del taller son la capacidad y simultaneidad admisibles, el significado de las curvas y campañas, y el fundamento para usar Arrhenius con los datos nuevos.

## Relevo entre sesiones

- **Punto de partida en Git.** Al iniciar este registro, `main` local apuntaba a `5ef8f5e` y la referencia local `origin/main` a `93c1bc8`. La estrategia de publicación y el umbral de uso quedaron por confirmar. Al retomar, comprobar `git status --short --branch` y `git log -5 --oneline`. Verificar rama y commit en GitHub cuando se haga la publicación.
- **Entradas de planificación.** Pauta de defensa «Pregunta que deben responder», «E13 — Miércoles: taller de consultas y cierre técnico» y «F01 — Artículo académico final». Se recibieron como adjuntos del chat. Este registro conserva los requisitos que afectan la ejecución. Si cambian, registrar el cambio y la fuente.
- **Corridas previas.** Verificar SHA, identidad de los datos, definición de métricas, horizonte y parámetros antes de reutilizarlas. Mantener la evidencia validada y repetir solo las corridas afectadas por un cambio de insumos, código o criterio.
- **Corridas de la campaña.** Registrar por corrida el identificador, estado, configuración, versión del código, insumos y ruta de resultados. Si se interrumpe una campaña, reanudar desde la primera corrida pendiente o fallida con esos mismos insumos. Comprobar que sus resultados estén completos antes de marcarla como terminada.
- **Antes de pausar o entregar.** Actualizar el paso actual, los bloqueos y la próxima acción. Anotar rama, commit, estado de publicación y enlace de GitHub cuando exista. Registrar el motivo de la pausa y el estado del aviso por correo si se solicitó.

### Formato para registrar cada avance

Copiar este formato al completar un avance o detectar un bloqueo. Actualizar también el estado del paso en la tabla.

```text
Fecha y paso
Estado: pendiente, en curso, bloqueado o verificado
Cambio y resultado
Insumos y decisiones: versiones, parámetros y supuestos relevantes
Verificación: comando o comprobación, resultado observado y criterio de aceptación
Evidencia: ruta relativa, identificador de corrida y commit cuando existan
Pendiente o bloqueo: qué falta y de qué depende
Siguiente acción concreta
```

Registrar verificaciones parciales a medida que se obtienen. Marcar un paso como verificado cuando exista la evidencia de cierre indicada en su fila.
