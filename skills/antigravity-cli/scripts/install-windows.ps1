[CmdletBinding()]
param(
    [switch]$EnableFullAccessByDefault,
    [string]$AgyExecutable = (Join-Path $env:LOCALAPPDATA 'agy\bin\agy.exe')
)

$ErrorActionPreference = 'Stop'

$resolvedAgy = (Resolve-Path -LiteralPath $AgyExecutable).Path
$skillRoot = Split-Path -Parent $PSScriptRoot
$personalSkillRoot = Join-Path $env:USERPROFILE '.gemini\antigravity\skills\antigravity-cli'
$shimRoot = Join-Path $env:LOCALAPPDATA 'agy\full-access-bin'

New-Item -ItemType Directory -Force -Path $personalSkillRoot | Out-Null
Copy-Item -LiteralPath (Join-Path $skillRoot 'SKILL.md') -Destination (Join-Path $personalSkillRoot 'SKILL.md') -Force
$sourceReferences = Join-Path $skillRoot 'references'
if (Test-Path -LiteralPath $sourceReferences) {
    $personalReferences = Join-Path $personalSkillRoot 'references'
    New-Item -ItemType Directory -Force -Path $personalReferences | Out-Null
    Copy-Item -Path (Join-Path $sourceReferences '*') -Destination $personalReferences -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $shimRoot | Out-Null
$escapedAgy = $resolvedAgy.Replace('%', '%%')

$safeShim = @(
    '@echo off'
    ('"{0}" %*' -f $escapedAgy)
    'exit /b %ERRORLEVEL%'
) -join "`r`n"
[System.IO.File]::WriteAllText((Join-Path $shimRoot 'agy-safe.cmd'), $safeShim + "`r`n", [System.Text.UTF8Encoding]::new($false))

if ($EnableFullAccessByDefault) {
    $fullShim = @(
        '@echo off'
        ('"{0}" --dangerously-skip-permissions %*' -f $escapedAgy)
        'exit /b %ERRORLEVEL%'
    ) -join "`r`n"
    [System.IO.File]::WriteAllText((Join-Path $shimRoot 'agy.cmd'), $fullShim + "`r`n", [System.Text.UTF8Encoding]::new($false))

    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $entries = @($userPath -split ';' | Where-Object {
        -not [string]::IsNullOrWhiteSpace($_) -and $_.TrimEnd('\') -ine $shimRoot.TrimEnd('\')
    })
    [Environment]::SetEnvironmentVariable('Path', (($shimRoot) + ';' + ($entries -join ';')), 'User')
}

[pscustomobject]@{
    AgyExecutable = $resolvedAgy
    SkillInstalledTo = $personalSkillRoot
    SafeCommand = (Join-Path $shimRoot 'agy-safe.cmd')
    FullAccessDefault = [bool]$EnableFullAccessByDefault
    RestartRequired = $true
}
