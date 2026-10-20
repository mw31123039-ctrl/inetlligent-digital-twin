param([switch]$SkipInstall)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
function Invoke-Checked([scriptblock]$Command) {
    & $Command
    if ($LASTEXITCODE -ne 0) { throw 'A setup command failed. Resolve the error above before continuing.' }
}
function Read-EnvValue([string]$File, [string]$Name) {
    $taskMatch = [regex]::Match([IO.File]::ReadAllText($File), '(?m)^' + [regex]::Escape($Name) + '=(.*)$')
    return $taskMatch.Groups[1].Value.Trim().Trim('"').Trim("'")
}
function Write-EnvValue([string]$File, [string]$Name, [string]$Value) {
    $taskText = [IO.File]::ReadAllText($File)
    $taskPattern = '(?m)^' + [regex]::Escape($Name) + '=.*$'
    if ([regex]::IsMatch($taskText, $taskPattern)) { $taskText = [regex]::Replace($taskText, $taskPattern, ($Name + '=' + $Value)) }
    else { $taskText += "`n$Name=$Value`n" }
    [IO.File]::WriteAllText($File, $taskText, [Text.UTF8Encoding]::new($false))
}
$taskPhp = (Get-Command php -ErrorAction Stop).Source
$taskUvCommand = Get-Command uv -ErrorAction SilentlyContinue
$taskUv = if ($taskUvCommand) { $taskUvCommand.Source } else { Join-Path $env:USERPROFILE '.local/bin/uv.exe' }
if (!(Test-Path -LiteralPath $taskUv)) { throw 'Install uv from https://docs.astral.sh/uv/ before setup.' }
Push-Location $taskRoot
try {
    if (!$SkipInstall) {
        $taskComposerCommand = Get-Command composer -ErrorAction SilentlyContinue
        Push-Location backend
        try {
            if ($taskComposerCommand) { Invoke-Checked { & $taskComposerCommand.Source install --no-interaction --prefer-dist } }
            else {
                $taskComposer = Join-Path $env:LOCALAPPDATA 'Programs/Composer/composer.phar'
                if (!(Test-Path -LiteralPath $taskComposer)) { throw 'Install Composer or add it to PATH.' }
                Invoke-Checked { & $taskPhp $taskComposer install --no-interaction --prefer-dist }
            }
        } finally { Pop-Location }
        Push-Location ai-service
        try { Invoke-Checked { & $taskUv sync --frozen --python 3.12 } } finally { Pop-Location }
        Push-Location frontend
        try { Invoke-Checked { npm ci } } finally { Pop-Location }
    }
    foreach ($taskDirectory in @('backend', 'ai-service')) {
        $taskEnv = Join-Path $taskRoot "$taskDirectory/.env"
        if (!(Test-Path -LiteralPath $taskEnv)) { Copy-Item -LiteralPath (Join-Path $taskRoot "$taskDirectory/.env.example") -Destination $taskEnv }
    }
    $taskApiEnv = Join-Path $taskRoot 'backend/.env'
    $taskAiEnv = Join-Path $taskRoot 'ai-service/.env'
    $taskKey = Read-EnvValue $taskApiEnv 'AI_SERVICE_KEY'
    $taskOtherKey = Read-EnvValue $taskAiEnv 'SERVICE_KEY'
    if (!$taskKey) { $taskKey = $taskOtherKey }
    if (!$taskKey) {
        $taskBytes = New-Object byte[] 40
        $taskRandom = [Security.Cryptography.RandomNumberGenerator]::Create()
        try { $taskRandom.GetBytes($taskBytes) } finally { $taskRandom.Dispose() }
        $taskKey = ([BitConverter]::ToString($taskBytes)).Replace('-', '').ToLowerInvariant()
    }
    if ($taskOtherKey -and $taskOtherKey -ne $taskKey) { throw 'The internal service keys differ. Configure matching server keys in the two .env files.' }
    if ($taskKey.Length -lt 32) { throw 'The internal service key must have at least 32 characters.' }
    Write-EnvValue $taskApiEnv 'AI_SERVICE_KEY' $taskKey
    Write-EnvValue $taskAiEnv 'SERVICE_KEY' $taskKey
    if (!(Read-EnvValue $taskApiEnv 'APP_KEY')) { Invoke-Checked { & $taskPhp backend/artisan key:generate --force --no-interaction } }
    if (!(Test-Path -LiteralPath 'backend/database/database.sqlite')) { New-Item -ItemType File -Path 'backend/database/database.sqlite' | Out-Null }
    Invoke-Checked { & $taskPhp backend/artisan migrate --force --no-interaction }
    Write-Host 'Setup complete. Server keys were not printed. Configure external AI separately in ai-service/.env.'
} finally { Pop-Location }
