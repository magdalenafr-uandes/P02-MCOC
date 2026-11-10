# Promedios de noviembre aportados por el usuario

Esta carpeta es la base de datos local del escenario de noviembre. La simulación
lee los CSV de aquí y no depende de la carpeta Descargas del equipo.

| Archivo | Contenido |
|---|---|
| `maximas.csv` | Promedios de temperaturas máximas de noviembre por año y simulación |
| `minimas.csv` | Promedios de temperaturas mínimas de noviembre por año y simulación |
| `maximas.png` | Gráfico original de temperaturas máximas |
| `minimas.png` | Gráfico original de temperaturas mínimas |
| `metadata.json` | Procedencia, mes, coordenadas, nombres originales, tamaños y huellas SHA-256 |

Los cuatro archivos se copiaron sin alterar su contenido y se verificaron
contra los originales. Las imágenes sirven como referencia; el cálculo usa
los valores numéricos de los CSV mediante `caso/ciclo_diario.py`.

Los CSV originales se conservan sin modificar: `maximas.csv` procede de
`promedio-de-la-temperatuMax.csv` y `minimas.csv` de `promedio-de-la-temperatu.csv`.
Separador `;`, coma decimal; un año por fila y una columna por simulación climática.
Se usa la última columna, **Valor medio de las simulaciones**.

Las imágenes aportadas identifican noviembre y 24.57°S, 69.58°O. Esta posición
es distinta del sitio del proyecto (-24.952830, -70.004838). No se atribuyen
estos datos a una estación ni al sitio exacto: no se proporcionó enlace de
origen, estación, escenario de emisiones ni metadata adicional.

Para 2026: mínima media de 5,5 °C y máxima media de 28,6 °C. No son extremos
observados de cada día ni un pronóstico horario. El modelo crea un día
representativo mediante dos medios cosenos, con mínima a las 06:00 y máxima
a las 15:00 por defecto (horas supuestas, editables). Se repite cada 24 h;
si la obra entra en diciembre, mantiene explícitamente el escenario de noviembre.
No se inventan datos de viento o sol: este modo usa convección constante,
inicialmente 10 W/(m² K) en el visor, sin radiación. El modo de snapshots
continúa disponible con viento y radiación según su configuración.

El año se elige mediante la fecha de inicio de obra; no se extrapolan años
ausentes. El YAML ejecutado conserva temperaturas, horas de extremos,
procedencia y huellas SHA-256 de ambos archivos para repetir el cálculo.
