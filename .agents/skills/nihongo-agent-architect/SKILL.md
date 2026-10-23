---
name: nihongo-agent-architect
description: Create, update, and refine repo-local agent guidance for the Nihongo Flask codebase. Use when the task involves `AGENTS.md`, repo-local `SKILL.md` files, `agents/openai.yaml`, repository-specific invocation prompts, or subagent workflows that should teach future agents how to work safely with this repository's startup side effects, clone overlay model, route/service/repository boundaries, and React SPA frontend.
---

# Nihongo Agent Architect

## Mission

Create or maintain agent files that match the real repository. Inspect first, then encode only the repo facts that help future agents make smaller, safer changes.

## Inspect Before Editing

Read only what the task needs, but start with these files:

- `AGENTS.md`
- `README.md`
- `README_SETUP.md`
- `app/__init__.py`
- `app/api/__init__.py`
- `wsgi.py`
- `docs/README.md`, `docs/backend/ARCHITECTURE.md`, `docs/frontend/ARCHITECTURE.md`

Then load task-specific context:

- Flashcards, clone overlay, share, study: `docs/runbooks/FLASHCARD_V2_RUNBOOK.md`, `docs/backend/old/completed-plans/CLONE_CUTOVER_REPORT.md`, `app/api/v1/flashcards/`, `app/services/flashcards_share_service.py`
- Vocabulary browse and study: `app/api/v1/learning/browse.py`, `app/api/v1/learning/study.py`, `app/repositories/vocabulary_repository.py`, `app/repositories/study_repository.py`, `app/services/anki_scheduler.py`
- Admin, TTS, stats, dashboard: `app/api/v1/admin/`, `app/api/v1/analytics/`, related service and test files
- UI and component work: `docs/frontend/ARCHITECTURE.md`, `frontend/src/`

## Workflow

1. Map the real repo shape.
   Record entry points, startup side effects, major domains, naming patterns, and risky large files.
2. Decide which agent files actually need changes.
   Use `AGENTS.md` for repo-wide rules. Use `skills/<skill-name>/SKILL.md` only for a recurring specialized workflow. Keep `agents/openai.yaml` aligned with the skill body.
3. Encode practical instructions, not theory.
   Point future agents to exact files to inspect first for common tasks. Call out preserved boundaries and known traps.
4. Keep edits narrow.
   Avoid touching application code unless agent guidance would otherwise become false.
5. Validate before finishing.
   Check that the skill metadata still matches the skill body, that the repo-specific guidance is concise, and that any docs you relied on still match the code.

## Repo Facts That Must Stay Accurate

- The app boots through `wsgi.py -> create_app()`.
- `create_app()` loads env configuration through `app/settings.py`. Production startup is passive by default; maintenance, schema helpers, seeds and cutover run through `app/startup.py` only when enabled.
- Config is env-driven in `app/settings.py`, loaded by `app/__init__.py`; there is no config-class layer.
- The route, service, and repository split is useful but imperfect. Some services import route helpers, and some repositories perform presenter-like shaping.
- Overlay implementation lives in `app/services/share/`, with `flashcards_share_service.py` as a facade. Preserve retired HTTP 410 wrappers in `app/routes/vocabulary.py`; verify current file size before calling a file a monolith.
- Shared deck installs are overlay-only. Clone edit flows must not mutate source notes or reintroduce legacy full-copy behavior.
- Legacy Level/Topic/Lesson vocabulary routes intentionally return `410`.
- The frontend is the React SPA (`frontend/src/`); user-facing Jinja templates have been removed.

## What Good Guidance Looks Like Here

- Name the file paths future agents should inspect first for auth, stats, vocabulary, flashcards, share, TTS, admin, UI, and CLI work.
- Preserve the current route -> service -> repository split instead of inventing a new architecture.
- Warn about startup side effects, clone overlay semantics, timezone-sensitive scheduling, and media sanitization rules.
- Point to the focused tests that already exist for the area being changed.

## What To Avoid

- Do not write generic Flask tutorials or abstract prompt-engineering advice.
- Do not recommend broad refactors just because the repo has large files.
- Do not describe architecture that is only planned in docs and not present in code.
- Do not create extra documentation files that future agents will not need.

## Validation

- If you update or create a repo skill, keep `agents/openai.yaml` synchronized with the skill body.
- Ensure `interface.default_prompt` explicitly names the skill as `$skill-name`.
- Prefer a quick validation pass with the skill validator when available.
- For substantial skill changes, forward-test with a fresh subagent using only the skill and repo context needed for the task.

## Shared skill governance

`skills/` is canonical; edit it rather than generated `.claude/skills/` or `.agents/skills/`. Run `python scripts/sync_claude_skills.py` and its `--check` mode after changes, then the `agent_skills` test module. Preserve vendor licenses, notices and relative dependencies when exporting. Separate observed source/Git/mirror/runtime/tool availability. Missing platform-specific capabilities belong in the export queue, not fabricated portable skills. Only an actual reviewer may record its own sign-off. See `docs/architecture/MULTI_AGENT_SKILLS_AUDIT_AND_UNIFICATION.md` for the dated audit and handoffs.
