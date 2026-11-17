# Progreso de la defensa final · P02-MCOC, Grupo 1

Actualizado el 17 de noviembre de 2026 · 01:55 · America/Santiago.

**Paso actual:** 8 de 10. **Cálculos completos** (17-nov, 01:50): las 8 filas pendientes terminaron y el paquete extendido tiene 35 corridas verificadas. EPS 200 mm / 12 °C cumple en todas las mallas calculadas (P_F = 0 % en fino), pero con salvedad de convergencia: Δ SS/ERA5 2025 = 19,44 °C a 0,25 m y 19,82 °C a 0,20 m. Falta decidir la recomendación con esa salvedad y actualizar el PDF (paso 9).

**Para retomar (vigente, 01:55):** ver la entrada del 17-nov 01:55 al final. No quedan corridas pendientes en `pendientes.json`. Siguiente acción: decidir con el grupo cómo presentar EPS 200 / 12 °C (cumple con margen 0,18 °C sin convergencia demostrada) y actualizar el PDF y el guion.

**Para retomar (histórico):** (17-nov, 00:45) la confirmación fina SS/ERA5 2025 de EPS 200 / 12 °C está lista para ejecutarse en Windows con un doble clic en `Confirmar EPS200 fino.cmd` (carpeta Cloude de Mauricio); ver la entrada de las 00:45. Además: leer `proyecto/docs/extension_defensa.md` y `proyecto/docs/evidencia_extension_defensa/pendientes.json`. Reanudar primero solo EPS 200 / 12 °C, SS / ERA5 2025 en fino, retirando PAUSAR cuando se autorice continuar. No repetir las 41 filas completas ni el barrido histórico. La recomendación y actualización del PDF quedan pendientes.

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
| **8. Campaña y selección** | Verificado · 60/60, sin plan factible | Ejecutar y guardar una fila por plan y escenario. Calcular marginales y unión. Revisar sensibilidad a los pesos y horizonte. | Diez matrices completas; P_T = 0%, P_F observada = 75–100%, o 50–100% con pesos 50/50. Los horizontes abiertos impiden declarar capturados todos los picos; sus cotas inferiores ya descartan los planes. |
| **9. Evidencia y control en obra** | Verificado bajo supuestos | Preparar cronogramas, curvas con umbrales, cortes comparables, duración vs. riesgo, plan de sensores y contingencias. Congelar SHA e insumos. | Figuras finales generadas, corte verificado a 147 h, informe con tabla completa y sensibilidad. Insumos/resultados congelados en `fc95932`; controles de obra son propuesta docente, no medida validada. |
| **10. PDF y ensayo** | PDF verificado; ensayo bloqueado por participación del grupo | Armar presentación con respaldo y ensayar exposición y preguntas. | PDF de 12 páginas: 8 principales (7 min propuestos), 4 de respaldo. Renderizado e inspeccionado; huella en `revision_pdf.json`. El ensayo y la comprensión individual siguen pendientes. |

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

## 16 de noviembre de 2026 · 20:29, America/Santiago · Paso 8

Estado: verificado para el descarte dentro del modelo provisional; no se encontró plan factible.

