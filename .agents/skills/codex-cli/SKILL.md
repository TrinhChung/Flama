---
name: codex-cli
description: Discover and run the local OpenAI Codex CLI for authorized coding tasks or read-only reviews, with scoped file ownership and verified installed CLI options.
---

# Codex CLI

Resolve `codex` with `Get-Command codex` (PowerShell) or `command -v codex` (POSIX), then inspect `codex --version` and `codex exec --help`. Do not hardcode a user's install directory, model name, or unsupported diagnostic command. Use official OpenAI documentation if installed help is insufficient.

For a read-only review in PowerShell:

```powershell
codex exec --sandbox read-only --ephemeral -C . 'Review the named files; do not edit, delegate, or access external services. Return findings with file and line evidence.'
```

For a multiline prompt, read an exact UTF-8 prompt file and pipe it to `codex exec ... -`. Use `-o <report-path>` when a report artifact is needed. Keep prompts out of shell-built `echo`/`cmd /c` expressions. An explicit prompt argument is non-interactive; a pipe is not mandatory. Check process completion and exit status; report authentication or model failures without claiming a review completed.

For implementation workers, define owned files, interfaces, tests and integration responsibility first. Select the least permissions that satisfy the authorized task; ordinary unattended work does not imply bypassing approvals and sandboxing. Retain the configured model unless explicitly directed otherwise. Review every resulting diff before integration and protect unrelated working-tree changes.

Never print credentials or private configuration. Do not change user-global settings or accounts to bypass a worker failure. Repository skills belong in canonical `skills/` and the generated `.agents/skills/` discovery mirror, not bulk copies into a user's global skill directory.
