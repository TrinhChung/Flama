[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$FilePath,

    [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Find-SignTool {
    $command = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }

    $windowsKitsBin = Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\bin"
    $candidates = @(
        Get-ChildItem -Path $windowsKitsBin -Filter signtool.exe -File -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.DirectoryName -match '[\\/]x64$' } |
            Sort-Object { [version]$_.Directory.Parent.Name } -Descending
    )
    if ($candidates.Count -eq 0) {
        throw "SignTool was not found in PATH or the Windows SDK."
    }

    return $candidates[0].FullName
}

function Test-CodeSigningEku {
    param([System.Security.Cryptography.X509Certificates.X509Certificate2]$Certificate)

    $codeSigningOid = "1.3.6.1.5.5.7.3.3"
    foreach ($extension in $Certificate.Extensions) {
        if ($extension -is [System.Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension]) {
            foreach ($usage in $extension.EnhancedKeyUsages) {
                if ($usage.Value -eq $codeSigningOid) {
                    return $true
                }
            }
        }
    }

    return $false
}

$certificateBase64 = $env:WINDOWS_SIGNING_CERTIFICATE_BASE64
$certificatePassword = $env:WINDOWS_SIGNING_CERTIFICATE_PASSWORD
$expectedThumbprint = ($env:WINDOWS_SIGNING_CERTIFICATE_THUMBPRINT -replace '[^0-9A-Fa-f]', '').ToUpperInvariant()

if ([string]::IsNullOrWhiteSpace($certificateBase64)) {
    throw "WINDOWS_SIGNING_CERTIFICATE_BASE64 is required."
}
if ([string]::IsNullOrWhiteSpace($certificatePassword)) {
    throw "WINDOWS_SIGNING_CERTIFICATE_PASSWORD is required."
}
if ([string]::IsNullOrWhiteSpace($expectedThumbprint)) {
    throw "WINDOWS_SIGNING_CERTIFICATE_THUMBPRINT is required."
}
if ([string]::IsNullOrWhiteSpace($TimestampUrl)) {
    throw "An RFC 3161 timestamp URL is required."
}

$resolvedFile = (Resolve-Path -LiteralPath $FilePath).Path
$runnerTemp = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { [IO.Path]::GetTempPath() }
$pfxPath = Join-Path $runnerTemp ("flama-audio-signing-{0}.pfx" -f [guid]::NewGuid().ToString("N"))
$importedCertificates = @()
$certificateBytes = $null
$securePassword = $null

try {
    $certificateBytes = [Convert]::FromBase64String($certificateBase64)
    [IO.File]::WriteAllBytes($pfxPath, $certificateBytes)
    $securePassword = ConvertTo-SecureString -String $certificatePassword -AsPlainText -Force
    $importedCertificates = @(
        Import-PfxCertificate `
            -FilePath $pfxPath `
            -CertStoreLocation Cert:\CurrentUser\My `
            -Password $securePassword `
            -Exportable:$false
    )

    $signingCertificates = @(
        $importedCertificates |
            Where-Object { $_.HasPrivateKey -and (Test-CodeSigningEku -Certificate $_) }
    )
    if ($signingCertificates.Count -ne 1) {
        throw "The PFX must contain exactly one private-key certificate with the Code Signing EKU."
    }

    $signingCertificate = $signingCertificates[0]
    $actualThumbprint = $signingCertificate.Thumbprint.ToUpperInvariant()
    if ($actualThumbprint -ne $expectedThumbprint) {
        throw "Imported certificate thumbprint mismatch. Expected $expectedThumbprint, got $actualThumbprint."
    }

    $now = Get-Date
    if ($now -lt $signingCertificate.NotBefore -or $now -gt $signingCertificate.NotAfter) {
        throw "The configured code-signing certificate is not currently valid."
    }

    Write-Host "Signing FlamaAudio with the pinned publisher certificate."
    Write-Host "Subject: $($signingCertificate.Subject)"
    Write-Host "Issuer: $($signingCertificate.Issuer)"
    Write-Host "Thumbprint: $actualThumbprint"

    $signTool = Find-SignTool
    & $signTool sign `
        /sha1 $actualThumbprint `
        /s My `
        /fd SHA256 `
        /tr $TimestampUrl `
        /td SHA256 `
        /d FlamaAudio `
        /v `
        $resolvedFile
    if ($LASTEXITCODE -ne 0) {
        throw "SignTool signing failed for $resolvedFile (exit code $LASTEXITCODE)."
    }

    & (Join-Path $PSScriptRoot "Test-WindowsRelease.ps1") `
        -FilePath $resolvedFile `
        -ExpectedThumbprint $expectedThumbprint
}
finally {
    foreach ($thumbprint in @($importedCertificates | ForEach-Object { $_.Thumbprint } | Select-Object -Unique)) {
        $certificateStorePath = "Cert:\CurrentUser\My\$thumbprint"
        if (Test-Path -LiteralPath $certificateStorePath) {
            Remove-Item -LiteralPath $certificateStorePath -Force
        }
    }
    if (Test-Path -LiteralPath $pfxPath) {
        Remove-Item -LiteralPath $pfxPath -Force
    }
    if ($null -ne $certificateBytes) {
        [Array]::Clear($certificateBytes, 0, $certificateBytes.Length)
    }
    if ($null -ne $securePassword) {
        $securePassword.Dispose()
    }
    $env:WINDOWS_SIGNING_CERTIFICATE_BASE64 = $null
    $env:WINDOWS_SIGNING_CERTIFICATE_PASSWORD = $null
}