- Cambio: se retomó `codex/defensa-final` en `7c626c0`, con árbol limpio; se restauraron las 76 corridas del ZIP y se ejecutaron solo las tres pendientes. `unica / M1_22A` dio Δ = 34,790; 33,715; 33,249 °C para ERA5 2023, 2024 y 2025, respectivamente (127–159 s por corrida).
- Verificación: `defensa.py --nivel barrido --plan unica --curva M1_22A --procesos 3`; después `evidencia_defensa.py --nivel barrido --figuras "Archivos Extra/Defensa final/figuras"`. Resultado: **79 corridas verificadas, cero pendientes de barrido**; claves/insumos, balance, diferencial simultáneo e integridad ZIP comprobados por el empaquetador.
- Evidencia: `proyecto/docs/evidencia_defensa/{estado.json,corridas.zip,escenarios.csv,comparacion.csv}`. No cambió el solver ni sus entradas; las 76 corridas anteriores mantienen vigencia.
- Resultado: sin aislación P_F = 100%; con manta/poliestireno P_F observada = 75%. La sensibilidad 50/50 da 100% y 50%, respectivamente. Todos superan 5%. Algunos horizontes a 420 h siguen abiertos: sus probabilidades son cotas inferiores, suficientes para descartar, pero no máximos definitivos de horizontes mayores.
- Pruebas: la ejecución inicial encontró temporales no escribibles; con `--basetemp=.pytest_cache/tmp_defensa_cierre` pasó raíz (5). Proyecto terminó con dos fallos HTTP por WinError 10013 del sandbox; se repite la suite completa con acceso a localhost antes del commit. No se considera aprobado ese intento fallido.
- Uso consultado: 96% restante al empezar, 95% antes de la campaña, 93% tras completarla.
- Siguiente acción: cerrar figuras y documento técnico, revisar el PDF y registrar el ensayo grupal como pendiente de participación humana.
- Verificación resuelta antes de guardar: la suite completa de proyecto terminó con código 0 (264 pruebas) al permitir localhost; raíz pasó 5/5. Repetir las tres pendientes informó **0 por ejecutar**, comprobando reutilización. Queda 91% de la ventana.

## 16 de noviembre de 2026 · 20:39, America/Santiago · Pasos 9 y 10

Estado: paso 9 verificado bajo los supuestos declarados; paso 10 verificado en PDF, bloqueado en ensayo grupal.

- Cambio: se generaron cronogramas, duración–riesgo y curvas comparables con umbrales; se conservó el corte de referencia vigente. El informe técnico incluye las diez alternativas, sensibilidad 50/50, balance y refinamiento por nivel, comandos y pendientes humanos. Se amplió el respaldo de la presentación sin alterar las ocho diapositivas principales.
- Verificación: `defensa.py --nivel barrido --procesos 3` informó **60 seleccionadas, 0 por ejecutar**. El empaquetador volvió a comprobar 79 corridas y cero faltantes. La fuente PDF se ejecutó con el Python/ReportLab del runtime instalado; Poppler renderizó las páginas. Se inspeccionaron las 12 páginas, se corrigió un glifo de ecuación y la leyenda, y se renderizaron/revisaron otra vez las páginas afectadas. Pypdf comprobó 12 páginas, identificación del proyecto, SHA de evidencia y extracción sin caracteres de sustitución. Compilación de ambas fuentes Python correcta.
- Resultado: PDF disponible en `Defensa final/Defensa final - Grupo 1.pdf`; fuente editable en `Archivos Extra/Defensa final/generar_presentacion.py`. No se afirma ensayo real. `revision_pdf.json` conserva SHA-256 y comprobaciones. El SHA congelado de los resultados es `fc95932a4fd3d08652679052c342b63e71858b9c`; el commit de publicación posterior añade figuras, PDF y documentación.
- Pruebas antes de guardar: raíz 5/5; suite completa del proyecto 264/264, código 0 con localhost permitido y temporales dentro de `.pytest_cache`. No se cambió física ni insumos del solver.
- Uso después de este avance: **89% restante**. El cierre no se debe al límite: el trabajo autónomo previsto quedó terminado; el ensayo, las confirmaciones de obra y el significado de SS/22A requieren al grupo/profesor. Los horizontes abiertos quedan registrados como limitación, sin afirmar picos definitivos.
- Punto exacto para retomar: abrir el PDF y `Archivos Extra/Defensa final/guion.md`, ensayar 7 minutos con los tres integrantes y registrar tiempo real y respuestas. Confirmar supuestos de obra y campañas; si se pide una alternativa factible, acordar un control de cara fría y simularlo con los mismos escenarios antes de recomendarlo. Confirmar también el plazo del artículo en Canvas.
- Publicación: pendiente de push del commit que contiene este reporte; comprobar SHA remoto y enviar aviso por Gmail al finalizar.

