---
name: antigravity-cli
description: Install, verify, configure, and operate the local Antigravity `agy` CLI on Windows, including model/login checks, project-scoped launches, PATH repair, and explicit safe or full-access execution. Use for `agy` CLI tasks; do not use for Antigravity Manager account API operations.
---

# Antigravity CLI

Operate the local `agy` CLI without exposing credentials or confusing it with the Antigravity Manager HTTP API.

## Discovery

Prefer `Get-Command agy`. If it is unavailable, check:

```powershell
$agyExe = Join-Path $env:LOCALAPPDATA 'agy\bin\agy.exe'
Test-Path -LiteralPath $agyExe
```

Do not infer that the CLI is logged out merely because the current terminal has stale `PATH` state.

## Verify installation and login

Run from the project directory the user requested:

```powershell
agy models
agy --print 'Reply with exactly: AGY_LOGIN_OK' `
    --model gemini-3.7-flash-low `
    --output-format text `
    --print-timeout 60s
```

The current CLI has no dedicated `auth status` command. A successful authenticated model listing plus a successful minimal response is the observable login check. Do not print tokens, cookies, environment dumps, or credential files.

## Permission modes

- `agy-safe`: invokes the original CLI and keeps normal permission prompts.
- `agy`: on machines restored with the full-access option, invokes the CLI with `--dangerously-skip-permissions`.

Full access permits unattended commands and destructive filesystem or external operations. Enable it only when the user explicitly requests persistent auto-approval. Full access does not broaden the scope of the user's task.

## Restore this machine setup

Run the checked-in installer from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\skills\antigravity-cli\scripts\install-windows.ps1 -EnableFullAccessByDefault
```

Omit `-EnableFullAccessByDefault` to install only the repo skill and keep the original CLI behavior.

The script verifies `agy.exe`, installs this skill into the Antigravity personal skill directory, creates `agy-safe.cmd`, optionally creates an `agy.cmd` full-access shim, and updates User `PATH` without deleting or duplicating existing entries.

Restart terminal/Antigravity after PATH changes.

## Operating rules

- Use `--project`, `--conversation`, or `--continue` only when the user's intended context is known.
- Do not use `--dangerously-skip-permissions` implicitly unless the machine's explicit full-access setup or the user requests it.
- Prefer a minimal model/login probe before diagnosing account failure.
- Do not change Antigravity Manager accounts through this skill; use `$antigravity-manager-api`.

## Worker mode

The user has authorized `agy` to act as an implementation worker for assigned repository tasks. This authorizes delegation and unattended CLI execution within the user's active task; it does not authorize unrelated work, deployment, production mutation, credential access, commits, pushes, or destructive cleanup unless those actions are separately in scope.

Before delegating substantial work, read [references/worker-orchestration.md](references/worker-orchestration.md). It defines task packaging, worktree coordination, result review, quota checks, and safe account rotation through `$antigravity-manager-api`.
