# Propuesta de aislación basal con vidrio celular | P02 MCOC, Grupo 1

## Decisión que se quiere verificar

Colocar 636,775 m³ de hormigón a 12 °C, a 40 m³/h, mediante cargas de 8 m³ cada 12 min, sin esperas programadas. Proteger las caras superiores y laterales expuestas con 200 mm de EPS y estudiar 70 mm de vidrio celular de alta resistencia en el contacto entre la fundación y el suelo. Con preenfriamiento y capa basal disponibles al inicio, la operación de colocación alcanza la cota D = V/r = 15,919 h. Si la preparación desplaza el inicio común, ese atraso se debe contabilizar y el clima debe alinearse con el nuevo cronograma.

## Qué se modeló

Se usó el solver de colocación progresiva del commit c25e3dd en una copia local. Se mantuvieron IFC, secuencia, caudal, temperaturas de colocación, moldaje, propiedades del hormigón y suelo y el EPS exterior. La modificación térmica basal se representó como R = 0,070/0,050 = 1,400 m²·K/W, frente a 1,429 m²·K/W de los 50 mm de EPS de las pruebas previas. La capa basal del solver es continua e idealizada como resistencia sin masa térmica. Las juntas, el contacto real y los detalles de instalación pueden cambiar su resistencia efectiva.

Se conservaron las dos curvas M1 y las tres historias ERA5. Para la evaluación prolongada se añadieron datos horarios hasta el 31 de diciembre a cada análogo histórico. Se comprobó coincidencia exacta en las 24 horas de solape del 20 de diciembre y se conservó íntegro el registro archivado. La verificación usa los límites térmicos de 70 °C y 20 °C y el criterio conjunto del 5 %.

## Resultados térmicos de la colocación progresiva

| Nivel | Curva | Clima | T máxima (°C) | Δ máximo (°C) | Hora de Δ | Horizonte (h) | Estado |
|---|---|---|---:|---:|---:|---:|---|
| fino | M1_22A | ERA5 2023 | 38,958 | 9,674 | 26,75 | 1019 | Cerrado |
| fino | M1_SS | ERA5 2023 | 49,955 | 12,374 | 1060,00 | 1240 | Cerrado |
| fino | M1_22A | ERA5 2024 | 38,904 | 9,703 | 26,75 | 1019 | Cerrado |
| fino | M1_SS | ERA5 2024 | 49,953 | 12,757 | 940,00 | 1019 | Cerrado |
| fino | M1_22A | ERA5 2025 | 38,946 | 9,671 | 26,75 | 1019 | Cerrado |
| fino | M1_SS | ERA5 2025 | 49,954 | 13,047 | 940,25 | 1019 | Cerrado |
| confirmacion | M1_SS | ERA5 2025 | 49,954 | 12,720 | 750,00 | 760 | Abierto |
| confirmacion | M1_SS | ERA5 2025 | 49,954 | 13,084 | 941,75 | 1019 | Cerrado |

La malla fina mide 0,25 × 0,25 × 0,05 m. La confirmación en M1 SS / ERA5 2025 mide 0,20 × 0,20 × 0,05 m.
Se observaron 0 excedencias en seis filas finas. P_F observada = 0,00 % con pesos 75/25 y 0,00 % con pesos 50/50. Las seis filas se ponderan por curva y año.
Filas finas con horizonte abierto: 0. Una fila abierta exige ampliar o justificar el horizonte antes de cerrar la clasificación bajo el procedimiento del equipo.

Se recalcularon los máximos desde las series, la unión de excedencias, la duración y el balance. El máximo residuo energético relativo observado en estas corridas fue 5.70e-16. Pasaron 24 pruebas de colocación progresiva, protección y solver de voxeles.

La matriz fina satisface el criterio térmico conjunto de 5 % bajo el modelo discreto y el horizonte comprobado. La aprobación constructiva sigue condicionada a las comprobaciones estructurales y geotécnicas.

En la confirmación y durante las primeras 672 h, el diferencial pasó de 20,025 °C sin aislación basal a 12,547 °C con vidrio celular. El resto de las cifras corresponde a máximos observados en horizontes más largos. Con vidrio celular, el máximo fue 12,720 °C hasta 760 h y 13,084 °C hasta 1.019 h. Las comparaciones entre horizontes indican qué máximos se detectaron al observar más tiempo.

El CSV adjunto conserva también las seis corridas de barrido a 760 h, la primera fila fina de SS/2023 a 1.019 h y la clave de cada corrida. La aproximación a la superficie del IFC y el uso de una capa térmica idealizada siguen formando parte del modelo.

## Condiciones para adopción constructiva

- **Presiones y contacto.** Obtener combinaciones de carga del aerogenerador y del diseño de fundación. Verificar presiones máximas y su distribución por peso propio, acciones repetidas y momentos de vuelco. Revisar el deslizamiento y la transferencia de corte por las interfaces y el contacto efectivo donde corresponda.
- **Deformación a largo plazo.** La ficha de referencia de FOAMGLAS F declara resistencia a compresión de al menos 1.600 kPa en ensayo. Se requiere la resistencia de diseño del sistema instalado y la comprobación de compresión, cargas repetidas, deformación a largo plazo y asentamiento total y diferencial. Verificar la inclinación admisible del aerogenerador. La ficha no sustituye esos cálculos.
- **Peso propio como referencia.** El IFC da 268,41 m² de cara basal. Con la densidad de 2.400 kg/m³, el hormigón pesa aproximadamente 14,99 MN y aporta 55,86 kPa como presión media si todo el apoyo participa por igual. Esta referencia excluye torre, equipo, rellenos, acciones y excentricidades. La presión de diseño local requiere esos datos.
- **Humedad en Taltal.** El clima superficial árido no establece el estado del suelo a la profundidad de apoyo. Pedir perfil geotécnico, agua, drenaje y propiedades térmicas del suelo en los estados relevantes. El vidrio celular de referencia declara capilaridad e higroscopicidad nulas. El agua y la calidad de las juntas y del drenaje se verifican para el sistema instalado.
- **Implantación.** Confirmar un apoyo continuo y nivelado, detalle de juntas e interfaces y la instalación de la capa basal antes de la colocación. Confirmar entrega de hormigón a 12 °C y caudal sostenido. Validar el momento de retiro del EPS exterior y la estrategia de medición en el costado inferior y los núcleos.

No se identificaron en el repositorio datos de cargas de diseño, límites de asentamiento ni un estudio geotécnico específico que permitan dar por aprobada la capa bajo la fundación.

## Fuentes

- [Campaña de colocación progresiva y referencia basal](https://github.com/magdalenafr-uandes/P02-MCOC/blob/c25e3dde230d4b7ec3553dc2ec5794c82fee1001/proyecto/docs/colocacion_progresiva.md)
- [Ficha de FOAMGLAS F usada para parametrizar la comparación](https://www.foamglas.com/-/media/project/foamglas/public/shared/files/foamglas-b/foamglas-f/pds/pds-foamglas-f-me.pdf)
- [API de históricos de Open-Meteo](https://open-meteo.com/en/docs/historical-weather-api)
