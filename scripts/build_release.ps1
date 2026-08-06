param(
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $projectRoot "release"
}
$outputRoot = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null

$temporaryRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$stageRoot = Join-Path $temporaryRoot ("resume-campaign-release-" + [guid]::NewGuid().ToString("N"))
$serverStage = Join-Path $stageRoot "resume-campaign-agent-server"
$extensionStage = Join-Path $stageRoot "resume-campaign-agent-extension-v0.7.1"

try {
    New-Item -ItemType Directory -Path $serverStage -Force | Out-Null
    New-Item -ItemType Directory -Path $extensionStage -Force | Out-Null

    @(
        "Dockerfile",
        "compose.yaml",
        ".dockerignore",
        ".env.server.example",
        "pyproject.toml",
        "README.md",
        "DEPLOY_SERVER.md"
    ) | ForEach-Object {
        Copy-Item -LiteralPath (Join-Path $projectRoot $_) -Destination $serverStage
    }
    Copy-Item -LiteralPath (Join-Path $projectRoot "src") -Destination $serverStage -Recurse
    Get-ChildItem -LiteralPath $serverStage -Recurse -Directory -Filter "__pycache__" | ForEach-Object {
        if ($_.FullName.StartsWith($stageRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $_.FullName -Recurse -Force
        }
    }
    @(
        "auth-content.js",
        "auth-utils.js",
        "bridge.js",
        "content.js",
        "journey-utils.js",
        "journey-content.js",
        "manifest.json",
        "panel.css",
        "panel.html",
        "panel.js",
        "permission-utils.js",
        "service-worker.js",
        "submit-content.js"
    ) | ForEach-Object {
        Copy-Item -LiteralPath (Join-Path $projectRoot "browser_extension\$_") -Destination $extensionStage
    }

    $serverArchive = Join-Path $outputRoot "resume-campaign-agent-server-0.2.2.zip"
    $extensionArchive = Join-Path $outputRoot "resume-campaign-agent-extension-v0.7.1.zip"
    Compress-Archive -Path (Join-Path $serverStage "*") -DestinationPath $serverArchive -CompressionLevel Optimal -Force
    Compress-Archive -Path (Join-Path $extensionStage "*") -DestinationPath $extensionArchive -CompressionLevel Optimal -Force

    Get-FileHash -Algorithm SHA256 $serverArchive, $extensionArchive |
        Select-Object Path, Hash
}
finally {
    $resolvedStage = [System.IO.Path]::GetFullPath($stageRoot)
    if ($resolvedStage.StartsWith($temporaryRoot, [System.StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $resolvedStage)) {
        Remove-Item -LiteralPath $resolvedStage -Recurse -Force
    }
}
