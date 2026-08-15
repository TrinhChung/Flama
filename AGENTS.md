# AGENTS.md

## Repo Snapshot
- Flask app factory in `app/__init__.py`, served by `wsgi.py`; production container runs Gunicorn against `wsgi:app`, while Docker Compose also sets `FLASK_APP=wsgi.py` on port `4789`.
- Backend stack: Flask, SQLAlchemy, Flask-Migrate, Flask-Login, MySQL in normal runtime. Many tests use SQLite in memory.
- Config is env-driven inside `app/__init__.py`; there is no `config.py` or config-class layer.
- Persistence lives in top-level `models/`, not under `app/`.
- Frontend stack: React SPA in `frontend/src/` (Vite, React Router, TailwindCSS/Lucide/Radix UI). Flask serves the SPA shell via `app/spa.py` and canonical REST resources under `/api`. Server-rendered Jinja templates have been completely eliminated.
- Companion services:
  - `connect_wsgi.py` on port `4790`: Flama Connect service (Yomitan / AnkiConnect protocol bridge for 1-click word mining).
  - `flama-audio/` on port `4791`: Flama Audio desktop companion (.NET 8 WPF) providing local VoiceVox and Kokoro TTS engines.
- Core domains: auth, dashboard/stats, vocabulary browse/study, flashcard note types/import/share/study/media, deck change requests, marketplace, payOS payments, admin management, CLI seeding.

## Inspect First
- Startup and config: `wsgi.py`, `app/__init__.py`, `app/extensions.py`, `app/api/__init__.py`, `docker-compose.yml`, `README_SETUP.md`
- Architecture context: `docs/architecture/SYSTEM_ARCHITECTURE.md`
- Flashcard/share/clone/change-request work: `docs/runbooks/FLASHCARD_V2_RUNBOOK.md`, `docs/plans/completed/CLONE_CUTOVER_REPORT.md`, `docs/plans/completed/DECK_CHANGE_REQUEST_SIMPLE_PLAN.md`
- UI structure: `frontend/docs/COMPONENT_ARCHITECTURE.md`, `frontend/src/`
- Treat docs as guidance, not automatic ground truth. Verify behavior in code before encoding agent instructions.

## Runtime Flow
- `wsgi.py` calls `create_app()`.
- `create_app()` loads env config, resolves media storage, initializes `db`, `migrate`, and `login_manager`, imports models for metadata registration, then registers blueprints and CLI commands.
- `flashcards_bp` and API routes are registered under canonical `/api`.
- Startup inside the app context is not passive. It runs `db.create_all()`, `ensure_user_management_schema()`, `_ensure_backward_compatible_schema()`, `ensure_default_user_roles()`, `ensure_default_tts_providers()`, and `flashcards_share.cutover_clone_model_to_overlay_only(...)`, then commits.
- Before changing startup, confirm whether the change affects app boot, tests, Docker startup, or local schema repair.

## Architecture Boundaries
- Prefer HTTP parsing, schema validation, and response mapping in `app/api/*`.
- Prefer business orchestration and transaction ownership in `app/services/*`.
- Prefer query and persistence code in `app/repositories/*`.
- Keep request sanitization and validation in `app/validators/*`.
- Keep schema changes in `models/*` plus `migrations/` unless the existing startup compatibility patch is the specific target.
- Do not assume the boundaries are perfectly clean today. Preserve behavior before trying to normalize the layer split.

## High-Risk Files
- `app/routes/vocabulary.py`: large route module covering browse, study, deck tree, clone-aware browse editing, and legacy `410` stubs.
- `app/services/flashcards_share_service.py`: overlay/share/install/cutover hotspot with many behaviors and failure paths.
- `app/services/deck_change_request_service.py`: change request lifecycle and conflict resolution engine.
- `app/__init__.py`: startup side effects, schema compatibility patches, and clone cutover.
- Avoid broad rewrites in these files unless the user explicitly asks for architectural refactoring.

