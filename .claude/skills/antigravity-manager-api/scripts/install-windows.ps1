[CmdletBinding()]
param(
    [string]$BaseUrl = 'http://127.0.0.1:8045/api'
)

$ErrorActionPreference = 'Stop'

$skillRoot = Split-Path -Parent $PSScriptRoot
$personalSkillRoot = Join-Path $env:USERPROFILE '.gemini\antigravity\skills\antigravity-manager-api'

New-Item -ItemType Directory -Force -Path $personalSkillRoot | Out-Null
Copy-Item -LiteralPath (Join-Path $skillRoot 'SKILL.md') -Destination (Join-Path $personalSkillRoot 'SKILL.md') -Force

$apiKey = [Environment]::GetEnvironmentVariable('ANTIGRAVITY_MANAGER_API_KEY', 'Process')
if (-not $apiKey) {
    $apiKey = [Environment]::GetEnvironmentVariable('ANTIGRAVITY_MANAGER_API_KEY', 'User')
}

if (-not $apiKey) {
    $secureKey = Read-Host 'Antigravity Manager API key' -AsSecureString
    $keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    try {
        $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
    }
}

if ([string]::IsNullOrWhiteSpace($apiKey)) {
    throw 'API key cannot be empty.'
}

[Environment]::SetEnvironmentVariable('ANTIGRAVITY_MANAGER_API_KEY', $apiKey, 'User')
[Environment]::SetEnvironmentVariable('ANTIGRAVITY_MANAGER_BASE_URL', $BaseUrl.TrimEnd('/'), 'User')
$apiKey = $null

[pscustomobject]@{
    SkillInstalledTo = $personalSkillRoot
    BaseUrl = $BaseUrl.TrimEnd('/')
    ApiKeyConfigured = $true
    RestartRequired = $true
}
