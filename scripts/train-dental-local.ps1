param([string]$Dataset = '', [string]$Output = '')
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$servicePath = Join-Path $taskRoot 'ai-service'
if (-not $Dataset) { $Dataset = Join-Path $servicePath 'training-data' }
if (-not $Output) { $Output = Join-Path $servicePath 'models/dental-local' }
# Prefer the managed interpreter; dependencies remain in the project venv.
$taskPython = Join-Path $env:APPDATA 'uv/python/cpython-3.12-windows-x86_64-none/python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { $taskPython = Join-Path $servicePath '.venv/Scripts/python.exe' }
$previousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $servicePath '.venv/Lib/site-packages'
    & $taskPython (Join-Path $servicePath 'scripts/train-dental-local.py') --dataset $Dataset --output $Output
    $trainingExitCode = $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $previousPythonPath
}
exit $trainingExitCode
