# Progreso de la defensa final · P02-MCOC, Grupo 1

Actualizado el 16 de noviembre de 2026 · America/Santiago.

**Paso actual:** 8 de 10, en pausa. Se completaron 57 de 60 escenarios del barrido principal y quedaron archivadas 76 corridas verificadas contando las confirmaciones. Se alcanzó el 10% restante de la ventana de 5 horas y se guardaron las corridas ya iniciadas.

**Para retomar:** extraer las corridas archivadas, completar las tres filas de `unica / M1_22A` del nivel `barrido` y regenerar la comparación. Luego generar las gráficas finales, producir el PDF desde su fuente, revisar visualmente todas sus páginas y ensayar con el grupo.

## Corte del 16 de noviembre de 2026 · 19:07, America/Santiago

- El indicador de uso llegó al **10% restante** de la ventana de cinco horas. Se activó `PAUSAR` para detener el inicio de nuevas corridas. Los ejecutores que estaban activos terminaron sus corridas iniciadas y salieron.
- [Estado del paquete](proyecto/docs/evidencia_defensa/estado.json) · [Corridas reutilizables](proyecto/docs/evidencia_defensa/corridas.zip) · [Filas por escenario](proyecto/docs/evidencia_defensa/escenarios.csv) · [Riesgo por plan](proyecto/docs/evidencia_defensa/comparacion.csv). El empaquetado comprobó la integridad ZIP, el cierre de balance y que el diferencial corresponde a la resta de extremos simultáneos. Pasaron **264 pruebas del proyecto y 5 de la CLI raíz**.
- Los nueve planes con matriz de barrido completa tienen excedencia conjunta observada de **75–100%** con los pesos principales. Todos quedan descartados por el diferencial. Algunos horizontes permanecen abiertos a 420 h, por lo que su riesgo observado es una cota inferior. El décimo plan, vertida única sin manta, ya falla en las tres combinaciones `M1_SS` del barrido y en los seis casos del cribado con la malla de 0,05 m vertical. El contraste del pronóstico para vertida única con poliestireno y `M1_SS` dio **22,908 °C** de diferencial.
- Quedan exactamente tres combinaciones del barrido: `unica / M1_22A` con `era5_2023`, `era5_2024` y `era5_2025`. Falta publicar la conclusión con la tabla completa, generar las figuras finales y verificar el PDF. El guion y la fuente de la presentación están en `Archivos Extra/Defensa final`.
- La rama de publicación es `codex/defensa-final`. El commit de corte es el que añade esta sección. Para reanudar desde GitHub, extraer el ZIP en `proyecto/results/defensa` y retirar solo el marcador `PAUSAR` si está presente. Ejecutar desde la raíz:

  ```powershell
  proyecto/.venv/Scripts/python.exe proyecto/scripts/defensa.py --nivel barrido --plan unica --curva M1_22A --procesos 3
  proyecto/.venv/Scripts/python.exe proyecto/scripts/evidencia_defensa.py --nivel barrido --figuras "Archivos Extra/Defensa final/figuras"
  ```

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
| **7. Verificación numérica** | Referencia verificada | Comparar espacio, paso de integración y muestreo por separado. Refinar los candidatos cuyo margen pueda cambiar la decisión. | El diferencial del caso de referencia fue 43,673 °C en barrido, 44,191 °C en cribado y 44,940 °C en fino. En los tres casos excede 20 °C. Reducir el paso temporal o el intervalo de registro cambió menos de 0,007 °C. |
| **8. Campaña y selección** | En pausa · 57/60 | Ejecutar y guardar una fila por plan y escenario. Calcular marginales y unión. Revisar sensibilidad a los pesos y horizonte. | Nueve matrices completas en barrido. Las tres filas restantes pertenecen a la vertida única sin manta con `M1_22A`. La misma alternativa ya tuvo `P_T = 0%` y `P_F = 100%` en el nivel de cribado de 0,05 m vertical. |
| **9. Evidencia y control en obra** | Parcial | Preparar cronogramas, curvas con umbrales, cortes comparables, duración vs. riesgo, plan de sensores y contingencias. Congelar SHA e insumos. | Corte de vertida única verificado a 147 h. El documento técnico incluye un plan de control docente. Falta generar las gráficas de la familia y cerrar el paquete. |
| **10. PDF y ensayo** | Parcial | Armar presentación con respaldo y ensayar exposición y preguntas. | Fuente de la presentación con ocho diapositivas principales y dos de respaldo. Falta generar y revisar el PDF con los resultados completos. El ensayo requiere al grupo. |

