# Evidencia del round-trip E02 (Bonsai)

Esta carpeta guarda la **evidencia real** del round-trip del hito E02. Los
archivos se generaron solo después de que la edición manual en Bonsai se
hizo y verificó; no se fabricaron datos.

Contenido (ensayo real completado):

| Archivo | Cómo se generó |
|---|---|
| `roundtrip_antes.json` | `python scripts/ifc_state.py geometry/foundation.ifc --salida docs/evidencia_e02/roundtrip_antes.json`, **antes** de editar en Bonsai |
| `roundtrip_despues.json` | Mismo comando **después** de guardar la edición en Bonsai |
| `roundtrip_diff.txt` | `python scripts/ifc_diff.py docs/evidencia_e02/roundtrip_antes.json docs/evidencia_e02/roundtrip_despues.json` redirigido al archivo; **código de salida 1** (diferencias detectadas, esperado) |

## El ensayo (18 → 19 °C)

1. `roundtrip_antes.json`: las cinco vertidas con
   `TemperaturaColocacion_C = 18 °C`.
2. Edición **manual en Bonsai** (Blender + Bonsai, *File > Open IFC Project*)
   sobre `geometry/foundation.ifc`: `TemperaturaColocacion_C` de
   `Vertida_01` (GlobalId `3ksU2stB516hyA0nwBMzEx`): **18 → 19 °C**, y
   *Save IFC Project*.
3. `roundtrip_despues.json`: mismo GlobalId con **19 °C**.
4. `roundtrip_diff.txt` (diff entre los dos JSON): el reporte contiene
   **una sola línea de cambio** —
   `3ksU2stB516hyA0nwBMzEx (Vertida_01) UANDES_HormigonMasivo.TemperaturaColocacion_C: 18 -> 19` —
   sobre el mismo GlobalId, con las cinco líneas de geometría en
   "sin cambios" (bbox y volumen idénticos; `n_vertidas = 5` y
   `volumen_total_m3 = 636.7751514210236` en ambos snapshots).
5. Verificación posterior: 27 tests en verde.

## Restauración del IFC

Después del ensayo **restauramos manualmente** `TemperaturaColocacion_C` de
`Vertida_01` a **18 °C** en Bonsai, para poder repetir la demostración en la
defensa.

Por eso: **la evidencia posterior del ensayo no representa el estado actual
del IFC**. El archivo `geometry/foundation.ifc` que está versionado tiene
las cinco vertidas a 18 °C; los JSONs de esta carpeta son los estados
"antes" y "después" del ensayo real y se conservan sin regenerar.

Si el guardado en Bonsai introduce cambios adicionales de cabecera
(metadatos, fecha, sistema autor), solo afectan al `FILE_NAME` del IFC: la
sección de datos (propiedades y geometría) queda igual que la versión
versionada.