### Publicación comprobada · 16 de noviembre de 2026, 20:43 · America/Santiago

- Push real completado: `7c626c0..8d123d8` en `origin/codex/defensa-final`.
- `git ls-remote origin refs/heads/codex/defensa-final` devolvió `8d123d8fdb50d3e25526b3a3190402bd8f8f9ba0`, igual a HEAD. Enlace: https://github.com/magdalenafr-uandes/P02-MCOC/tree/codex/defensa-final .
- Se guarda esta constancia en un commit documental de cierre y se vuelve a comprobar el remoto antes del correo. El correo identificará el SHA final del reporte, además del SHA congelado `fc95932` de la campaña.
- Incidencia de herramientas: la revisión automática rechazó `git restore` sobre el ZIP regenerado por riesgo de descartar cambios sin respaldo. No se ejecutó; se conservó el ZIP verificado en el commit publicado. No quedó trabajo bloqueado por esa revisión.
- Cierre por dependencia humana: ensayo grupal y confirmación de supuestos; no por falta de saldo. No se declara terminada la defensa ni validado un plan factible. Próxima acción exacta: ensayo con el PDF y guion, y registrar tiempos y observaciones en este archivo. El correo se envía después de comprobar el commit final; su resultado se comunica en el chat.
- Comprobación adicional del paquete: diez planes × seis escenarios ERA5 = 60 filas principales y ZIP íntegro de 79 corridas. Un conteo exploratorio por nivel dio 61 porque incluía el contraste de pronóstico de peso cero; al seleccionar los climas principales se verificó la matriz 60/60. No se eliminó el contraste ni se alteraron pesos.
- Saldo al iniciar el cierre: **88%** de la ventana de cinco horas.
- Antes del commit documental final: suites raíz y proyecto aprobadas nuevamente (5 y 264, código 0). Se conserva la evidencia anterior; no hay fallos de pruebas sin resolver.

## 16 de noviembre de 2026 · 21:40, America/Santiago · Reapertura local de pasos 8–9

Estado: en curso; nueva búsqueda solicitada por el usuario. Instrucción posterior: **no subir nada**. No hacer push ni enviar correos/archivos; los avances y commits serán exclusivamente locales.

