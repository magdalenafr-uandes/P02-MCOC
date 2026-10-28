# Evidencia local E04/E05 — versión integrada

Preparada el 27 de octubre de 2026 sobre `bbf6150bb8d419e99487f77aac52a00f495952ed`.
Es evidencia de ejecución local; no acredita evaluación ni publicación.

## Resultados reales

- `tests.txt`: **83 tests del proyecto aprobados en 15.30 s** y **5 tests de la
  raíz aprobados en 0.16 s**, Python 3.12.10.
- `demostraciones.txt`: scripts 2D/3D regenerados con temperatura superficial y
  figura de estabilidad corregidas.
- `voxelizacion.txt`: error total y por vertida para d=0.4,0.2,0.1 m.
- `inspeccion_ifc.txt`: IFC existente, cinco vertidas, 636.78 m³.
- Figuras en `../../results/figures/`; estabilidad y bordes revisados visualmente.

El comando `scripts/verificar_entregas.ps1` ejecutó ambas suites. Usa una carpeta
temporal nueva dentro de `results/tmp/` en cada corrida, evitando el problema
de permisos del temporal externo del entorno.

## Correcciones y compatibilidad

1. `dt_max` se documenta como criterio suficiente conservador de monotonía,
   distinto del límite espectral. Una regresión comprueba ambos en una caja 2D.
2. `temperatura_superficie` reconstruye la cara del sólido; Dirichlet devuelve
   exactamente la temperatura impuesta. Los gráficos usan esa cara.
3. `voxel.py` es el motor único, ampliado a 1D/2D/3D. `solver_nd.py` delega en él.
4. La demostración `verification_nd.py` permite cambiar malla, longitudes, tiempo,
   propiedades, fuente, flujo, convección y aislación desde la consola.
5. La fuente temporal se evalúa una sola vez por paso, tanto para el balance como
   para la contabilidad de energía.

Signos: el motor y la demostración usan Neumann positivo ENTRANDO. La API
auxiliar `MallaTermica` conserva el signo saliente de la preparación anterior y
lo traduce al motor. El solver nodal histórico conserva su propia API.

En el ejemplo de bordes a 7 días: Robin sin aislación da Ts=29.72 °C,
Robin con aislación Ts=51.07 °C y Dirichlet Ts=20.00 °C. Son ejemplos con fuente
constante; no son una evaluación del caso real con hidratación y clima.

## Conservación del trabajo previo

Se integraron los commits del compañero sin regenerar el IFC.
Se contrastaron con el ZIP de respaldo los archivos previos del equipo:
IFC, figura 1D y JSON de defensa conservan bytes idénticos; el script 1D y el
generador BIM conservan contenido idéntico, con normalización de fin de línea de Git.
`.gitignore` conserva tanto las reglas remotas como las exclusiones personales locales.

Respaldo adicional: `results/respaldo_local_pre_integracion.zip` (27 archivos,
verificado al generarlo) y stash `Respaldo local previo a integrar E04 E05`.
Ambos se conservaron. La rama local `codex/e04-e05-termica` ya parte del commit remoto.
Este registro se generó antes de publicar. Para Canvas usar el SHA del commit
que contiene estos archivos, consultable con `git rev-parse HEAD`.

## Comprobación BIM

`Proyecto2.blend` se abrió en segundo plano con Blender 5.2.2 LTS, ejecución
automática de scripts desactivada, sin modificarlo: contiene nueve objetos.
Esto confirma lectura del archivo, no una revisión visual de Bonsai o de sus paneles.
La inspección IFC comprueba las cinco vertidas y propiedades mediante IfcOpenShell.

La voxelización usa el generador paramétrico; no lee cambios de malla del IFC ni
acopla todavía la fundación irregular al solver. Persisten campos de moldaje y
aislación por definir. Hidratación realista, clima y confiabilidad son etapas futuras.

Guía y comandos: `../e04_e05.md`. Defensa detallada: `../guia_e04.md`.
