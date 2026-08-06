[CmdletBinding()]
param(
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$version = "0.2.2"
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $projectRoot "release"
}
$outputRoot = [System.IO.Path]::GetFullPath($OutputDirectory)
$temporaryRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$stageRoot = Join-Path $temporaryRoot ("resume-campaign-local-" + [guid]::NewGuid().ToString("N"))
$packageName = "resume-campaign-agent-local-source-$version"
$packageStage = Join-Path $stageRoot $packageName
$archive = Join-Path $outputRoot "$packageName.zip"

try {
    New-Item -ItemType Directory -Path $packageStage -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $packageStage "docs") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $packageStage "scripts") -Force | Out-Null

    @(
        ".env.example",
        ".gitignore",
        "BROWSER_EXTENSION.md",
        "CHANGELOG.md",
        "CODE_OF_CONDUCT.md",
        "CONTRIBUTING.md",
        "LICENSE",
        "NOTICE",
        "pyproject.toml",
        "SECURITY.md"
    ) | ForEach-Object {
        Copy-Item -LiteralPath (Join-Path $projectRoot $_) -Destination $packageStage
    }
    Copy-Item -LiteralPath (Join-Path $projectRoot "LOCAL_README.md") -Destination (Join-Path $packageStage "README.md")
    Copy-Item -LiteralPath (Join-Path $projectRoot "docs\AI_HANDOFF_LOCAL.md") -Destination (Join-Path $packageStage "AI_HANDOFF.md")

    @("src", "browser_extension", "tests") | ForEach-Object {
        Copy-Item -LiteralPath (Join-Path $projectRoot $_) -Destination $packageStage -Recurse
    }
    @(
        "API.md",
        "ARCHITECTURE.md",
        "LOCAL_USER_GUIDE.md",
        "SECURITY.md",
        "TESTING.md",
        "TROUBLESHOOTING.md"
    ) | ForEach-Object {
        Copy-Item -LiteralPath (Join-Path $projectRoot "docs\$_") -Destination (Join-Path $packageStage "docs")
    }
    @(
        "build_local_source.ps1",
        "check_local_package.py",
        "check_public_release.py",
        "setup_local.ps1",
        "start_local.ps1",
        "verify_local.ps1"
    ) | ForEach-Object {
        Copy-Item -LiteralPath (Join-Path $projectRoot "scripts\$_") -Destination (Join-Path $packageStage "scripts")
    }

    Get-ChildItem -LiteralPath $packageStage -Recurse -Directory |
        Where-Object { $_.Name -in @("__pycache__", ".pytest_cache") } |
        Sort-Object FullName -Descending |
        ForEach-Object {
            if ($_.FullName.StartsWith($packageStage, [System.StringComparison]::OrdinalIgnoreCase)) {
                Remove-Item -LiteralPath $_.FullName -Recurse -Force
            }
        }

    New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
    Compress-Archive -Path $packageStage -DestinationPath $archive -CompressionLevel Optimal -Force

    $venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
    $python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { (Get-Command python -ErrorAction Stop).Source }
    & $python (Join-Path $projectRoot "scripts\check_local_package.py") $archive
    if ($LASTEXITCODE -ne 0) { throw "Local source package validation failed" }

    Get-FileHash -Algorithm SHA256 $archive | Select-Object Path, Hash
}
finally {
    $resolvedStage = [System.IO.Path]::GetFullPath($stageRoot)
    if ($resolvedStage.StartsWith($temporaryRoot, [System.StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $resolvedStage)) {
        Remove-Item -LiteralPath $resolvedStage -Recurse -Force
    }
}
