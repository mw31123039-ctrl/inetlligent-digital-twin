param([ValidateRange(1,500)][int]$Epochs = 30, [switch]$Download)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$servicePath = Join-Path $taskRoot 'ai-service'
$taskPython = Join-Path $env:APPDATA 'uv/python/cpython-3.12-windows-x86_64-none/python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { $taskPython = Join-Path $servicePath '.venv/Scripts/python.exe' }
$previousPythonPath = $env:PYTHONPATH
Push-Location -LiteralPath $servicePath
try {
    $env:PYTHONPATH = Join-Path $servicePath '.venv/Lib/site-packages'
    $trainingArguments = @('scripts/train-dental-public.py', '--epochs', $Epochs)
    if ($Download) { $trainingArguments += '--download' }
    & $taskPython @trainingArguments
    $trainingExitCode = $LASTEXITCODE
} finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
exit $trainingExitCode
