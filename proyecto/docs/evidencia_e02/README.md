# Evidencia del round-trip E02 (Bonsai)

Esta carpeta guarda la **evidencia real** del round-trip del hito E02. Los
archivos se generan solo después de que la edición manual en Bonsai se haya
hecho y verificado; no se fabrican datos.

Contenido esperado:

| Archivo | Cómo se genera |
|---|---|
| `roundtrip_antes.json` | `python scripts/ifc_state.py geometry/foundation.ifc --salida docs/evidencia_e02/roundtrip_antes.json` (antes de editar en Bonsai) |
| `roundtrip_despues.json` | Mismo comando tras el guardado en Bonsai |
| `roundtrip_diff.txt` | Salida de `python scripts/ifc_diff.py docs/evidencia_e02/roundtrip_antes.json geometry/foundation.ifc` redirigida al archivo |

Modificación de demostración documentada: `TemperaturaColocacion_C` de
`Vertida_01`, de 18 °C a 19 °C, editada manualmente en Bonsai (Blender +
Bonsai) sobre `geometry/foundation.ifc`. El valor inicial de 18 °C está
verificado en el archivo generado; el "después" solo existe tras la edición
real.

Si el guardado en Bonsai introduce cambios adicionales (metadatos,
unidades, representación), se muestran en el diff y se documentan aquí.
