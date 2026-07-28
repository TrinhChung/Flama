# AGENTS.md

## Repo Snapshot
- Flask app factory in `app/__init__.py`, served by `wsgi.py`; production container runs Gunicorn against `wsgi:app`, while Docker Compose also sets `FLASK_APP=wsgi.py` on port `4789`.
- Backend stack: Flask, SQLAlchemy, Flask-Migrate, Flask-Login, MySQL in normal runtime. Many tests use SQLite in memory.
- Config is env-driven inside `app/__init__.py`; there is no `config.py` or config-class layer.
- Persistence lives in top-level `models/`, not under `app/`.
- Frontend stack: server-rendered Jinja templates, reusable partials under `templates/components/`, vanilla JS under `static/js/`, CSS modules under `static/css/components/`.
- Core domains: auth, dashboard/stats, vocabulary browse/study, flashcard note types/import/share/study/media, admin user/TTS/donation management, CLI seeding.

## Inspect First
- Startup and config: `wsgi.py`, `app/__init__.py`, `app/extensions.py`, `app/routes/__init__.py`, `docker-compose.yml`, `README_SETUP.md`
- Architecture context: `docs/SYSTEM_ARCHITECTURE.md`
- Flashcard/share/clone work: `docs/FLASHCARD_V2_RUNBOOK.md`, `docs/CLONE_CUTOVER_REPORT.md`
- UI structure: `frontend/docs/COMPONENT_ARCHITECTURE.md`, `templates/base.html`
- Treat docs as guidance, not automatic ground truth. `README.md`, `frontend/docs/COMPONENT_ARCHITECTURE.md`, and parts of `docs/FLASHCARD_V2_RUNBOOK.md` lag the current codebase, so verify behavior in code before encoding agent instructions.

## Runtime Flow
- `wsgi.py` calls `create_app()`.
- `create_app()` loads env config, resolves media storage, initializes `db`, `migrate`, and `login_manager`, imports models for metadata registration, then registers blueprints and CLI commands.
- `flashcards_bp` is assembled partly by submodule side-effect imports under `app/routes/flashcards/`; trace those imports before moving helpers or renaming endpoints.
- Startup inside the app context is not passive. It runs `db.create_all()`, `ensure_user_management_schema()`, `_ensure_backward_compatible_schema()`, `ensure_default_user_roles()`, `ensure_default_tts_providers()`, and `flashcards_share.cutover_clone_model_to_overlay_only(...)`, then commits.
- Before changing startup, confirm whether the change affects app boot, tests, Docker startup, or local schema repair.

## Architecture Boundaries
- Prefer HTTP parsing and response mapping in `app/routes/*`.
- Prefer business orchestration and transaction ownership in `app/services/*`.
- Prefer query and persistence code in `app/repositories/*`.
- Keep request sanitization and validation in `app/validators/*`.
- Keep schema changes in `models/*` plus `migrations/` unless the existing startup compatibility patch is the specific target.
- Do not assume the boundaries are perfectly clean today. Some services import route helpers, some routes still query models directly, and `vocabulary_repository` also performs presenter-style shaping. Preserve behavior before trying to normalize the layer split.

## High-Risk Files
- `app/routes/vocabulary.py`: large route module covering browse, study, deck tree, clone-aware browse editing, and legacy `410` stubs.
- `app/routes/flashcards/__init__.py`: large facade module that re-exports many helper functions used by submodules.
- `app/services/flashcards_share_service.py`: overlay/share/install/cutover hotspot with many behaviors and failure paths.
- `app/__init__.py`: startup side effects, schema compatibility patches, and clone cutover.
- Avoid broad rewrites in these files unless the user explicitly asks for architectural refactoring.

