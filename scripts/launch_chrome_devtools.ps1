# ==============================================================================
# Flama - Launch Chrome with Isolated Profile & Remote Debugging
# ==============================================================================
# Golden Rule: Never use the user's default/personal profile for DevTools/MCP.
# ==============================================================================

param (
    [int]$Port = 9222,
    [string]$Url = "http://localhost:5173",
    [string]$ProfileDir = "$env:USERPROFILE\.gemini\chrome-profiles\flama-devtools"
)

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "🚀 Flama Chrome DevTools Launcher (Isolated Profile)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Resolve Chrome executable
$chromeCandidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)

$chromePath = $null
foreach ($candidate in $chromeCandidates) {
    if (Test-Path $candidate) {
        $chromePath = $candidate
        break
    }
}

if (-not $chromePath) {
    Write-Error "❌ Google Chrome executable not found in standard paths. Please install Google Chrome or update the script path."
    exit 1
}

# 2. Ensure isolated profile directory exists
if (-not (Test-Path $ProfileDir)) {
    Write-Host "📁 Creating isolated profile directory: $ProfileDir" -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $ProfileDir | Out-Null
}

Write-Host " Chrome Executable : $chromePath" -ForegroundColor Green
Write-Host " Isolated Profile  : $ProfileDir" -ForegroundColor Green
Write-Host " Debug Port        : $Port" -ForegroundColor Green
Write-Host " Target URL        : $Url" -ForegroundColor Green
Write-Host "------------------------------------------------------------"

# 3. Launch Chrome with isolated user data directory and remote debugging
$arguments = @(
    "--remote-debugging-port=$Port",
    "--user-data-dir=`"$ProfileDir`"",
    "--no-first-run",
    "--no-default-browser-check",
    "`"$Url`""
)

Start-Process -FilePath $chromePath -ArgumentList $arguments

Write-Host "✅ Chrome launched successfully with isolated profile!" -ForegroundColor Green
Write-Host "💡 Chrome DevTools MCP and profiling tools can now attach to port $Port." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
