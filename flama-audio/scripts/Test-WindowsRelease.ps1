[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$FilePath,

    [string]$ExpectedThumbprint = ""
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

$resolvedFile = (Resolve-Path -LiteralPath $FilePath).Path
$signTool = Find-SignTool

& $signTool verify /pa /all /v /tw $resolvedFile
if ($LASTEXITCODE -ne 0) {
    throw "SignTool verification failed for $resolvedFile (exit code $LASTEXITCODE)."
}

$signature = Get-AuthenticodeSignature -LiteralPath $resolvedFile
if ([string]$signature.Status -ne "Valid") {
    throw "Authenticode status for $resolvedFile is '$($signature.Status)', expected 'Valid'."
}
if ($null -eq $signature.SignerCertificate) {
    throw "Authenticode did not return a signer certificate for $resolvedFile."
}
if ($null -eq $signature.TimeStamperCertificate) {
    throw "The Authenticode signature on $resolvedFile does not contain a trusted timestamp."
}

$actualThumbprint = $signature.SignerCertificate.Thumbprint.ToUpperInvariant()
$normalizedExpectedThumbprint = ($ExpectedThumbprint -replace '[^0-9A-Fa-f]', '').ToUpperInvariant()
if (
    $normalizedExpectedThumbprint -and
    $actualThumbprint -ne $normalizedExpectedThumbprint
) {
    throw "Signer thumbprint mismatch. Expected $normalizedExpectedThumbprint, got $actualThumbprint."
}

Write-Host "Authenticode verification succeeded."
Write-Host "Subject: $($signature.SignerCertificate.Subject)"
Write-Host "Issuer: $($signature.SignerCertificate.Issuer)"
Write-Host "Thumbprint: $actualThumbprint"
Write-Host "Timestamp subject: $($signature.TimeStamperCertificate.Subject)"