## Common Task Maps
- Auth and sessions: `app/routes/auth.py`, `models/user.py`, `app/services/auth_service.py`
- Dashboard and stats: `app/routes/main.py`, `app/services/dashboard_service.py`, `app/services/stats_overview.py`, `app/services/stats_today_future.py`, `tests/test_stats_overview.py`, `tests/test_stats_today_future.py`
- Vocabulary browse/study/decks: `app/routes/vocabulary.py`, `app/repositories/vocabulary_repository.py`, `app/repositories/study_repository.py`, `app/services/anki_scheduler.py`, `tests/test_deck_settings_routes.py`, `tests/test_counter_logic.py`, `tests/test_study_integration.py`
- Flashcard note types/import/render/study: `app/routes/flashcards/`, `app/services/flashcard_renderer.py`, `app/services/flashcard_import_service.py`, `app/services/study_service.py`, `tests/test_flashcard_api_integration.py`, `tests/test_flashcard_renderer.py`, `tests/test_flashcard_validation_security.py`
- Shared decks, clone overlay, marketplace: `app/routes/flashcards/share.py`, `app/services/flashcards_share_service.py`, `app/repositories/flashcards_share_repository.py`, `docs/CLONE_CUTOVER_REPORT.md`
- TTS provider config and user profiles: `app/routes/main.py`, `app/routes/admin.py`, `app/services/tts_provider_service.py`, `models/tts_provider_config.py`, `models/tts_user_provider_profile.py`, `tests/test_tts_provider_seed.py`, `tests/test_tts_user_profile_api.py`
- Admin users and roles: `app/routes/admin.py`, `app/services/admin_service.py`, `app/services/user_roles.py`, `models/user_role.py`, `tests/test_admin_user_roles.py`
- Seeding and CLI: `app/cli.py`, `scripts/reseed_db.*`, `static/seed_data/`, `tests/test_vocab_seed_sharing.py`

## Repo-Specific Guardrails
- Preserve the overlay-only shared deck model. Do not reintroduce legacy full-copy clone behavior or mutate source notes in clone edit flows.
- Treat `docs/CLONE_CUTOVER_REPORT.md` as required context before changing `DeckInstall`, clone scope resolution, browse edit for cloned cards, or cutover logic.
- Legacy Level/Topic/Lesson routes in `app/routes/vocabulary.py` intentionally return `410`. Do not revive that structure unless the user explicitly wants it back.
- Due counts and study ordering depend on timezone and day-boundary helpers in `app/services/anki_scheduler.py` and `app/repositories/study_repository.py`. Do not hand-roll new scheduling logic in routes.
- Flashcard HTML rendering and media safety flow through `app/services/flashcard_renderer.py` plus CSP and `/media/proxy/<asset_id>` constraints. Preserve sanitization and proxy-based media access.
- For UI work, target the React frontend (`frontend/src/`) by default unless the user explicitly requests changes to legacy Jinja templates (`templates/`).
- Mặc định khi người dùng yêu cầu sửa/nâng cấp giao diện (UI/UX), ưu tiên làm việc và điều chỉnh trên React frontend (`frontend/src/`), chỉ can thiệp vào Jinja templates cũ nếu người dùng yêu cầu đích danh.
- Large route and service modules already have refactor notes in `docs/FLAMA_*`. Unless the user requests refactoring, land the smallest behavior-preserving change.

## Testing
- Prefer the narrowest relevant test module first; most feature areas already have focused tests in `tests/`.
- The suite is flat `unittest` with per-file app/database setup and no shared fixture layer. Copy the closest existing test file instead of inventing a new harness.
- If you touch startup, config, media paths, or DB compatibility logic, verify against the real entry point (`wsgi.py` or Docker) instead of relying only on unit tests.
- If you touch clone overlay flows, validate both direct source ownership cases and installed-clone cases.
- SQLite tests are useful, but MySQL-specific schema behavior still matters for startup and migrations.

## Agent Files
- Use `$docs-architect` when the task is to create or update repository documentation such as `README.md`, `README_SETUP.md`, `docs/*.md`, troubleshooting notes, or operational runbooks.
- Use `$nihongo-agent-architect` when the task is to create or update repo-local agent guidance such as `AGENTS.md`, skill folders under `skills/`, or `agents/openai.yaml`.
- Keep agent guidance short, repo-specific, and workflow-oriented. Avoid generic Flask or prompt-engineering tutorials.
