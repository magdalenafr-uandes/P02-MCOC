# Progreso de la defensa final · P02-MCOC, Grupo 1

Actualizado el 16 de noviembre de 2026 · America/Santiago.

**Paso actual:** 7 y 8 de 10. Terminó el piloto de vertida única. Están en curso las comprobaciones espacial y temporal y la comparación de 48 escenarios. Los insumos del cronograma y los pesos son provisionales, con autorización del usuario para avanzar bajo supuestos explícitos.

**Para retomar:** comprobar qué corridas terminaron en `proyecto/results/defensa` y el resultado de `unica / M1_SS / era5_2025` en los niveles `cribado`, `fino`, `temporal` y `registro`. Luego resolver los planes competitivos y generar las tablas, figuras y presentación.

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
| **1. Cronograma y recursos** | Verificado bajo supuestos | Inicio 19 de noviembre a las 04:00, una línea de 40 m³/h, sin simultaneidad y espera mínima provisional de 0 h. Moldaje común, opción de manta del catálogo y sin tuberías. | El IFC suma 636,775 m³. El cronograma continuo da 15,919 h; las esperas de 3 y 6 h por interfaz dan 27,919 y 39,919 h. La prueba verifica conservación de volumen, duración y espera. |
| **2. Hidratación** | Verificado para el modelo provisional | Usar `M1_SS` y `M1_22A` como dos modelos del identificador M1 del IFC, con la curva completa común a todas las vertidas en cada escenario. Fuente por edad, `Ea_J_mol = 0`. | El usuario indicó que no hay antecedentes adicionales. Se mantienen las ocho curvas trazables. `M1_SS` integra 88,1 MJ/m³ y `M1_22A` 61,2 MJ/m³; la comparabilidad entre campañas sigue siendo una hipótesis. El lector usa Q = 0 tras el registro. |
| **3. Clima** | Verificado para el horizonte configurado | Tres análogos ERA5 de las mismas fechas de 2023–2025. Pronóstico del 16 de noviembre con final hasta el 1 de diciembre y cola ERA5 2025 como contraste. | Cada análogo contiene 480 horas continuas de temperatura, viento y radiación, en America/Santiago. El cargador comprobó la cobertura desde el 19 para 336 h. |
| **4. Métricas y extracción** | Verificado en prueba dirigida | Extraer máximos globales con hora y ubicación. Conservar el diferencial por vertida para diagnóstico. | Un caso de dos vertidas comprueba que el diferencial global usa extremos simultáneos y devuelve la cara a 25 mm. Queda evaluar el intervalo de registro con una corrida real. |
| **5. Vertida única y costo** | Piloto verificado | Ejecutar la operación continua, primero con activación térmica conjunta y después con activación sucesiva dentro de una operación del mismo tiempo físico. | Piloto `unica / M1_SS / era5_2025`, 336 h y 91,3 s. Máxima 54,913 °C, diferencial global 44,191 °C a las 147 h, cara fría x− a 10,72 °C. La métrica global detectó incumplimiento en esta realización. |
| **6. Familia de planes y pesos** | Fijado antes de comparar | Una operación continua en dos representaciones térmicas, esperas de 3 y 6 h, cada caso con y sin manta de 50 mm. Dos curvas M1 cruzadas con tres climas. | Catálogo en `configs/defensa.yaml`. Pesos hipotéticos 0,75/0,25 por menor confianza de 22A, sensibilidad 0,50/0,50 y 1/3 por clima análogo consecutivo. Producto por independencia supuesta. El pronóstico se usa como contraste sin peso. |
| **7. Verificación numérica** | En curso | Recuperar un caso conocido verificable, comprobar balance y comparar dos mallas y dos pasos temporales por separado. | Tabla de diferencias para ambas métricas y efecto sobre la clasificación. Refinar los casos cuyo margen pueda cambiar la decisión o declararlos indeterminados. |
| **8. Campaña y selección** | En curso | Ejecutar y guardar una fila por plan y escenario. Calcular marginales y unión. Revisar sensibilidad a los pesos y horizonte. | Filas reproducibles con peso, máximos, ubicaciones, horas e indicadores. Tabla agregada con vertida única, propuesta y alternativas competitivas más rápida y más lenta cuando existan. Elegir el menor tiempo factible entre los evaluados o documentar que ninguno cumple. |
| **9. Evidencia y control en obra** | Pendiente | Preparar cronogramas, curvas con umbrales, cortes comparables, duración vs. riesgo, plan de sensores y contingencias. Congelar SHA e insumos. | Resultados que se abren sin conexión y comandos verificables para un caso y para la comparación. |
| **10. PDF y ensayo** | Pendiente | Armar presentación con respaldo y ensayar exposición y preguntas. | PDF revisado, exposición de hasta 7 minutos y todos los integrantes preparados para explicar física, verificación, riesgo y recomendación. |