- Inicio en `codex/defensa-final`, `ec94f89`, sin cambios rastreados. La carpeta `tmp/` previa se conserva.
- Saldo inicial: 99% restante de la ventana de cinco horas.
- Diagnóstico: poliestireno de 100 mm falla por diferencial de 22,4–23,3 °C, con mínimo en cara x− de la vertida 1 junto al suelo; algunos picos son tardíos. El espesor no corta el intercambio conductivo con el suelo.
- Familia fijada antes del piloto: EPS 100/150/200/300 mm a 18 °C y EPS 100/200 mm a 12 °C, activación conjunta, aislación superior/lateral desde colocación. Se mantienen IFC, caudal 40 m³/h, recursos de colocación, curvas M1 y pesos, sin tuberías. Preenfriamiento y disponibilidad de protección son supuestos que requieren confirmación; no se afirma ejecución aprobada.
- Implementación: `configs/defensa_extension.yaml` y `scripts/explorar_defensa.py`. Reutiliza solver y métricas existentes sin modificarlos; JSON completos y claves en `results/defensa_extension`. Se conservan intactas las 79 corridas anteriores.
- Comprobación dirigida: pasó `test_extension_defensa.py`, verificando controles efectivos del plan IFC, mantenimiento después del desmolde y ausencia de aislación bajo el suelo. Pilotos seleccionados antes de comparar: seis controles con M1_SS / ERA5 2024, nivel barrido, 336 h y extensión automática a 448 h dentro de cobertura real disponible.
- Siguiente acción: completar seis escenarios de los candidatos prometedores; confirmar espacio/tiempo/muestreo y activación sucesiva, capturar picos y declarar indeterminado si falta evidencia.
- Pilotos terminados: EPS 100/150/200/300 mm a 18 °C dieron Δ = 23,0199 / 22,3320 / 21,9992 / 21,7614 °C; ninguno cumple ese escenario. EPS 100/200 mm a 12 °C dieron 19,2022 / 18,2382 °C. Son candidatos, todavía no planes aceptados; el de 200 mm sigue con horizonte abierto a 448 h.
- Verificación del cambio antes del primer commit local: suite raíz 5/5, proyecto 264/264 y prueba nueva de integración 1/1; comprobación dirigida adicional de integración/mapa 3/3. Saldo consultado después del primer avance: 96% restante.
- Siguiente acción: completar las seis combinaciones de EPS 100 mm a 12 °C y contrastar con resolución fina. Conserva 15,919 h de colocación; el costo/recursos de preenfriamiento no se han confirmado.
- Nuevo pedido: enviar correo al terminar; queda reautorizado solo el correo final, se mantiene **sin push**.
- Matriz inicial de EPS 100 mm / 12 °C: seis escenarios completos en barrido y ningún indicador de excedencia; dos conservan horizonte abierto a 448 h. No se marca aceptado.
- Se descargaron colas ERA5 reales 2023/2024/2025 hasta el 20-dic en carpetas nuevas `data/weather/defensa_extension_*`. Los 480 registros previos de temperatura, viento y radiación coinciden exactamente; se conserva el prefijo original y su SHA en metadatos. `configs/defensa_extension_clima.yaml` fija estas entradas para todas las confirmaciones extendidas.
- Se inició barrido completo con extensión hasta 672 h, cribado a 0,05 m vertical y tres confirmaciones finas de M1_SS en el horizonte anterior. La resolución fina había costado 1254 s en la referencia histórica; se mide el costo nuevo antes de ampliar más.
- Saldo consultado antes de las confirmaciones largas: 91% restante.
- Incidencia: el pool de confirmación fina de EPS 200 / 12 °C falló al iniciar con WinError 6 / BrokenProcessPool. No generó filas aceptables. Se añadió modo realmente secuencial sin multiprocessing y pausa mediante marcador PAUSAR; se reanudan los tres climas en procesos independientes, guardando cada realización completa. No cambió el solver, las métricas ni los pesos.
- Confirmación fina inicial de EPS 100 mm / 12 °C, SS / ERA5 2024: Δ = 19,9382 °C, frente a 19,2022 °C en barrido. Margen de solo 0,0618 °C; no se recomienda ese control como robusto con la evidencia disponible.
- EPS 200 mm / 12 °C completó seis escenarios de barrido con extensión real hasta 672 h: cero fallas, horizontes cerrados y Δ máxima 18,4003 °C. Sigue pendiente la confirmación fina; no se declara aún verificado el punto 2.
- Suite de proyecto tras el cambio: 264 pruebas pasaron y una prueba CLI falló por timeout de 120 s bajo carga; el proceso terminó con código 0 pero la comprobación del tiempo falló. No se modifica el timeout para aprobarla. Se repite esa prueba y se ejecutará de nuevo la suite completa antes del siguiente commit. Raíz pasó 5/5.
- El empaquetador inicial detectó la diferencia de serialización 672 frente a 672.0 en la clave del horizonte. Se corrigió admitiendo exclusivamente esas representaciones numéricamente idénticas; configuración, hashes de insumos, balances y métricas siguen verificándose. El paquete parcial validó 13 corridas, residuo relativo máximo 7,69e-16.
- Saldo antes de las comprobaciones de espacio/tiempo/registro: 82% restante. También se inició la sensibilidad de activación sucesiva conservando la misma operación de 15,919 h.
- El usuario volvió a autorizar al terminar **push a GitHub y correo**. La prohibición temporal queda revocada para el cierre; mantener `codex/defensa-final` y comprobar SHA remoto.
- Los tres casos M1_SS del candidato EPS 100 / 12 °C quedaron comprobados en fino a 448 h: ERA5 2023 19,24 °C; 2024 19,94 °C; 2025 20,15 °C. El caso 2025 ya implica cota inferior P_F = 25% (o 16,67% con pesos 50/50). Se descarta; no hace falta completar 22A en fino para recuperar un plan que ya falla.
- La prueba CLI que había agotado timeout pasó sin modificarla en el reintento dirigido. Se repetirá la suite completa antes de guardar el siguiente commit.
- Para no resolver una clasificación marginal con la última malla, se fija un nivel adicional de confirmación horizontal 0,20 m y vertical 0,05 m en el estudio extendido. Se evaluará el escenario SS/ERA5 2025 del candidato EPS 200 / 12 °C; se conservan por separado barrido, cribado y fino. No se altera ningún resultado previo ni sus claves.