## Common Task Maps
- Auth and sessions: `app/api/identity/routes.py`, `models/user.py`, `app/services/identity_api_service.py`
- Dashboard and stats: `app/api/analytics/routes.py`, `app/services/dashboard_service.py`, `app/services/stats_overview.py`, `app/services/stats_today_future.py`
- Vocabulary browse/study/decks: `app/api/decks/routes.py`, `app/api/learning/browse.py`, `app/api/learning/study.py`, `app/repositories/vocabulary_repository.py`, `app/repositories/study_repository.py`, `app/services/anki_scheduler.py`
- Flashcard note types/import/render/study: `app/api/flashcards/`, `app/services/flashcard_renderer.py`, `app/services/flashcard_content_service.py`, `app/services/flashcard_import_api_service.py`, `app/services/study_service.py`
- Shared decks, clone overlay, marketplace: `app/api/marketplace/`, `app/services/flashcards_share_service.py`, `app/repositories/flashcards_share_repository.py`, `docs/plans/completed/CLONE_CUTOVER_REPORT.md`
- Deck Change Requests: `app/services/deck_change_request_service.py`, `app/repositories/deck_change_request_repository.py`, `models/deck_change_request.py`, `docs/plans/completed/DECK_CHANGE_REQUEST_SIMPLE_PLAN.md`
- Flama Connect (Yomitan/AnkiConnect): `connect_wsgi.py`, `app/services/flama_connect_service.py`, `models/connect_*.py`
- Flama Audio Local TTS: `flama-audio/`, `frontend/src/features/audio/`, `flama-audio/README.md`
- Payments (payOS): `app/services/payment_service.py`, `app/services/payment/provider/payos_provider.py`, `docs/architecture/FLAMA_PAYMENT_ARCHITECTURE.md`
- Admin users and roles: `app/api/admin/`, `app/services/admin_service.py`, `app/services/admin_user_api_service.py`, `app/services/user_roles.py`, `models/user_role.py`
- Seeding and CLI: `app/cli.py`, `scripts/reseed_db.*`, `static/seed_data/`

## Repo-Specific Guardrails
- Preserve the overlay-only shared deck model. Do not reintroduce legacy full-copy clone behavior or mutate source notes in clone edit flows.
- Treat `docs/plans/completed/CLONE_CUTOVER_REPORT.md` as required context before changing `DeckInstall`, clone scope resolution, browse edit for cloned cards, or cutover logic.
- Legacy Level/Topic/Lesson routes in `app/routes/vocabulary.py` intentionally return `410`. Do not revive that structure unless the user explicitly wants it back.
- Due counts and study ordering depend on timezone and day-boundary helpers in `app/services/anki_scheduler.py` and `app/repositories/study_repository.py`. Do not hand-roll new scheduling logic in routes.
- Flashcard HTML rendering and media safety flow through `app/services/flashcard_renderer.py` plus CSP and `/media/proxy/<asset_id>` constraints. Preserve sanitization and proxy-based media access.
- For UI work, target the React frontend (`frontend/src/`). Jinja templates have been completely deleted; all user-facing UI is in React.
- Mặc định khi người dùng yêu cầu sửa/nâng cấp giao diện (UI/UX), làm việc và điều chỉnh trên React frontend (`frontend/src/`).

## Testing
- Prefer the narrowest relevant test module first; most feature areas already have focused tests in `tests/`.
- The suite is flat `unittest` with per-file app/database setup and no shared fixture layer. Copy the closest existing test file instead of inventing a new harness.
- If you touch startup, config, media paths, or DB compatibility logic, verify against the real entry point (`wsgi.py` or Docker) instead of relying only on unit tests.
- If you touch clone overlay flows, validate both direct source ownership cases and installed-clone cases.
- SQLite tests are useful, but MySQL-specific schema behavior still matters for startup and migrations.

## Agent Files
- Use `$docs-architect` when the task is to create or update repository documentation such as `README.md`, `README_SETUP.md`, `docs/*.md`, troubleshooting notes, or operational runbooks.
- Use `$nihongo-agent-architect` when the task is to create or update repo-local agent guidance such as `AGENTS.md`, skill folders under `skills/`, or `agents/openai.yaml`.
- Use `$impeccable` when designing, reviewing, auditing, critiquing, styling, or polishing frontend UI/UX in `frontend/src/`.
- Use `$stitch-skills` (bao gồm `$generate-design`, `$react-components`, `$shadcn-ui`, `$manage-design-system`, `$extract-design-md`, `$code-to-design`) khi cần tương tác với Google Stitch MCP để sinh màn hình, quản lý design system, trích xuất HTML sang Stitch, hoặc tạo React component từ thiết kế Stitch.
- Keep agent guidance short, repo-specific, and workflow-oriented. Avoid generic Flask or prompt-engineering tutorials.
