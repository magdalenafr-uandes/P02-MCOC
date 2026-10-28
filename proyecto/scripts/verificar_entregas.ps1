# Ejecutar desde cualquier carpeta: verifica ambos paquetes sin mezclarlos.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$repo = Split-Path -Parent $repo
$pythonRaiz = Join-Path $repo '.venv\Scripts\python.exe'
$pythonProyecto = Join-Path $repo 'proyecto\.venv\Scripts\python.exe'
foreach ($python in @($pythonRaiz, $pythonProyecto)) {
    if (-not (Test-Path -LiteralPath $python)) {
        throw "Falta el entorno: $python. Sigue la instalación de proyecto/README.md."
    }
}
$identificador = [guid]::NewGuid().ToString('N')
$temporal = Join-Path $repo "proyecto\results\tmp\entregas_$identificador"
New-Item -ItemType Directory -Force -Path $temporal | Out-Null
Push-Location $repo
try {
    & $pythonRaiz -m pytest tests -q -o 'addopts=' --basetemp (Join-Path $temporal 'raiz')
    if ($LASTEXITCODE -ne 0) { throw 'Fallaron las pruebas de la raíz.' }
    & $pythonProyecto -m pytest proyecto/tests -v -s -o 'addopts=' --basetemp (Join-Path $temporal 'proyecto')
    if ($LASTEXITCODE -ne 0) { throw 'Fallaron las pruebas del proyecto.' }
    Write-Host 'Ambas suites aprobadas. Falta publicar un commit para declarar el SHA en Canvas.'
}
finally {
    Pop-Location
}