## 17 de noviembre de 2026 · 00:10, America/Santiago · Pausa explícita del usuario

Estado: búsqueda completada para la familia nueva; verificación final **pendiente**. El usuario pidió detener el trabajo largo por demora. La pausa no se debe al límite de uso: queda **73%** de la ventana de cinco horas.

- Se crearon marcadores `PAUSAR` en ambas carpetas de la extensión y se detuvieron exclusivamente los procesos propios identificados por PID y comando. No quedan simulaciones largas de esta tarea ejecutándose. Los cálculos interrumpidos no cuentan como filas válidas y deberán recomenzar desde t0; no hay checkpoint temporal del solver.
- Se conservaron y empaquetaron **41 corridas nuevas completas** (14 pilotos/confirmaciones de 100 mm y 27 del horizonte extendido). Verificación: claves, hashes de IFC/hidratación/clima/código, balance, resta simultánea de extremos e integridad ZIP. Residuos relativos máximos 7,63e-16 y 9,04e-16. Los 79 resultados históricos siguen intactos.
- Punto 1: se fijó y exploró una familia de protecciones/preenfriamiento. EPS 100 mm / 12 °C pasó barrido pero falló en fino con SS/ERA5 2025: **20,1497997 °C**, por lo que P_F ≥ 25% con los pesos principales. No se acepta ese plan.
- EPS 200 mm / 12 °C: seis escenarios de barrido completos, sin excedencias y horizonte cerrado hasta 672 h. Peor Δ = **18,4003 °C**. La referencia de 0,05 m vertical dio **18,6343 °C**; temporal y registro **18,6361 °C**. No se afirma error numérico acotado ni cumplimiento final. El ensayo de registro también cambió el número de pasos; no aísla completamente muestreo e integración.
- Punto 2 pendiente: **0/6** escenarios finos del candidato EPS 200 / 12 °C terminados y **0/1** de confirmación adicional a 0,20 m. Activación sucesiva: **5/6** de barrido; falta 22A/ERA5 2025. Se conservó contraste de pronóstico sin peso (Δ = 18,3440 °C).
- Evidencia: `proyecto/docs/evidencia_extension_defensa`, `proyecto/docs/evidencia_extension_pilotos`; informe y comando exacto en `proyecto/docs/extension_defensa.md`. `pendientes.json` enumera las ocho filas aún pendientes. Las figuras marcan explícitamente el candidato de 200 mm como provisional. El PDF anterior no se actualizó con una recomendación aún sin verificar.
- Siguiente acción prioritaria: comprobar **una sola fila** EPS 200 / 12 °C, fino, SS/ERA5 2025. Retirar PAUSAR solo al reanudar. Si falla, replantear antes de ejecutar el resto. Si pasa, completar las otras cinco y resolver cualquier margen dudoso con la confirmación adicional. Confirmar además suministro a 12 °C desde t0 y protección disponible; si el preenfriamiento retrasa la colocación, sumar ese retraso a D.
- Cierre autorizado: guardar avances en commits locales, publicar `codex/defensa-final`, comprobar remoto y enviar correo con estado **pendiente**, sin afirmar que el candidato está validado. Los resultados de las comprobaciones de cierre se registran abajo.
- Comprobaciones de cierre tras detener la campaña: raíz **5/5** y proyecto **265/265**, ambas suites código 0. El fallo previo por timeout no se reprodujo. Empaquetado final: 27 + 14 corridas verificadas, sin filas finas incompletas aceptadas. `git diff --check` no detectó errores de formato.
- Rama: `codex/defensa-final`. El SHA de este reporte será el commit que añade esta sección y los paquetes; se comprobará contra GitHub antes de enviar el correo final. El correo y el chat informarán el SHA publicado y el resultado real del push.
## 16 de noviembre de 2026 · 23:50, America/Santiago · Relevo de Mauricio (Claude) · verificación independiente

