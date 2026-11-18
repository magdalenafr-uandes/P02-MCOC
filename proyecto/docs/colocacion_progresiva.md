# Colocación de 8 m³ cada 12 minutos

Sensibilidad solicitada para el candidato EPS 200 mm y hormigón a 12 °C. El reloj físico conserva 636,775 m³, una línea de 40 m³/h, 04:00 como hora de inicio y 15,919 h hasta terminar. Se simulan 79 cargas completas y una final de 4,775 m³. La activación de la primera porción ocurre al empezar el reloj.

## Representación térmica

- Se conserva el IFC y se voxeliza con las mismas resoluciones de la extensión. El reloj de cargas cruza los límites de sólidos. Si una carga cruza un límite, la porción que sigue se activa cuando se termina el sólido anterior. Los volúmenes planificados se aproximan con celdas completas, conservando exactamente el volumen de la grilla y todos los identificadores IFC para las métricas.
- El orden provisional dentro del sólido es por altura, luego `x`, luego `y`. Cada porción se agrega al comenzar su colocación, a 12 °C y con edad térmica cero. Se conserva el retiro del moldaje a las 72 h del inicio del sólido. Se modela EPS en caras superior y laterales expuestas, incluidas las que aparecen temporalmente al avanzar el llenado. La trayectoria y la protección de esos frentes requieren confirmación de obra.
- El motor de volúmenes finitos, las propiedades, las dos curvas M1, los bloques ERA5, el diferencial a 25 mm y los límites siguen la extensión. Se inicia con 336 h y se extiende a 672 h si se detectan señales tardías. La comparación se filtra por escenario y malla.

## Resultado

Se completaron ocho corridas progresivas con horizonte cerrado. En barrido quedaron seis de seis bajo ambos límites, con probabilidad de excedencia observada de 0% en ambos juegos de pesos. En las dos mallas más finas se probó M1_SS/ERA5 2025, el escenario que daba el mayor diferencial en la matriz fina de activación conjunta.

| Malla [m] | Δ conjunta [°C] | Δ sucesiva [°C] | Δ progresiva [°C] | T máxima progresiva [°C] |
| --- | ---: | ---: | ---: | ---: |
| 0,50 × 0,50 × 0,10 | 18,4003 | 18,6347 | 18,6054 | 49,8380 |
| 0,25 × 0,25 × 0,05 | 19,4409 | — | 19,6447 | 49,8408 |
| 0,20 × 0,20 × 0,05 | 19,8215 | — | **20,0255** | 49,8410 |

En la malla de 0,20 m, el diferencial progresivo máximo fue **20,025470 °C**, a las 437,75 h. El aumento de 0,203948 °C respecto de la activación conjunta consume el margen de 0,178477 °C y supera el límite de 20 °C por 0,025470 °C. La temperatura máxima permanece por debajo de 70 °C. En el criterio discreto, ese escenario tiene peso 25% (16,67% con pesos 50/50). A 0,20 m se calculó una sola fila progresiva y la convergencia del diferencial permanece sin demostrar. El resultado aporta evidencia de que la aceptación es sensible tanto a resolución como a representación de la colocación.

## Sensibilidad al espesor de EPS

El EPS de 20 cm aporta 5,7143 m²·K/W y el de 30 cm aporta 8,5714 m²·K/W (`R = e/k`, con `k = 0,035 W/(m·K)`). El solver suma `R` a las resistencias de media celda y de película de aire. El contacto con el suelo sigue intercambiando calor por conducción. La temperatura superficial se evalúa 25 mm dentro del hormigón y se resta de la temperatura máxima **del mismo instante**.

En M1_SS/ERA5 2025, las 80 cargas, la malla de 0,20 × 0,20 × 0,05 m, las condiciones del suelo, el clima y las demás entradas coinciden. La serie de 30 cm reduce en **0,157657 °C** el diferencial a las 437,75 h (hora del pico con 20 cm). Su propio pico ocurre a las 581,75 h, seis días después. El punto frío de ambos picos queda en la misma cara lateral de la primera vertida, con centro de celda a 25 mm sobre el contacto con el suelo.

