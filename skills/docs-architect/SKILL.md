---
name: docs-architect
description: Design, update, restructure, and maintain repository documentation for the Nihongo Flask codebase. Use when the task is to inspect or revise README files, setup/install docs, architecture notes, runbooks, troubleshooting guides, AGENTS-facing documentation, or other engineering docs so they match the real code, startup flow, scripts, Docker setup, config, and repository structure.
---

# Docs Architect

## Mission

Keep documentation aligned with the repository as it exists now. Inspect code and scripts first, then make the smallest documentation change that removes confusion for engineers.

## Inspect Before Editing

Start with the runtime and documentation entry points:

- `README.md`
- `README_SETUP.md`
- `wsgi.py`
- `app/__init__.py`
- `app/routes/__init__.py`
- `app/cli.py`
- `Dockerfile`
- `docker-compose.yml`
- `.env_example`
- `docs/SYSTEM_ARCHITECTURE.md`

Then load task-specific context:

- Flashcards, sharing, overlay installs: `docs/FLASHCARD_V2_RUNBOOK.md`, `docs/CLONE_CUTOVER_REPORT.md`, `app/routes/flashcards/`, `app/services/flashcards_share_service.py`
- Vocabulary browse and study: `app/routes/vocabulary.py`, `app/repositories/vocabulary_repository.py`, `app/repositories/study_repository.py`, `app/services/anki_scheduler.py`
- Frontend and components: `frontend/docs/COMPONENT_ARCHITECTURE.md`, `templates/base.html`, `templates/components/`, `static/js/`, `static/css/components/`
- Admin, TTS, stats, dashboard: `app/routes/main.py`, `app/routes/admin.py`, related service and test files
- Setup, seeding, and operational workflows: `scripts/setup_github_workspace.sh`, `scripts/setup_new_device.sh`, `scripts/reseed_db.sh`, `scripts/reseed_db.ps1`, `scripts/reseed_db.bat`, `.github/workflows/`

## Workflow

1. Map the real behavior first: entry points, startup commands, env vars, scripts, and existing docs.
2. Compare docs against code. When docs and implementation disagree, treat the codebase as the source of truth.
3. Separate docs by purpose:
   - root `README*.md` for overview and setup
   - `docs/*ARCHITECTURE*.md` for structure and boundaries
   - runbooks and migration notes for operational flows
   - troubleshooting only when tied to real failure modes in this repo
4. Update the smallest useful set of files. Tighten existing docs before creating new ones.
5. Finish with remaining documentation gaps instead of padding the current task.

## Repo Facts That Must Stay Accurate

- The app boots through `wsgi.py -> create_app()`.
- `create_app()` loads env config directly in `app/__init__.py`; there is no `config.py` or config-class layer.
- Startup is side-effect heavy: `db.create_all()`, schema compatibility patches, role and TTS seeding, and clone cutover run during app startup.
- The Docker image runs `gunicorn --bind 0.0.0.0:4789 wsgi:app`, while local development commonly uses `flask --app wsgi.py run --host=0.0.0.0 --port=4789`.
- Persistence models live in top-level `models/`, not under `app/`.
- The frontend is Jinja templates plus vanilla JS and CSS components.
- Shared deck installs are overlay-only. Do not document legacy full-copy clone behavior as current behavior.
- Legacy Level/Topic/Lesson routes in `app/routes/vocabulary.py` intentionally return `410`.
- Scheduling and due counts depend on timezone-aware helpers in `app/services/anki_scheduler.py` and `app/repositories/study_repository.py`.
- Media handling must preserve renderer sanitization and `/media/proxy/<asset_id>` access rules.

## Documentation Focus Areas

- Overview and repo shape: `README.md`
- Local setup and commands: `README_SETUP.md`, `.env_example`, `scripts/`
- Architecture and boundaries: `docs/SYSTEM_ARCHITECTURE.md`, `frontend/docs/COMPONENT_ARCHITECTURE.md`
- Flashcard, share, and cutover behavior: `docs/FLASHCARD_V2_RUNBOOK.md`, `docs/CLONE_CUTOVER_REPORT.md`
- Migrations and schema repair: `migrations/`, `app/__init__.py`, `docs/LEGACY_SCHEMA_MIGRATION_PLAN.md`
- Scheduler and study behavior: `docs/SCHEDULER_FIX_DOCUMENTATION.md`, related services and repositories
- CI and deployment hints: `.github/workflows/`, `Dockerfile`, `docker-compose.yml`

## Writing Rules

- Prefer short sections, concrete commands, and exact file paths.
- Document what the repo does today, not what it might do after a refactor.
- Remove or rewrite stale commands, paths, and architecture claims instead of preserving them.
- Avoid generic Flask tutorials, marketing language, or framework theory.
- Do not change application code unless the user explicitly asks.

## Deliverables

For each docs task, report:

- files inspected
- docs created or updated
- stale or missing content found
- what changed
- why the change improves accuracy or usability
- remaining gaps worth documenting later

## Validation

- Re-read every command, path, env var, and entry point against the repository before finishing.
- If setup or operational docs changed, confirm the referenced script or command exists for the platform being documented.
- Keep the skill concise and repository-aware.