Estado: pasos 1–9 siguen verificados; paso 10 sigue con el PDF verificado y el ensayo grupal pendiente. No hubo trabajo autónomo nuevo que hacer: los pendientes son humanos.

- Punto de partida: `origin/codex/defensa-final` en `ec94f89`, árbol limpio. Se leyó este archivo completo. No se repitió el barrido: las 60 filas y las 79 corridas siguen vigentes, porque no cambió código, insumos ni criterio.
- Verificación independiente (sin usar el empaquetador): desde `proyecto/docs/evidencia_defensa/escenarios.csv` se recalcularon P_T, P_delta y P_F de los 10 planes con pesos 0,75/0,25 y 0,50/0,50 por curva y 1/3 por clima. Coinciden con `comparacion.csv` (diferencia < 1e-9). En las 60 filas, I_T = [T_max > 70 °C], I_delta = [Δ > 20 °C] e I_F = máx(I_T, I_delta). Resultado: T_max ≤ 56,6 °C en todos los planes; el menor diferencial observado es 15,19 °C (`unica_poliestireno`), pero cada plan tiene al menos una fila sobre 20 °C, así que ninguno queda en P_F ≤ 5 %.
- Integridad: SHA-256 del PDF `59d5115e…2e30` igual al de `revision_pdf.json`; `corridas.zip` íntegro (`testzip` sin errores, 79 archivos).
- Pruebas: `test_defensa.py`, `test_fuente_calor.py`, `test_mapa_codigo.py`, `test_voxel.py` y `test_solver1d.py`: **42/42 aprobadas**, en Linux sin IfcOpenShell. **No se corrió la suite completa (264)**: este entorno no tiene IfcOpenShell ni acceso a PyPI. La última suite completa aprobada es la del corte de las 20:43.
- Uso de la ventana de 5 horas: **no consultable desde esta sesión** (no hay indicador de uso disponible para este agente). El cierre no se debe al límite: el trabajo autónomo ya estaba terminado.
- Correo: **no enviado**. La cuenta no tiene un conector de correo (Gmail) activo en Claude; el reporte se entregó en el chat.
- Punto exacto para retomar (sin cambios): abrir `Defensa final/Defensa final - Grupo 1.pdf` y `Archivos Extra/Defensa final/guion.md`, ensayar 7 minutos con los tres integrantes y registrar tiempos y respuestas aquí. Confirmar con el profesor los supuestos de obra, el significado de SS/22A y Arrhenius, y el plazo del artículo en Canvas.

### 17 de noviembre · integración del cierre

- El push de `c60659d` fue rechazado porque Mauricio publicó `e2e8a1c` durante esta sesión. Solo cambió este registro. Se conservaron ambas entradas completas, sin force push ni cambio del solver o los resultados.
- La entrada de Mauricio describe el paquete congelado `ec94f89`. La investigación nueva permanece pausada y la malla fina pendiente, según el encabezado y el corte de las 00:10.
- La integración solo modifica documentación; siguen vigentes las suites del cierre aprobadas antes de integrar: proyecto 265/265 y raíz 5/5. El correo indicará el SHA final y el estado real del push.

