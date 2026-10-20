---
name: antigravity-manager-api
description: "Manage the local Antigravity Manager through its HTTP Admin API: health checks, current account, account listing, quota refresh, and explicit account switching. Use for Antigravity Manager account operations; do not use for ordinary `agy` CLI execution."
---

# Antigravity Manager API

Use the local Antigravity Manager HTTP Admin API. Never store or copy its API key into this skill, source code, logs, screenshots, commits, or responses.

## Configuration

Read configuration from:

- `ANTIGRAVITY_MANAGER_API_KEY`: required for authenticated endpoints.
- `ANTIGRAVITY_MANAGER_BASE_URL`: optional; defaults to `http://127.0.0.1:8045/api`.

If the key is missing, stop and direct the user to the checked-in installer. Avoid asking the user to paste a key into chat.

PowerShell setup:

```powershell
$apiKey = [Environment]::GetEnvironmentVariable('ANTIGRAVITY_MANAGER_API_KEY', 'Process')
if (-not $apiKey) {
    $apiKey = [Environment]::GetEnvironmentVariable('ANTIGRAVITY_MANAGER_API_KEY', 'User')
}
if (-not $apiKey) {
    throw 'Missing ANTIGRAVITY_MANAGER_API_KEY.'
}

$baseUrl = [Environment]::GetEnvironmentVariable('ANTIGRAVITY_MANAGER_BASE_URL', 'Process')
if (-not $baseUrl) {
    $baseUrl = [Environment]::GetEnvironmentVariable('ANTIGRAVITY_MANAGER_BASE_URL', 'User')
}
if (-not $baseUrl) {
    $baseUrl = 'http://127.0.0.1:8045/api'
}
$baseUrl = $baseUrl.TrimEnd('/')
$headers = @{ Authorization = "Bearer $apiKey" }
```

Do not print `$apiKey`, `$headers`, the full environment, or command lines containing credentials.

## Restore local configuration

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\skills\antigravity-manager-api\scripts\install-windows.ps1
```

The installer copies the repo skill into the Antigravity personal skill directory and securely prompts for a key when none exists in Process/User environment. The key is stored only in the Windows User environment, never in the repository.

Restart Antigravity after changing User environment variables.

## Read operations

Health check:

```powershell
Invoke-RestMethod -Method Get -Uri "$baseUrl/health"
```

List accounts:

```powershell
$response = Invoke-RestMethod -Method Get -Uri "$baseUrl/accounts" -Headers $headers
$response.accounts | Select-Object id, email, is_current, disabled
```

Current account:

```powershell
Invoke-RestMethod -Method Get -Uri "$baseUrl/accounts/current" -Headers $headers
```

## State-changing operations

Only refresh quotas when requested:

```powershell
Invoke-RestMethod -Method Post -Uri "$baseUrl/accounts/refresh" -Headers $headers
```

Only switch after the user identifies one unambiguous account. Resolve an email to exactly one account from `GET /accounts`, then send the account's ID. The current server requires `accountId`; email-only switch examples from older Manager versions are not compatible.

Classic Antigravity:

```powershell
$body = @{ accountId = $targetAccountId } | ConvertTo-Json -Compress
Invoke-RestMethod -Method Post -Uri "$baseUrl/accounts/switch" -Headers $headers -ContentType 'application/json' -Body $body
```

Antigravity IDE:

```powershell
$body = @{ accountId = $targetAccountId; target_ide = 'ide' } | ConvertTo-Json -Compress
Invoke-RestMethod -Method Post -Uri "$baseUrl/accounts/switch" -Headers $headers -ContentType 'application/json' -Body $body
```

Antigravity CLI (`agy`):

```powershell
$body = @{ accountId = $targetAccountId; target_ide = 'agy' } | ConvertTo-Json -Compress
Invoke-RestMethod -Method Post -Uri "$baseUrl/accounts/switch" -Headers $headers -ContentType 'application/json' -Body $body
```

After a Classic switch, call `GET /accounts/current` and verify the target. After an IDE or `agy` switch, verify the successful POST and test the target client because the generic current-account endpoint may represent only the Classic target. If a POST response is ambiguous, inspect target state before retrying.

## Safety and failures

- Prefer loopback. Do not send the key to a non-loopback host without explicit confirmation.
- Treat `401`/`403` as missing or invalid credentials without displaying the value.
- Treat `404` as a base URL or API-version mismatch.
- Stop on duplicate emails or ambiguous targets and request an account ID.
- Do not switch to a disabled account unless the API supports it and the user explicitly requests it.
- If a key has been exposed, rotate it and rerun the installer.

## `agy` worker quota rotation

`$antigravity-cli` may use this skill to rotate only the `agy` target when the applicable quota group's five-hour or weekly `remaining_fraction` is at or below `0.10`, or after an explicit quota-exhaustion response.

Before switching, exclude accounts that are disabled, proxy-disabled, validation-blocked, forbidden, or missing relevant quota. Choose the eligible account with the highest minimum remaining fraction across the relevant five-hour and weekly buckets. Never switch while an `agy` job is active, never modify Classic/IDE as part of worker rotation, and retry the interrupted task at most once after verification.

Read `$antigravity-cli`'s `references/worker-orchestration.md` for the complete delegation and rotation workflow.
