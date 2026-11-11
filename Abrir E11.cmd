@echo off
setlocal
cd /d "%~dp0proyecto"
if not exist ".venv\Scripts\python.exe" (
  echo No se encontro el entorno Python del proyecto.
  pause
  exit /b 1
)
echo Abriendo E11: resultado 3D guardado.
echo Puede girar con el mouse y acercar con la rueda.
".venv\Scripts\python.exe" "scripts\demo_e11.py" --guardado --abrir
if errorlevel 1 (
  echo No se pudo abrir E11. Revise el mensaje anterior.
  pause
)
