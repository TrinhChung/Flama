---
name: nihongo-engineer
description: Route work in the Nihongo/Flama checkout to current repository guidance and the appropriate frontend, backend, database or documentation skill.
---

# Nihongo Engineer

This is a compatibility entry point for Flama, not a second architecture manual. Apply it only inside the Nihongo/Flama repository.

1. Read the checkout's `AGENTS.md` and inspect the files relevant to the request. Resolve all paths below from the checkout root.
2. Read only the applicable canonical skill:
   - React SPA: `skills/flama-frontend-architecture/SKILL.md`.
   - Flask API/services/repositories: `skills/flama-backend-architecture/SKILL.md`.
   - Models, schema, migrations: `skills/flama-database-architecture/SKILL.md`; add `skills/mysql/SKILL.md` for MySQL tuning.
   - Documentation: `skills/docs-architect/SKILL.md`.
   - Agent guidance: `skills/nihongo-agent-architect/SKILL.md`.
   - Authorized complex multi-agent coordination: `skills/flama-agent-orchestrator/SKILL.md`.
3. If a skill is missing, search known local skill roots and report the exact missing package and prerequisites. Do not reconstruct an old architecture from memory.

Current entry points are `wsgi.py -> app.create_app()`, React `frontend/src/`, canonical `app/api/v1/`, configuration in `app/settings.py`, and gated maintenance in `app/startup.py`. Production startup is passive by default. User-facing Jinja pages have been removed. Preserve native JSON arrays, overlay-only installs, renderer/media safety and local-MySQL development rules in `AGENTS.md`.