Para el paso 4, calcular en cada instante `T_max_activo(t) − T_min_superficie_25mm(t)` y luego maximizar en el tiempo. Para el paso 8, una fila falla si supera cualquiera de los dos límites y cuenta una vez aunque supere ambos. Evaluar el 5% con valores sin redondear. Usar 14 días desde el inicio común y extender si quedan máximos tardíos o temperaturas crecientes, informando ambos horizontes.

Las consultas prioritarias del taller son la capacidad y simultaneidad admisibles, el significado de las curvas y campañas, y el fundamento para usar Arrhenius con los datos nuevos.

### Registro de ejecución

- Rama de trabajo `codex/defensa-final`, derivada de `main` en `a54090e`. La pausa solicitada se dispara con **10% o menos** restante de la ventana de 5 horas. La publicación debe verificar el SHA remoto antes de enviar el reporte por correo.
- [Configuración](proyecto/configs/defensa.yaml) y [ejecutor](proyecto/scripts/defensa.py). Desde la raíz, `proyecto/.venv/Scripts/python.exe proyecto/scripts/defensa.py --solo-cronograma` genera la tabla física. Para el piloto usar `--plan unica --curva M1_SS --clima era5_2025`. Para la familia completa usar `--procesos 4`. Los filtros se pueden repetir y el nivel se elige con `--nivel cribado|fino|temporal|registro`.
- Los resultados de trabajo se escriben en `proyecto/results/defensa`. Cada corrida completa se guarda de forma atómica con una clave del caso, clima, IFC, curva y código. Al repetir el comando se reutilizan las filas compatibles. La tabla de escenarios incluye verificaciones por caso y la agregada aparece cuando el conjunto del plan está completo.
- Descargas de [Open-Meteo](https://open-meteo.com/en/docs/historical-weather-api), sitio Wayra/Taltal, coordenadas solicitadas −24,95283, −70,004838. Huellas cortas de los análogos `f80608501d04`, `6ba580bb17f3` y `f28fb0e4c608`. Huella del [pronóstico](https://open-meteo.com/en/docs) `4634e11ee380`. Las URLs, unidades y marcas de descarga están en `proyecto/data/weather/defensa_*/metadata.json`.
- Pasaron las cuatro pruebas dirigidas de defensa. Cubren cronograma, ubicación del diferencial global, doble excedencia en una sola fila y clasificación exacta en 5% y 5,004%.
- El piloto calculó y guardó la corrida completa. La exportación inicial falló por una variable con el mismo nombre que la función que reconstruye las tareas. Se corrigió y se comprobó con dos procesos que se escriben los JSON y el CSV, se activa la extensión de horizonte y se reanuda con cero corridas pendientes cuando los insumos coinciden. Pasaron 263 pruebas del proyecto y 5 de la CLI raíz.
- [Fundamento y reproducción](proyecto/docs/defensa.md). Para pausar la campaña, crear `proyecto/results/defensa/PAUSAR` vacío. El ejecutor guarda las corridas en curso y deja las restantes pendientes.

## Relevo entre sesiones

- **Punto de partida en Git.** Al iniciar este registro, `main` local apuntaba a `5ef8f5e` y la referencia local `origin/main` a `93c1bc8`. Al retomar, comprobar `git status --short --branch` y `git log -5 --oneline`. Verificar la rama y el commit en GitHub cuando se haga la publicación.
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
