# Cómo contribuir — Repositorio compartido del Grupo 1

Trabajamos en un **único repositorio de equipo** en GitHub, con acceso de
escritura para los integrantes autorizados.

## Principios de colaboración

- Cada integrante usa **su propia cuenta** de GitHub.
- Cada integrante trabaja en **su propio clon** local del repositorio.
- **Una rama por tarea**; los cambios se integran mediante **Pull Requests** hacia `main`.
- **Revisión por otro integrante** cuando sea posible antes de integrar.
- **Actualiza tu copia local** (`git pull` en `main`) antes de comenzar una tarea.
- **Commits pequeños** con mensajes claros en español.
- **Nunca usar force push sobre `main`** (`git push --force` está prohibido en `main`).
- Mantener `main` siempre utilizable (las pruebas deben pasar).
- **Declarar el SHA exacto** del commit en cada entrega/actividad evaluada.
- **No compartir credenciales** (tokens, contraseñas, llaves) por chat, issues ni commits.

> Importante: compartir el enlace del repositorio **no** concede permisos de
> escritura. Hay que agregar colaboradores desde GitHub (o usar una organización
> con permisos adecuados).

## Nombres de rama

Usa nombres sencillos y descriptivos:

- `feat/configuracion-sitio`
- `docs/registro-equipo`
- `feat/solver-1d`
- `fix/error-yaml`

Prefijo sugerido: `feat/` (funcionalidad), `fix/` (corrección), `docs/`
(documentación), `test/` (pruebas), `chore/` (mantención).

## Flujo completo paso a paso

### 1. El propietario crea el repositorio

- En GitHub: New repository.
- Nombre sugerido (libre para el equipo): p. ej. `p2-mcoc-grupo1`.
- Visibilidad: **elegir en equipo** (privado o público; no asumir ninguna).
- **No** inicializar con README, .gitignore ni licencia si ya tenemos historial
  local (para evitar conflictos en el primer push).

### 2. Agregar colaboradores

Como propietario: **Settings → Collaborators and teams → Add people**.
Introduce los nombres de usuario de GitHub de cada integrante y envía la
invitación con permisos de **Write**.

### 3. Aceptar la invitación

Cada integrante recibe un correo/notificación de GitHub y debe aceptar la
invitación antes de poder hacer push.

### 4. Clonar el repositorio

```powershell
git clone <URL-del-repositorio.git>
cd <nombre-del-repositorio>
```

### 5. Crear una rama para tu tarea

```powershell
git switch main
git pull
git switch -c feat/nombre-de-la-tarea
```

### 6. Instalar el proyecto

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### 7. Ejecutar las pruebas

```powershell
python -m pytest -q
```

No subas cambios que rompan las pruebas en `main`.

### 8. Subir la rama

```powershell
git add <archivos>
git commit -m "Descripción clara y breve del cambio"
git push -u origin feat/nombre-de-la-tarea
```

### 9. Abrir un Pull Request

- En GitHub: **Compare & pull request** desde tu rama hacia `main`.
- Título claro y descripción breve de qué cambia y por qué.
- Pide revisión a otro integrante cuando sea posible.
- Espera la aprobación y que la CI pase antes de integrar.

### 10. Actualizar `main` después de integrar

```powershell
git switch main
git pull
git branch -d feat/nombre-de-la-tarea   # limpiar rama local ya integrada
```

## Protección de `main` (recomendada vs. aplicada)

**Configuración recomendada** (si la cuenta lo permite, en el plan gratuito de
cuenta personal o de organización):

- Settings → Branches → Add branch protection rule sobre `main`:
  - **Require a pull request before merging** (con al menos 1 revisión si es posible).
  - **Require status checks to pass before merging** (la job `test` del workflow CI).
  - **Do not allow force pushes**.

**Configuración realmente aplicada:** ninguna todavía. Depende de la cuenta
propietaria del repositorio (no hemos podido verificar GitHub desde este entorno).
Queda pendiente que el propietario la configure y lo declare aquí:

- Estado: PENDIENTE.
- Quién configura: propietario del repositorio (por definir).

Mientras no exista protección, el acuerdo del equipo es no hacer force push sobre
`main` y mantenerlo siempre utilizable.

## Declaración de evidencia en entregas

Toda actividad evaluada debe declarar:

```text
Repositorio: <URL>
Commit evaluado: <SHA completo>
```

El SHA declarado queda **congelado** para esa actividad una vez iniciada la
evaluación. Puedes seguir desarrollando en commits posteriores sin cambiar la
evidencia ya declarada.

## Qué no subir al repositorio

- Tokens, contraseñas ni llaves.
- `.venv/` ni cachés (`__pycache__/`, `.pytest_cache/`, etc.).
- Archivos temporales.
- Resultados pesados generados (se ignoran en `.gitignore`).
- Datos personales innecesarios.
