# Instrucciones para Claude — P02-MCOC (Grupo 1)

Proyecto `mcplan`: planificación y análisis térmico de vertidas de hormigón
masivo. Código en `src/mcplan/`, pruebas en `tests/`, entregas en `proyecto/`.
Ver también `README.md` y `CONTRIBUTING.md`.

## Commits

- **Al terminar cada cambio que funcione, haz commit** sin esperar a que te lo pidan.
- Antes de cada commit ejecuta `python -m pytest -q`; no hagas commit si las pruebas fallan
  (avisa del fallo en vez de commitear).
- Commits pequeños, un cambio lógico por commit.
- Mensajes en español, claros y breves. Si el cambio es de una entrega, usa el prefijo
  de la entrega como en el historial (p. ej. `E04: ...`); si no, `docs:`, `ci:`, `fix:`, etc.
- Agrega solo los archivos del cambio (`git add <archivos>`), nunca `git add -A` a ciegas.
  No subas `.venv/`, cachés, resultados pesados ni credenciales (ver `.gitignore`).
- Usa la herramienta Bash para los comandos git.

## Push

- **No hagas push automáticamente.** Haz push solo cuando el usuario lo pida.
- Nunca `git push --force` sobre `main`.
