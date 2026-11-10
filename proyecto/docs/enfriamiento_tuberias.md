# Evaluación inicial: enfriamiento interno con agua

Estado: propuesta de modelación, todavía no implementada en el solver ni en
el visor. No constituye un dimensionamiento constructivo.

## Problema y alternativa

En la corrida local `3106ece7cb3c` (168 h), el voxel que alcanzó el pico llegó
a 64,30 °C a las 42 h y conservó 58,83 °C a las 168 h. Retirar el moldaje
lateral tuvo poco efecto en ese punto durante la primera semana. Las tuberías
embebidas permiten extraer calor del interior sin esperar a que llegue a la
superficie de la fundación. ACI incluye este procedimiento entre las medidas
de control térmico del hormigón masivo [1].

Las tuberías se instalan y fijan antes del vertido. El calor pasa del hormigón
a la pared de la tubería y al agua, que sale más caliente. Si el circuito es
cerrado, debe representarse el calentamiento del estanque y, si existe, el
rechazo térmico de un enfriador: una bomba por sí sola no mantiene fría el agua.

## Modelo propuesto para el proyecto

El balance actual por voxel se conserva, añadiendo un intercambio localizado:

    C_i dT_i/dt = Σ_j G_ij(T_j - T_i) + q_h,i V_i + P_exterior,i - P_agua,i

Para un tramo de tubería dentro de una celda, aproximando su respuesta como
cuasiestacionaria y la temperatura de esa celda como uniforme:

    capacidad_del_flujo = m_dot * cp_agua                         [W/K]
    K_tramo = capacidad_del_flujo * (1 - exp(-UA / capacidad_del_flujo))
    P_tramo = K_tramo * (T_voxel - T_entrada_tramo)                [W]
    T_salida_tramo = T_entrada_tramo + P_tramo / capacidad_del_flujo

La salida de un tramo es la entrada del siguiente, en el orden de circulación.
`UA` es una conductancia global que incluye el intercambio interior, la pared
y la aproximación de conducción entre el voxel y la tubería; no se obtiene
solo del diámetro. Con caudal cero, este primer modelo no extrae calor por
circulación. Si el agua está más caliente que el hormigón, el signo del intercambio
se invierte: no se fuerza una extracción de calor inexistente.

No se impone al hormigón la temperatura del agua ni se enfría todo el núcleo
uniformemente. Cada tramo actúa únicamente sobre las celdas atravesadas y
solo cuando la vertida correspondiente existe. Los encendidos y apagados
deben ser eventos y el paso estable debe incluir la conductancia adicional.

La malla actual tiene Δx = 0,5 m y Δz = 0,05 m en el perfil del visor.
Una tubería menor que la celda requiere un modelo de intercambio subcelda:
convertir un voxel entero en agua alteraría artificialmente su diámetro.
Para estudiar gradientes junto a la pared hace falta refinamiento espacial
o un modelo local; la temperatura media de una celda no resuelve ese gradiente.

## Qué comparar

Mantener el mismo clima, material, malla, vertidas y protecciones en todos los casos:

1. Caso actual sin tuberías.
2. Circuitos distribuidos por vertida con suministro continuo.
3. Mismo trazado con control de operación (temperatura de entrada, caudal y horario).
4. Si corresponde, circuito recirculado con estanque y enfriador explícitos.

Registrar máximo global y su hora; sondas fijas del núcleo, borde y cerca de
las tuberías; diferencias térmicas por vertida; velocidades de enfriamiento;
temperatura de salida, energía retirada y consumo de agua. La línea del máximo
global no sustituye el seguimiento de un punto fijo.

Como control de escala, el volumen voxelizado de esa corrida es 643,625 m³.
Con ρ = 2400 kg/m³ y cp = 970 J/(kg K), su capacidad térmica es 1,498 GJ/K.
Bajar 10 K su temperatura **media** representa aproximadamente 14,98 GJ,
equivalentes a 24,8 kW medios durante siete días. Es solo una cuenta de energía
sensible: no fija la potencia de diseño ni considera la evolución de la
hidratación, pérdidas exteriores o distribución espacial del enfriamiento.

## Datos necesarios para una primera simulación

- Circuito abierto o recirculado; disponibilidad de agua y eventual enfriador.
- Material, diámetro interior y exterior de la tubería.
- Trazado, separación, cota y longitud de cada circuito por vertida.
- Caudal **por circuito**, temperatura de entrada y horarios de funcionamiento.
- Método para estimar/calibrar la conductancia global del intercambio.

Sin estos datos se pueden estudiar escenarios docentes, identificando cada
parámetro supuesto. No se adopta un diámetro, caudal o temperatura como solución
validada para construcción.

## Criterio de evaluación

El objetivo no es enfriar lo más rápido posible: el enfriamiento localizado
puede producir diferencias térmicas importantes junto a las tuberías [2].
Hay que evaluar esas diferencias, el control del agua y la operación junto
con el descenso de la temperatura máxima. El solver actual calcula temperaturas,
no tensiones ni resistencia a tracción: no puede certificar ausencia de fisuras.

## Fuentes

1. ACI, *How to Control Mass Concrete Temperature during Construction*:
   https://www.concrete.org/frequentlyaskedquestions.aspx?faqid=892
2. Tasri y Susilawati (2019), *Effect of cooling water temperature and space
   between cooling pipes of post-cooling system on temperature and thermal
   stress in mass concrete*, Journal of Building Engineering:
   https://doi.org/10.1016/j.jobe.2019.100731
