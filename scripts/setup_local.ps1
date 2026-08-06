[CmdletBinding()]
param(
    [switch]$SkipVerification
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvRoot = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"

Set-Location $projectRoot

if (-not (Test-Path -LiteralPath $venvPython)) {
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        & $pyLauncher.Source -3 -m venv $venvRoot
    } else {
        $pythonLauncher = Get-Command python -ErrorAction Stop
        & $pythonLauncher.Source -m venv $venvRoot
    }
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Python virtual environment was not created. Install Python 3.11 or 3.12 and retry."
}

& $venvPython -c "import sys; assert sys.version_info >= (3, 11), sys.version"
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -e ".[test]"

if (-not $SkipVerification) {
    & (Join-Path $PSScriptRoot "verify_local.ps1")
}

Write-Host "Local setup complete. Start with scripts\start_local.ps1" -ForegroundColor Green
