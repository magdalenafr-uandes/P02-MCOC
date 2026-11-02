@echo off
setlocal
if not exist "%~dp0proyecto\.venv\Scripts\pythonw.exe" (
  echo Falta el entorno Python del proyecto. Revisa la instalacion en proyecto\README.md.
  pause
  exit /b 1
)
start "" "%~dp0proyecto\.venv\Scripts\pythonw.exe" "%~dp0proyecto\scripts\abrir_visualizador.py"
exit /b 0
