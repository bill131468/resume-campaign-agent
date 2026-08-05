param(
    [Parameter(Mandatory = $true)]
    [string]$Origin,
    [Parameter(Mandatory = $true)]
    [string]$OutputArchive
)

$ErrorActionPreference = "Stop"
$uri = [Uri]$Origin
if (-not $uri.IsAbsoluteUri -or $uri.Scheme -notin @("http", "https") -or $uri.AbsolutePath -ne "/") {
    throw "Origin must be an absolute HTTP(S) origin without a path"
}
$normalizedOrigin = $uri.GetLeftPart([System.UriPartial]::Authority)
$projectRoot = Split-Path -Parent $PSScriptRoot
$sourceRoot = Join-Path $projectRoot "browser_extension"
$temporaryRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$stageRoot = Join-Path $temporaryRoot ("resume-extension-origin-" + [guid]::NewGuid().ToString("N"))
$utf8 = New-Object System.Text.UTF8Encoding($false)

try {
    New-Item -ItemType Directory -Path $stageRoot -Force | Out-Null
    @(
        "auth-content.js", "auth-utils.js", "bridge.js", "content.js",
        "journey-utils.js", "journey-content.js",
        "manifest.json", "panel.css", "panel.html", "panel.js",
        "permission-utils.js", "service-worker.js", "submit-content.js"
    ) | ForEach-Object {
        $source = Join-Path $sourceRoot $_
        $destination = Join-Path $stageRoot $_
        $content = [System.IO.File]::ReadAllText($source, [System.Text.Encoding]::UTF8)
        $content = $content.Replace("http://127.0.0.1:18010", $normalizedOrigin)
        [System.IO.File]::WriteAllText($destination, $content, $utf8)
    }
    $outputPath = [System.IO.Path]::GetFullPath($OutputArchive)
    $outputParent = Split-Path -Parent $outputPath
    New-Item -ItemType Directory -Path $outputParent -Force | Out-Null
    Compress-Archive -Path (Join-Path $stageRoot "*") -DestinationPath $outputPath -CompressionLevel Optimal -Force
    Get-FileHash -Algorithm SHA256 $outputPath | Select-Object Path, Hash
}
finally {
    $resolvedStage = [System.IO.Path]::GetFullPath($stageRoot)
    if ($resolvedStage.StartsWith($temporaryRoot, [System.StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $resolvedStage)) {
        Remove-Item -LiteralPath $resolvedStage -Recurse -Force
    }
}
