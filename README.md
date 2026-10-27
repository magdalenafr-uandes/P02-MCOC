# mcplan — Planificación de vertidas de hormigón masivo (Grupo 1)

Proyecto universitario (P2 MCOC) para diseñar, justificar y defender un **plan de
construcción por vertidas** de una fundación de hormigón masivo, sustentado en
simulación térmica y análisis de confiabilidad.

El flujo previsto es:

```
BIM → IFC → geometría y propiedades → voxelización → solver →
métricas → confiabilidad → recomendación constructiva
```

El horizonte de análisis será de **14 días** desde el inicio de la primera vertida.
El núcleo numérico (solver térmico 3D sobre grilla cartesiana) será desarrollado por
el equipo; no se usará Kratos, ANSYS, OpenSees u otro solver como sustituto.

## Alcance implementado

### E00 — Kickoff y registro de repositorio

- Paquete Python instalable en modo editable (raíz del repositorio).
- CLI `mcplan info`.
- Configuración oficial del sitio en `configs/site.yaml`.
- Pruebas automatizadas con `pytest` y CI en GitHub Actions.
- Documentación de colaboración.

### Proyecto activo (subcarpeta `proyecto/`) — hitos E01 y E02

El trabajo del capstone vive en [`proyecto/`](proyecto/): modelo **IFC4** de
la fundación de 5 vertidas (`foundation.ifc`, geometría docente de la guía
Bonsai), lectores con IfcOpenShell (selección semántica por pset), **solver
térmico 1D explícito (FTCS)** con Dirichlet, Neumann adiabática y Robin, y
**verificación analítica** (solución sinusoidal exacta) con demos de Δx y
Δt (`--nx`, `--dt-scale`). E01 y E02 son hitos documentados del mismo
proyecto; no hay código duplicado por entrega.

Detalle, instalación y comandos en [`proyecto/README.md`](proyecto/README.md);
preparación oral en [`proyecto/docs/guia_estudio.md`](proyecto/docs/guia_estudio.md).

> **Nota:** la raíz (E00) y `proyecto/` contienen dos distribuciones
> distintas ambas llamadas `mcplan` (raíz: solo PyYAML, con la CLI;
> proyecto: NumPy, Matplotlib e IfcOpenShell). Cada una tiene su entorno
> virtual; no se instalan en la misma venv.

**E04:** solver térmico **2D/3D por balance de voxel** con Dirichlet,
Neumann (flujo impuesto y adiabático), Robin (convección + aislación),
fuente volumétrica, dos materiales y criterio de estabilidad general
dt ≤ min C/ΣG; verificación 2D/3D y voxelización preliminar de la
fundación. Guía oral en [`proyecto/docs/guia_e04.md`](proyecto/docs/guia_e04.md).

**Aún no implementado:** lectura de mallas IFC para voxelizar, hidratación,
activación de vertidas, meteorología, Monte Carlo, HPC y la simulación
de 14 días.

## Sitio oficial del Grupo 1

| Dato | Valor |
| --- | --- |
| Grupo | G1 |
| Sitio de referencia | Taltal / Zona de Reserva Eólica |
| Región | Antofagasta, Chile |
| Proyecto eólico de referencia | Parque Eólico Wayra |
| Estado/contexto (material docente) | proyectado / evaluado |
| Latitud meteorológica oficial | -24.952830 |
| Longitud meteorológica oficial | -70.004838 |
| Zona horaria | America/Santiago |
| Fuente documental | https://infofirma.sea.gob.cl/DocumentosSEA/MostrarDocumento?docId=b6/3a/d2cc556e10c4845faba1868e1e97666a88fe |

Las coordenadas son el **punto meteorológico oficial del caso docente** y no deben
presentarse como la ubicación exacta de una fundación real. El estado/contexto
proviene del material del curso y no es una verificación actualizada del proyecto.

`configs/site.yaml` es la **única fuente de configuración del sitio**. Los futuros
módulos meteorológicos deben leer exactamente esas coordenadas, salvo autorización
explícita del profesor.

## Requisitos

- Python 3.10 o superior.
- Git.
- Windows PowerShell (los comandos de este README están verificados en Windows).

## Instalación (Windows PowerShell)

Desde la raíz del repositorio:

