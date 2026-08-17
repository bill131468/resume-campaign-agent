[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Local environment not found. Run scripts\setup_local.ps1 first."
}

Set-Location $projectRoot
& $venvPython -m pytest -q

$node = Get-Command node -ErrorAction SilentlyContinue
if ($node) {
    & $node.Source --test browser_extension/auth-utils.test.js browser_extension/journey-utils.test.js browser_extension/permission-utils.test.js tests/app-utils.test.js
    @(
        "browser_extension/service-worker.js",
        "browser_extension/panel.js",
        "browser_extension/content.js",
        "browser_extension/auth-content.js",
        "browser_extension/journey-content.js",
        "browser_extension/submit-content.js",
        "src/resume_campaign_agent/static/app-utils.js",
        "src/resume_campaign_agent/static/app.js"
    ) | ForEach-Object { & $node.Source --check $_ }
} else {
    Write-Warning "Node.js not found; browser extension tests were skipped."
}

$manifest = Get-Content -Raw -Encoding UTF8 "browser_extension\manifest.json" | ConvertFrom-Json
if ($manifest.version -ne "0.7.1") { throw "Unexpected extension version: $($manifest.version)" }
if (($manifest.host_permissions -join ",") -ne "http://127.0.0.1:18010/*") {
    throw "Local extension has unexpected fixed host permissions"
}
$worker = Get-Content -Raw -Encoding UTF8 "browser_extension\service-worker.js"
if ($worker.Contains("chrome.permissions.request")) {
    throw "Site permission requests must not run from the service worker"
}
Write-Host "Local verification passed." -ForegroundColor Green