| Tiempo desde el inicio | EPS | Temperatura máxima en ese instante [°C] | Temperatura a 25 mm de la cara más fría [°C] | Diferencial [°C] |
| --- | ---: | ---: | ---: | ---: |
| 437,75 h | 20 cm | 48,5028 | 28,4773 | 20,0255 |
| 437,75 h | 30 cm | 48,8117 | 28,9439 | 19,8678 |
| 581,75 h | 20 cm | 47,3454 | 27,3616 | 19,9837 |
| 581,75 h | 30 cm | 47,8508 | 27,8486 | 20,0022 |
| 581,75 h | 40 cm | 48,1465 | 28,1073 | 20,0392 |

El máximo de toda la corrida baja **0,023244 °C** al pasar de 20 a 30 cm. Con 40 cm el pico se mantiene a las 581,75 h y sube a **20,039239 °C**. Entre 30 y 40 cm, a esa hora el núcleo se mantiene 0,2957 °C más caliente y la zona cercana a la cara, 0,2587 °C más caliente. El aumento del núcleo es mayor y eleva el diferencial en 0,0370 °C. Los tres espesores superaron 20 °C en esta corrida. El excedente de 0,0022 °C con 30 cm es el valor que entrega esta discretización. La incertidumbre de malla y el muestreo cada 15 minutos importan debido a la cercanía al umbral. [Comparación de espesores](evidencia_colocacion_progresiva/comparacion_eps.csv) · [Corridas adicionales](evidencia_colocacion_progresiva/sensibilidad_eps.zip).

## Reproducción y evidencia

Desde la raíz del repositorio con el entorno del proyecto instalado:

```powershell
$py = 'proyecto/.venv/Scripts/python.exe'
& $py proyecto/scripts/colocacion_progresiva.py --nivel barrido --salida proyecto/results/colocacion_progresiva/barrido
& $py proyecto/scripts/colocacion_progresiva.py --nivel fino --curva M1_SS --clima era5_2025 --salida proyecto/results/colocacion_progresiva/fino
& $py proyecto/scripts/colocacion_progresiva.py --nivel confirmacion --curva M1_SS --clima era5_2025 --salida proyecto/results/colocacion_progresiva/confirmacion
& $py proyecto/scripts/publicar_colocacion.py
```

Las corridas completas compatibles se reutilizan por clave. `PAUSAR` en la carpeta de salida evita iniciar otra corrida tras terminar la actual. Para regenerar solo las tablas y el HTML, extraer el [ZIP de corridas nuevas](evidencia_colocacion_progresiva/corridas.zip) en una carpeta vacía dentro de `proyecto/results/colocacion_progresiva` y ejecutar `publicar_colocacion.py`. El script comprueba volúmenes y horas de las cargas, balances, hora y valor de los picos e indicadores de excedencia. Las referencias se leen de la [extensión archivada](evidencia_extension_defensa/corridas.zip) y deben tener las mismas huellas de modelo, IFC, hidratación y clima.

El espesor de aislamiento se puede indicar con `--eps-mm`. Para comparar un espesor distinto de 200 mm con la corrida progresiva de referencia:

```powershell
& $py proyecto/scripts/colocacion_progresiva.py --eps-mm 300 --horizonte-completo --nivel confirmacion --curva M1_SS --clima era5_2025 --salida proyecto/results/colocacion_eps300
```

`--horizonte-completo` integra directamente hasta 672 h, el horizonte usado en la comparación, y ahorra la corrida preliminar de 336 h. Si el pico queda al final de las 672 h, la evidencia registra el horizonte como abierto.

[Comparación por resolución y escenario](evidencia_colocacion_progresiva/comparacion.csv) · [Estado de matrices](evidencia_colocacion_progresiva/estado.json) · [Porciones de la malla del visor](evidencia_colocacion_progresiva/porciones.csv) · [HTML interactivo](../../Archivos%20Extra/Colocaci%C3%B3n%20progresiva/Colocaci%C3%B3n%20del%20hormig%C3%B3n.html)