```powershell
# 1. Crear el entorno virtual
python -m venv .venv

# 2. Activarlo
.venv\Scripts\Activate.ps1

# 3. Actualizar pip e instalar el proyecto en modo editable con dependencias de desarrollo
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

> Si la activación falla por la política de ejecución de PowerShell, habilítela
> **solo para la sesión actual** (no cambia la configuración global):
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

## Ejecución de la CLI

```powershell
# Usa la configuración por defecto: configs/site.yaml (relativo al directorio actual)
mcplan info

# Indicando explícitamente el archivo de configuración
mcplan info --site configs/site.yaml
```

Salida esperada (datos del sitio):

```
Proyecto:       Planificación de vertidas de hormigón masivo
Grupo:          G1
Etapa actual:   E00
Parque eólico:  Parque Eólico Wayra
Sitio:          Taltal / Zona de Reserva Eólica, Región de Antofagasta
Latitud:        -24.952830
Longitud:       -70.004838
Zona horaria:   America/Santiago
Fuente:         https://infofirma.sea.gob.cl/...
```

**Ruta por defecto:** `configs/site.yaml` relativo al directorio de trabajo actual.
Si el archivo no existe o es inválido, la CLI muestra un error claro en `stderr` y
termina con código de salida `2`.

## Ejecución de pruebas

E00 (CLI y configuración del sitio), con el paquete de la raíz instalado:

```powershell
python -m pytest -q
```

Proyecto (solver 1D y modelo IFC de la fundación), con el paquete de
`proyecto/` instalado en un entorno virtual separado:

```powershell
py -3.12 -m venv proyecto\.venv
.\proyecto\.venv\Scripts\python.exe -m pip install --upgrade pip
.\proyecto\.venv\Scripts\python.exe -m pip install -e "proyecto[dev]"
.\proyecto\.venv\Scripts\python.exe -m pytest proyecto -q
```

Ambos conjuntos de pruebas se ejecutan también en GitHub Actions
(ver `.github/workflows/ci.yml`).

## Incorporación al repositorio compartido

El repositorio es de **equipo** (un único repositorio, con acceso de escritura para
los integrantes autorizados). Compartir el enlace **no** concede permisos de
escritura: es necesario agregar colaboradores o usar una organización con permisos
adecuados.

Instrucciones detalladas en [CONTRIBUTING.md](CONTRIBUTING.md).

Resumen:

1. El propietario crea el repositorio en GitHub.
2. Agrega a los colaboradores (Settings → Collaborators).
3. Cada integrante acepta la invitación.
4. Cada integrante clona el repositorio en su equipo.
5. Crea una rama por tarea (p. ej. `feat/configuracion-sitio`).
6. Instala el proyecto (secciones anteriores).
7. Ejecuta las pruebas.
8. Sube la rama (`git push -u origin <rama>`).
9. Abre un Pull Request hacia `main`.
10. Actualiza `main` local tras integrar cambios (`git switch main; git pull`).

## Hoja de ruta

Ver [docs/hoja_de_ruta.md](docs/hoja_de_ruta.md). Interfaces futuras previstas
(no implementadas en E00):

```text
mcplan simulate  plan.yaml
mcplan reliability plan.yaml
mcplan compare   plan_A.yaml plan_B.yaml
```

## Registro de evidencia

- E00: [docs/registro_e00.md](docs/registro_e00.md) (integrantes, URL y SHA inicial).
- Proyecto (hitos E01/E02): [proyecto/docs/guia_estudio.md](proyecto/docs/guia_estudio.md)
  (guía de estudio y checklist); evidencia del round-trip E02 en
  [proyecto/docs/evidencia_e02/](proyecto/docs/evidencia_e02/) una vez
  realizada la edición manual en Bonsai.

## Datos todavía pendientes

- **Usuarios de GitHub** de los integrantes (los nombres ya están en
  `docs/registro_e00.md`; faltan los usuarios para las invitaciones de
  colaboración).
- **Geometría oficial** de la fundación (debe entregarla o validarla el
  profesor; la del IFC en `proyecto/geometry/` es la geometría docente de la
  guía Bonsai del capstone).
- **Datos meteorológicos** y sus snapshots (etapas posteriores).
