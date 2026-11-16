# Restart the local HumanTwin AI service on 127.0.0.1:8001 after code or model changes.
# The copied virtual-environment python.exe is blocked by Application Control on this machine,
# so the uv-managed interpreter is used with the service's site-packages on PYTHONPATH.
# Usage (from the project root):  powershell -ExecutionPolicy Bypass -File scripts/start-ai-service.ps1
param([int]$Port = 8001)

$ErrorActionPreference = 'Stop'
$service = Join-Path $PSScriptRoot '..\ai-service' | Resolve-Path
$python = Join-Path $env:APPDATA 'uv\python\cpython-3.12-windows-x86_64-none\python.exe'
if (-not (Test-Path $python)) { $python = (& uv python find 3.12).Trim() }

# Stop an existing service on this port (an older process keeps serving old code until it is restarted).
$listeners = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
foreach ($listener in $listeners) {
  $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
  if ($process.CommandLine -match 'uvicorn' -and $process.CommandLine -match 'app\.main:app') {
    Write-Host "Stopping the previous AI service (PID $($process.ProcessId))"
    Stop-Process -Id $process.ProcessId -Force
  } else {
    throw "Port $Port is used by another program: $($process.CommandLine)"
  }
}
Start-Sleep -Milliseconds 800

$env:PYTHONPATH = Join-Path $service '.venv\Lib\site-packages'
$env:PYTHONDONTWRITEBYTECODE = '1'
Write-Host "Starting the AI service on http://127.0.0.1:$Port (Ctrl+C to stop)"
Set-Location $service
& $python -m uvicorn app.main:app --host 127.0.0.1 --port $Port --no-access-log