## 17 de noviembre de 2026 · 00:45, America/Santiago · Relevo de Mauricio (Claude) · paso 8 bloqueado por ejecución

Estado: paso 8 sigue **en pausa / bloqueado**; la siguiente fila no se pudo ejecutar en esta sesión. Evidencia existente verificada de forma independiente.

- Punto de partida: `origin/codex/defensa-final` en `9da4f22` (cierre de Magdalena a las 00:10, integración a las 00:28). El repositorio local de Mauricio se adelantó a ese commit sin cambios propios.
- Bloqueo: el solver necesita IfcOpenShell y el Python del proyecto en Windows. Este agente trabaja en Linux sin IfcOpenShell ni acceso a PyPI, y no puede ejecutar programas en el Windows de Mauricio. No se lanzó ninguna corrida ni se tocó `PAUSAR`.
- Trabajo en paralelo, verificación independiente (sin el empaquetador): ZIP de `evidencia_extension_defensa` (27) y `evidencia_extension_pilotos` (14) íntegros; en las 41 filas I_T, I_delta e I_F coinciden con 70 °C / 20 °C; P_F recalculado con pesos 0,75/0,25 y 0,50/0,50 × 1/3 coincide con `comparacion.csv` en todos los planes y niveles (diferencia < 1e-9).
- Análisis de sensibilidad a la malla (solo con filas existentes, **no es verificación**): en EPS 100 / 12 °C, SS, el diferencial subió +0,18 a +0,21 °C de barrido a cribado y +0,43 a +0,65 °C de cribado a fino, sin disminuir el incremento. En EPS 200 / 12 °C, SS/ERA5 2025, barrido → cribado subió +0,234 °C (18,400 → 18,634 °C). Si el paso a fino se comporta igual, el fino quedaría en ≈ 19,1–19,3 °C, bajo 20 °C con margen < 1 °C y sin convergencia demostrada. Esto respalda correr primero esa única fila, como indica la entrada de las 00:10.
- Preparado: `Confirmar EPS200 fino.cmd` en la carpeta `Cloude` de Mauricio (fuera del repositorio). Ejecuta exactamente `explorar_defensa.py --estudio proyecto/configs/defensa_extension_clima.yaml --salida proyecto/results/defensa_extension_larga --plan eps200_T12 --nivel fino --curva M1_SS --clima era5_2025 --horizonte-extendido 672 --procesos 1` y guarda la salida en `confirmacion_eps200_fino.txt`. No ejecuta `resumir_extension_defensa.py`: en esa máquina la carpeta de resultados tendría solo esta fila y podría reempaquetar la evidencia incompleta.
- Pruebas en esta sesión: no se modificó código. Las suites completas vigentes son las del cierre de las 00:10 (proyecto 265/265, raíz 5/5).
- Uso de la ventana de 5 horas: no consultable por este agente.
- Siguiente acción exacta: doble clic en `Confirmar EPS200 fino.cmd` (≈ 30–60 min estimados, sin medir). Si EXIT=0, copiar el JSON nuevo de `proyecto/results/defensa_extension_larga` junto a las 27 corridas del ZIP antes de reempaquetar. Si Δ > 20 °C, el candidato queda descartado y hay que replantear el control antes de correr las otras cinco filas finas.

## 17 de noviembre de 2026 · 01:55, America/Santiago · Relevo de Mauricio (Claude) · paso 8, confirmación fina completa

Estado: paso 8 con **todos los cálculos pendientes completos**. EPS 200 mm / 12 °C cumple en todas las mallas calculadas, con salvedad de convergencia. El paso 9 (recomendación y PDF) sigue pendiente.

