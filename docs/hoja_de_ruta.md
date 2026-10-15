# Hoja de ruta — plan de vertidas de hormigón masivo (Grupo 1)

Fases previstas más allá de E00. Cada fase se documentará y validará antes de
pasar a la siguiente. Las decisiones constructivas se modificarán mediante
**configuración** (archivos YAML), sin reescribir el programa.

## W1 — BIM, round-trip IFC, difusión y verificación 1D

- Modelación CAD/BIM con Bonsai/Blender (solo para generar IFC; el solver no
  depende del estado interno de Blender).
- Escritura/lectura IFC con IfcOpenShell y verificación de round-trip.
- Información por vertida en IFC: `VertidaID`, `TipoHormigon`, `InicioPlanificado`,
  `TemperaturaColocacion_C`, `Moldaje`, `Aislacion`, `RetiroMoldaje_h`.
- Solver de difusión térmica 1D con condición de Dirichlet constante.
- Verificación analítica/numérica 1D.

## W2 — Extensión 2D/3D, condiciones de borde y verificación térmica

- Extensión del solver a 2D y 3D sobre grilla cartesiana regular.
- Condiciones de borde: conducción, convección hacia el ambiente e interacción
  térmica con el suelo.
- Verificación térmica con casos de referencia.

## W3 — Voxelización, activación de vertidas e hidratación

- Lectura de geometría y propiedades desde IFC con IfcOpenShell.
- Voxelización de la geometría.
- Generación de calor por hidratación y activación temporal de vertidas.
- Interfaces térmicas entre vertidas.

## W4 — Entorno, moldaje, clima y simulación determinista de 14 días

- Moldajes, aislación y retiro de moldajes según configuración.
- Temperatura de colocación y temperatura ambiente variable.
- Descarga y snapshot de datos meteorológicos reales (sin sobrescribir snapshots
  anteriores; cada snapshot registra fuente, modelo, fecha/hora de descarga,
  coordenadas, unidades, horizonte y variables).
- Simulación determinista del horizonte de 14 días.

## W5 — Incertidumbre, confiabilidad, Monte Carlo y HPC

- Incertidumbre de material, ejecución, clima y modelo.
- Confiabilidad y Monte Carlo.
- Ejecución de realizaciones independientes en HPC.

## Cierre — Comparación de planes y defensa

- Comparación de planes de construcción.
- Plan de Control de Temperatura.
- Defensa y demo.

## Interfaces CLI futuras (no implementadas en E00)

```text
mcplan simulate    plan.yaml     # simulación determinista de un plan de vertidas
mcplan reliability plan.yaml     # análisis de confiabilidad / Monte Carlo
mcplan compare     plan_A.yaml plan_B.yaml   # comparación de dos planes
```

En E00 **no** se implementan comandos vacíos que aparenten realizar estas
funciones.

## Criterios térmicos del curso (referencia)

- Temperatura máxima: 70 °C.
- Diferencial térmico núcleo–superficie: 20 °C durante todo el análisis.
- Evaluación sobre los máximos de 14 días; superficie representada a ~25 mm bajo
  las superficies exteriores (discretización y extracción por justificar).
- Son criterios docentes: no se afirma que ICH exija siempre 70 °C ni un
  diferencial fijo de 20 °C. Cumplir el diferencial es control del riesgo de
  agrietamiento; no demuestra mecánicamente ausencia de grietas.

## Geometría de referencia (por validar)

Caso de Ju y Lei (2019): fundación de ~18 m × 18 m, espesor 3,30 m, parte
superior cilíndrica de ~7 m de diámetro. Estos datos **no** bastan para
reconstruir todos los detalles; la geometría oficial deberá ser entregada o
validada por el profesor. No se inventan dimensiones faltantes.