Para el paso 4, calcular en cada instante `T_max_activo(t) − T_min_superficie_25mm(t)` y luego maximizar en el tiempo. Para el paso 8, una fila falla si supera cualquiera de los dos límites y cuenta una vez aunque supere ambos. Evaluar el 5% con valores sin redondear. Usar 14 días desde el inicio común y extender si quedan máximos tardíos o temperaturas crecientes, informando ambos horizontes.

Las consultas prioritarias del taller son la capacidad y simultaneidad admisibles, el significado de las curvas y campañas, y el fundamento para usar Arrhenius con los datos nuevos.

### Registro de ejecución

- Rama de trabajo `codex/defensa-final`, derivada de `main` en `a54090e`. La pausa solicitada se dispara con **10% o menos** restante de la ventana de 5 horas. La publicación debe verificar el SHA remoto antes de enviar el reporte por correo.
- [Configuración](proyecto/configs/defensa.yaml) y [ejecutor](proyecto/scripts/defensa.py). Desde la raíz, `proyecto/.venv/Scripts/python.exe proyecto/scripts/defensa.py --solo-cronograma` genera la tabla física. El caso de referencia usa `--plan unica --curva M1_SS --clima era5_2025`. Los filtros se pueden repetir y el nivel se elige con `--nivel barrido|cribado|fino|temporal|registro`.
- La malla original de 0,05 m vertical se conserva en `proyecto/results/defensa`. La cola inicial se dejó drenar con el archivo `PAUSAR` para priorizar la malla de 0,10 m vertical, que reduce el costo del barrido. Para completar la familia, usar `proyecto/.venv/Scripts/python.exe proyecto/scripts/defensa.py --salida proyecto/results/defensa_piloto_barrido --nivel barrido --procesos 3`. Los niveles espaciales conservan 0,50 m en horizontal salvo `fino`, que usa 0,25 m.
- Cada corrida completa se guarda de forma atómica con una clave del caso, clima, IFC, curva y código. Al repetir el comando se reutilizan las filas compatibles. Para consolidar, copiar solo los JSON de corridas del barrido a `proyecto/results/defensa` y ejecutar `proyecto/.venv/Scripts/python.exe proyecto/scripts/evidencia_defensa.py --nivel barrido --figuras "Archivos Extra/Defensa final/figuras"`. Añadir `--permitir-parcial` para un respaldo de avance.
- Descargas de [Open-Meteo](https://open-meteo.com/en/docs/historical-weather-api), sitio Wayra/Taltal, coordenadas solicitadas −24,95283, −70,004838. Huellas cortas de los análogos `f80608501d04`, `6ba580bb17f3` y `f28fb0e4c608`. Huella del [pronóstico](https://open-meteo.com/en/docs) `4634e11ee380`. Las URLs, unidades y marcas de descarga están en `proyecto/data/weather/defensa_*/metadata.json`.
- Pasaron las cuatro pruebas dirigidas de defensa. Cubren cronograma, ubicación del diferencial global, doble excedencia en una sola fila y clasificación exacta en 5% y 5,004%.
- El piloto calculó y guardó la corrida completa. La exportación inicial falló por una variable con el mismo nombre que la función que reconstruye las tareas. Se corrigió y se comprobó con dos procesos que se escriben los JSON y el CSV, se activa la extensión de horizonte y se reanuda con cero corridas pendientes cuando los insumos coinciden. Pasaron 263 pruebas del proyecto y 5 de la CLI raíz.
- [Fundamento y reproducción](proyecto/docs/defensa.md). Para pausar la campaña, crear `proyecto/results/defensa/PAUSAR` vacío. El ejecutor guarda las corridas en curso y deja las restantes pendientes.
- Verificación independiente de hidratación a 72 h en hormigón adiabático, con integración trapezoidal de Q: 52,89405531 °C tanto en el cálculo de referencia como en el solver, con error de 7,11 × 10⁻¹⁵ °C. En la corrida real de referencia, pasar de 15 a 7,5 minutos entre registros cambió el diferencial 0,0066 °C, y reducir a la mitad la fracción temporal lo cambió 0,0066 °C. El barrido a 0,10 m vertical dio 43,673 °C frente a 44,191 °C a 0,05 m; se mantuvo el incumplimiento. El balance relativo de ambos casos fue inferior a 3 × 10⁻¹⁶.
- [Corte térmico de referencia](Archivos%20Extra/Defensa%20final/figuras/corte_critico.png). Se reprodujo el campo del escenario `unica / M1_SS / era5_2025` a las 147 h y se comprobó la temperatura del punto caliente. El símbolo marca ese punto en el plano Y = 0 m.
- El piloto de la manta dio 25,431 °C de diferencial con `M1_SS / era5_2025` en el barrido, frente a 43,673 °C sin manta. Se agregó una extensión de dos planes con poliestireno de 100 mm del catálogo, uno con activación conjunta y otro sucesiva. Mantienen los insumos, pesos y duración física de la operación continua. La familia original de 48 corridas y las 12 de extensión quedan identificadas en el mismo YAML.
- Se comprobó que los tres análogos cubren tanto 336 como 420 h. El contraste con pronóstico aporta 307 h y completa las 29 h restantes del horizonte base con el análogo 2025.
- [Archivo de avance de las corridas](proyecto/docs/evidencia_defensa/corridas.zip) y [estado del conjunto](proyecto/docs/evidencia_defensa/estado.json). El ZIP contiene corridas completas del modelo con balance y métricas verificados. Si se retoma en otra máquina, extraerlo en `proyecto/results/defensa` y usar esa carpeta como `--salida` al reanudar. Retirar el archivo `PAUSAR` si está presente. La clave de reanudación normaliza finales de línea del código y los JSON meteorológicos. Se comprobó que una corrida del ZIP se reutiliza desde otra carpeta con **cero simulaciones pendientes**.
- Los dos primeros casos con poliestireno y activación conjunta dieron 22,430 °C con ERA5 2023 y 23,020 °C con ERA5 2024, ambos con `M1_SS`. La cara fría fue x− de la vertida 1. Se inició una confirmación del caso 2024 con 0,05 m vertical. Estos datos aún no cierran la clasificación de la familia completa.
- En el barrido ya están completos seis escenarios de `continua_manta`, `espera_3h_manta` y `unica_poliestireno`. Para cada plan hubo tres fallas, todas de `M1_SS` por diferencial. La suma ponderada da `P_T = 0%` y `P_delta = P_F = 75%`, o 50% con el reparto alternativo de curvas. Queda confirmar en resolución más fina los casos con menor margen sobre 20 °C y terminar las alternativas restantes.
- Confirmaciones a 0,05 m vertical: vertida única con manta, `M1_SS / era5_2025`, Δ máxima **25,618 °C**. Vertida única con poliestireno, `M1_SS / era5_2024`, Δ máxima **23,264 °C** frente a 23,020 °C en el barrido. La espera de 6 h sin manta y `M1_SS / era5_2023` dio **43,935 °C** en el barrido. Con esta última corrida, los diez planes tienen por lo menos una excedencia de `M1_SS`; eso aporta una cota inferior de 25% de riesgo conjunto en cada plan, al nivel en que se evaluó el caso. Es un descarte preliminar. Las probabilidades exactas por plan requieren cerrar las matrices por nivel.

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
