[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 18010,
    [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Local environment not found. Run scripts\setup_local.ps1 first."
}

$env:APP_ENV = "production"
$env:ENABLE_TEST_FIXTURES = "false"
$env:AGENT_HOST = "127.0.0.1"
$env:AGENT_PORT = [string]$Port

if ($OpenBrowser) {
    Start-Process "http://127.0.0.1:$Port/"
}

Set-Location $projectRoot
& $venvPython -m resume_campaign_agent
