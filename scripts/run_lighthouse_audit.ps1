# ==============================================================================
# Flama - Run Lighthouse Audit with Isolated Test Profile
# ==============================================================================
# Golden Rule: Never use the user's default/personal profile for audits.
# ==============================================================================

param (
    [string]$Url = "http://localhost:5173",
    [string]$Categories = "seo,performance,accessibility,best-practices",
    [string]$ProfileDir = "$env:USERPROFILE\.gemini\chrome-profiles\flama-devtools",
    [string]$OutputDir = "reports/lighthouse",
    [ValidateSet("desktop", "mobile")]
    [string]$FormFactor = "desktop",
    [switch]$NoView
)

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "🔍 Flama Lighthouse Audit (Isolated Test Profile)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Ensure report directory exists
$resolvedOutputDir = Join-Path (Get-Location) $OutputDir
if (-not (Test-Path $resolvedOutputDir)) {
    New-Item -ItemType Directory -Force -Path $resolvedOutputDir | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$reportBasePath = Join-Path $resolvedOutputDir "lighthouse_${FormFactor}_${timestamp}"

Write-Host " Target URL        : $Url" -ForegroundColor Green
Write-Host " Categories        : $Categories" -ForegroundColor Green
Write-Host " Form Factor       : $FormFactor" -ForegroundColor Green
Write-Host " Isolated Profile  : $ProfileDir" -ForegroundColor Green
Write-Host " Report Output     : $reportBasePath.report.html" -ForegroundColor Green
Write-Host "------------------------------------------------------------"

# 2. Build Chrome Flags
$chromeFlags = "--user-data-dir=`"$ProfileDir`" --no-first-run --no-default-browser-check"

# 3. Build Lighthouse CLI Arguments
$argsList = @(
    "`"$Url`"",
    "--chrome-flags=`"$chromeFlags`"",
    "--only-categories=$Categories",
    "--output=html",
    "--output=json",
    "--output-path=`"$reportBasePath`""
)

if ($FormFactor -eq "desktop") {
    $argsList += "--preset=desktop"
} else {
    $argsList += "--form-factor=mobile"
}

if (-not $NoView) {
    $argsList += "--view"
}

Write-Host "🚀 Executing Lighthouse audit..." -ForegroundColor Yellow

# Prefer local frontend node_modules if available, otherwise npx
$localLighthouse = "d:\Project\nihongo\frontend\node_modules\.bin\lighthouse.cmd"
if (Test-Path $localLighthouse) {
    & $localLighthouse @argsList
} else {
    npx -y lighthouse @argsList
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "✅ Audit completed! Report generated at:" -ForegroundColor Green
Write-Host "   📄 HTML: $reportBasePath.report.html" -ForegroundColor Cyan
Write-Host "   📄 JSON: $reportBasePath.report.json" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
