# Ciclo día/noche y horarios de vertidas

## Consultar un voxel

En los modos de voxels, hacer clic sobre una cara visible selecciona su voxel
y muestra temperatura, vertida, índices y coordenadas del centro. Se destaca
en color claro; el valor sigue el mismo voxel al mover el reloj, incluso antes
de su colocación (se muestra "Todavía no vertido"). El corte horizontal permite
consultar también el interior. Un arrastre gira la cámara y no selecciona.
El moldaje visible permite consultar el hormigón que tiene debajo. Los
triángulos IFC sin correspondencia con un voxel indican cambiar al modo voxels.
La temperatura consultada es la del voxel de hormigón, no una temperatura
exacta de superficie ni la de la madera. **Quitar selección** limpia el panel.

## Mostrar el moldaje

El botón **Mostrar moldaje**, sobre la vista 3D, representa en marrón el
moldaje lateral activo. Sirve en temperatura, identificación por vertida y
modo IFC; en este último la capa es una representación por caras de voxel.
Al alcanzar `inicio de vertida + edad de retiro`, desaparece automáticamente.
No se dibuja sobre interfaces entre sólidos, la cara superior ni cortes
artificiales. Al retroceder el reloj se restaura su estado anterior.
El botón solo controla la vista y no cambia la simulación ni sus resultados.

En el visor integrado (`Abrir visualizador.cmd`), elegir **Inicio de obra**
con fecha y hora local de Chile. Editar **Fecha y hora local** de cada vertida
o sus **Inicio [+h]**, que se mantienen sincronizados. Cambiar el inicio global
desplaza las vertidas conservando sus intervalos. Ninguna puede comenzar
antes del inicio global. La temperatura de colocación sigue siendo independiente
de la del aire: esta última no reemplaza automáticamente los 18 °C del hormigón.

La opción **Ciclo día/noche · promedios de noviembre** está seleccionada al
abrir el visor. Usa el año del inicio para leer la media publicada de los CSV
en `data/clima_noviembre/`. Para 2026 oscila entre **5,5 y 28,6 °C**.
Las horas de mínima (06:00) y máxima (15:00) son supuestos editables.
El ciclo suave se evalúa como una serie cada cinco minutos, incluyendo los
extremos exactos y el inicio y final; el solver interpola en cada paso estable.

Estos son promedios de simulaciones climáticas en una posición distinta
del sitio IFC, no observaciones ni forecast diario. Se repite un día representativo,
incluso fuera de noviembre. Se usa h constante editable y se omiten viento
variable y radiación en este modo. El selector permite volver al snapshot
meteorológico; desmarcar temperatura variable usa aire constante.

Después de ejecutar, cada fotograma muestra fecha y hora de obra y temperatura
del aire junto al hormigón calculado. El gráfico muestra ambas curvas.
Reproducir permite avanzar a **1, 6 o 24 horas simuladas por segundo**.
La velocidad solo cambia la reproducción, no el cálculo ni su paso temporal.
La resolución visual depende de **Guardar cada [h]**: usar 1 h o menos para
seguir el ciclo diario; 24 h solo mostraría la misma hora de cada día.

`caso_ejecutado.yaml` incluye el ciclo y sus huellas y se puede ejecutar con
la CLI compartida. `resultado.json` incluye `fecha_hora` y `ambiente_C` por
fotograma, evaluados por Python en los mismos instantes que el campo térmico.
