---
name: flama-local-dev
description: Run, test and verify Flama on the owner's Windows dev machine - venv Python, local MySQL80, test env flags that leak from .env, ignored-path allowlists, Flask/Vite ports, browser verification, and working safely in a checkout other agents edit at the same time. Use before running tests or dev servers, checking a UI change in a browser, committing new migration or skill files, or starting a multi-file refactor in the main checkout.
---

# Flama Local Dev

Machine observations below date from 2026-10-20. Re-check the interpreter, service, ports and shell when using another machine or session; these observations do not authorize schema changes or cleanup of another agent's workspace.

## Interpreter and database

- Bare `python` on PATH is the Microsoft Store stub. Run from the repo root with `.\.venv\Scripts\python.exe` (PowerShell) or `./.venv/Scripts/python.exe` (Bash).
- Local MySQL 8.0 was observed running as the Windows service `MySQL80`. Check with `Get-Service -Name MySQL80` or `sc.exe query MySQL80`; bare `sc` is a PowerShell alias. Use the existing `DB_*` configuration without printing credentials. Never repoint development to SQLite (see `AGENTS.md`).
- The local buffer pool target is 128M on purpose (see `AGENTS.md`). Read `@@innodb_buffer_pool_size`, `@@innodb_buffer_pool_instances`, `@@innodb_buffer_pool_chunk_size`, `my.ini` and `performance_schema.persisted_variables` before measuring. The running size can differ from the configured target until a restart; report both instead of claiming the target is already active. Do not resize, restart `MySQL80` or use `SET PERSIST` merely to speed up tests or improve benchmarks.
- A model-column change needs its matching Alembic migration. When that schema work is authorized, coordinate with the agent owning the shared server, verify the local MySQL target and migration chain, then run `.\.venv\Scripts\python.exe -m flask --app wsgi.py db upgrade` before restarting consumers. Adding an ORM column alone is not a reason to run unrelated pending migrations.
- Before running `scripts/probe_*_mysql.py`, inspect that specific script and its database helper for target selection, mutation and cleanup. Several probes create disposable databases; the filename pattern alone does not prove isolation from the development database.

## Tests

- Use `scripts/run_tests.py` (`--changed`, `--module <name> --backend-only`, `--fe`, `--list-modules`).
- `app/settings.py` calls `load_dotenv()` without override, so `.env` can change study-test behavior unless process values are supplied. For tests intended to exercise code defaults, pass these rollout flags as empty strings for that process only (`coerce_bool_env()` treats empty as the default); never edit `.env`. Tests explicitly targeting a rollout mode should retain their required values:

  ```bash
  env STUDY_WIRE_V4_ENABLED= STUDY_ASYNC_BATCH_ENABLED= STUDY_NEW_LEARNER_NOTE_ENABLED= \
      STUDY_NOTE_COUNT_ENABLED= STUDY_PROGRESS_SHADOW_WRITE_ENABLED= \
      STUDY_PROGRESS_SHADOW_BACKFILL_ENABLED= STUDY_PROGRESS_SHADOW_COMPARE_ENABLED= \
      ./.venv/Scripts/python.exe scripts/run_tests.py --module study --backend-only
  ```

  The example uses Git Bash. In the observed Windows PowerShell 5.1 session, `$env:NAME = ''` removes the variable, allowing `load_dotenv()` to supply it again. Do not assume other PowerShell versions behave identically; verify that the child process receives an empty value.

## Ignored paths that silently drop new files

- `/migrations/*` is ignored except an allowlist. A new helper module beside `versions/` does not show as untracked and would be left out of the commit, which breaks fresh migration chains in CI. Add `!/migrations/<file>.py` to `.gitignore`. Never put helpers inside `versions/`, because Alembic loads every file there as a revision.
- `skills/*` is ignored except reviewed shared skills. A new skill needs `!skills/<name>/` in `.gitignore`, then `python scripts/sync_claude_skills.py` and `--check`.
- After creating files under either path, run `git check-ignore -v <path>`, then `git status --short -- <path>`. Being unignored does not stage or commit a file; inspect the actual staged diff before committing only the paths you own.
- CI ignores `docs/**` and `**.md`, so a change that touches only Markdown (including `SKILL.md`) runs no CI and no mirror drift test. Run `python scripts/sync_claude_skills.py --check` yourself.

## UI verification

- `.claude/launch.json` defines `flask-api` (port 4789), `vite` (5173) and `vite-alt` (5184). The Vite dev server proxies `/api` to `127.0.0.1:4789`. When another session already owns 5173, use `vite-alt` or another `--strictPort` port.
- Sign-in cookies are host-specific. Use the hostname used for the intended test session; `localhost` and `127.0.0.1` do not share host cookies. An isolated browser profile may require its own login regardless of hostname.
- For an isolated fix, choose a worktree baseline that contains the intended code and run Vite on its own port; do not assume `origin/master` includes pending work. Prefer separate dependencies. If reusing dependencies through a junction, record the worktree path, link path and resolved target first. Before cleanup, verify those absolute paths remain within the intended workspace, distinguish removal of the link from deletion of its target, and use one shell with explicit link-removal semantics. Do not recursively delete or move an unresolved junction or its target.
- Disposable local accounts can be staged from a scratch script with `tests.study_note_fixtures.create_note_user` plus `User.set_password`. Keep generated passwords out of chat and the repository.
- All Chrome debugging and automation uses an isolated profile (see `AGENTS.md`).

## Shared checkout with other agents

Codex, Antigravity and Claude sessions may edit this checkout at the same time. Keep an initial diff and explicit file ownership so temporary failures do not cause another contributor's work to be reset or deleted.

- Before a multi-file change, check `git status`, recent mtimes and running agents (`Get-Process codex*, Antigravity*`).
- Write new files first and switch imports or entry points in one batch, so the tree never stays broken between steps. Use a worktree for long refactors.
- If another agent is rewriting a file, do not edit it at the same time. Put your contribution in a new file and integrate it after that agent finishes.
- Stage only the paths you own. Never commit another agent's uncommitted changes as part of your work.