- Inicio: `codex/defensa-final` en `e7b5976`, al día con `origin` y árbol limpio salvo `e11_clima.png`. Sin otras simulaciones corriendo y sin marcador `PAUSAR`. Saldo inicial de la ventana de 5 h: 57 % restante.
- Fila prioritaria, ejecutada sola (01:21:31–01:28:41): EPS 200 / 12 °C, fino, SS/ERA5 2025, 672 h. **Δ = 19,4409 °C**, T_max = 49,64 °C, horizonte cerrado. **Duración: 430 s de reloj** (426 s de solver), muy por debajo de los 30–60 min estimados. Cumple con margen 0,56 °C, así que se continuó con el resto.
- Saldo antes de las demás corridas: 55 % restante. Se lanzaron 3 procesos independientes con `--procesos 1`, porque el pool múltiple había fallado antes con WinError 6. Todos terminaron con código 0 a las 01:50:
  - fino SS: ERA5 2023 18,4703 °C (550 s); ERA5 2024 19,2890 °C (550 s).
  - fino 22A: ERA5 2023 11,0557 °C (187 s; cerró a 336 h); 2024 11,6009 °C (548 s); 2025 11,7366 °C (491 s).
  - confirmación 0,20 m / 0,05 m, SS/ERA5 2025: **19,8215 °C** (689 s).
  - activación sucesiva, barrido 22A/ERA5 2025: 11,3878 °C (70 s). Completa la matriz sucesiva (6/6) sin excedencias.
- Empaquetado: se extrajeron las 27 corridas de `corridas.zip` junto a las 8 nuevas, sin sobrescribir nada, y `resumir_extension_defensa.py` verificó **35 corridas**. Claves, huellas de solver, IFC, hidratación y clima, diferencial como resta simultánea, indicadores y balance: residuo relativo máximo 9,04e-16. ZIP íntegro con 35 archivos. `comparacion.csv`: eps200_T12 fino P_T = P_Δ = P_F = 0 % con ambos juegos de pesos.
- Figuras regeneradas con `graficar_extension_defensa.py`, usando las corridas históricas (79) y los pilotos (14) extraídos de sus ZIP en `results/`, sin modificar los ZIP. La comparación usa ahora la fila fina de 200 mm, ya no la provisional, y la sensibilidad incluye la confirmación de 0,20 m.
- **Salvedad de malla (no ocultar en la defensa):** en SS/ERA5 2025, Δ sube con cada refinamiento horizontal: 18,634 (0,5 m) → 19,441 (0,25 m) → 19,822 °C (0,20 m). El último incremento es proporcionalmente mayor que el anterior; con estas tres mallas no se puede extrapolar un valor convergido ni acotar el error. Margen a 0,20 m: 0,18 °C. Es el mismo patrón que llevó a descartar EPS 100 / 12 °C, que cruzó 20 °C solo en fino. Conclusión honesta: EPS 200 / 12 °C cumple en todas las resoluciones calculadas, pero es marginal y no está demostrado que el valor convergido quede bajo 20 °C.
- Actualizados: `pendientes.json` (ya sin pendientes, con las 8 filas y la advertencia) y `proyecto/docs/extension_defensa.md` (sección «Confirmación fina»).
- Verificación antes del commit (01:58): raíz **5/5**; proyecto **264 aprobadas + 1 omitida** (prueba opcional del renderer JS, que se omite si Node no está instalado), código 0. `git diff --check` sin errores.
- Siguiente acción: decidir con el grupo la recomendación. Opciones: (a) presentar EPS 200 / 12 °C como el mejor candidato hallado, con margen de 0,18 °C y la salvedad de malla; o (b) buscar más margen (por ejemplo EPS 300 mm a 12 °C o colocación a 10 °C) en barrido y fino, a unos 7–10 min por fila. Después actualizar el PDF y el guion (paso 9) y ensayar (paso 10). Los supuestos de obra (suministro a 12 °C desde t0, EPS disponible) siguen sin confirmar.
