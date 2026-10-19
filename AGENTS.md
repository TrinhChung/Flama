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
- Master docs portal & audit report: `docs/README.md`, `docs/DOCUMENTATION_AUDIT_REPORT.md`
- Core architecture hubs: `docs/frontend/ARCHITECTURE.md`, `docs/backend/ARCHITECTURE.md`, `docs/ops/ARCHITECTURE.md`, `docs/logs/ARCHITECTURE.md`
- Startup and config: `wsgi.py`, `app/__init__.py`, `app/extensions.py`, `app/api/__init__.py`, `docker-compose.yml`, `README_SETUP.md`
- Flashcard/share/clone/change-request work: `docs/runbooks/FLASHCARD_V2_RUNBOOK.md`, `docs/backend/old/completed-plans/CLONE_CUTOVER_REPORT.md`, `docs/backend/old/completed-plans/DECK_CHANGE_REQUEST_SIMPLE_PLAN.md`
- UI structure: `docs/frontend/ARCHITECTURE.md`, `frontend/src/`
- Treat docs as guidance, not automatic ground truth. Verify behavior in code before encoding agent instructions.

## Runtime Flow
- `wsgi.py` calls `create_app()`.
- `create_app()` loads env config, resolves media storage, initializes `db`, `migrate`, and `login_manager`, imports models for metadata registration, then registers blueprints and CLI commands.
- `flashcards_bp` and API routes are registered under canonical `/api`.
- Startup inside the app context is passive by default in production (executes a connectivity check `SELECT 1` only); schema migrations and mutations are owned strictly by Alembic. When `STARTUP_RUN_MAINTENANCE=True` (dev/test), it executes `db.create_all()`, `ensure_user_management_schema()`, `ensure_backward_compatible_schema()`, `ensure_default_user_roles()`, `ensure_default_tts_providers()`, and `flashcards_share.cutover_clone_model_to_overlay_only(...)`, then commits.
- Before changing startup, confirm whether the change affects app boot, tests, Docker startup, or local schema repair.

## Architecture Boundaries
- Prefer HTTP parsing, schema validation, and response mapping in `app/api/*`.
- Prefer business orchestration and transaction ownership in `app/services/*`.
- Prefer query and persistence code in `app/repositories/*`.
- Keep request sanitization and validation in `app/validators/*`.
- Keep schema changes in `models/*` plus `migrations/` unless the existing startup compatibility patch is the specific target.
- Do not assume the boundaries are perfectly clean today. Preserve behavior before trying to normalize the layer split.

## High-Risk Files
- `app/routes/vocabulary.py`: pruned legacy route module (117 LOC) retaining browse deck-tree and deck-settings wrappers.
- `app/services/share/` (and compatibility facade `app/services/flashcards_share_service.py`): overlay/share/install/cutover hotspot with many behaviors and failure paths.
- `app/services/deck_change_request_service.py`: change request lifecycle and conflict resolution engine.
- `app/__init__.py`: startup side effects, schema compatibility patches, and clone cutover.
- Avoid broad rewrites in these files unless the user explicitly asks for architectural refactoring.

## Common Task Maps
- Auth and sessions: `app/api/v1/identity/routes.py`, `models/user.py`, `app/services/identity_api_service.py`
- Dashboard and stats: `app/api/v1/analytics/routes.py`, `app/services/dashboard_service.py`, `app/services/stats_overview.py`, `app/services/stats_today_future.py`
- Vocabulary browse/study/decks: `app/api/v1/decks/routes.py`, `app/api/v1/learning/browse.py`, `app/api/v1/learning/study.py` (canonical, delegating to `app/routes/flashcards/study.py`), `app/repositories/vocabulary_repository.py`, `app/repositories/study_repository.py`, `app/services/anki_scheduler.py`
- Flashcard note types/import/render/study: `app/api/v1/flashcards/`, `app/services/flashcard_renderer.py`, `app/services/flashcard_content_service.py`, `app/services/flashcard_import_api_service.py`, `app/services/study_service.py`
- Shared decks, clone overlay, marketplace: `app/api/v1/marketplace/`, `app/services/share/` (via facade `app/services/flashcards_share_service.py`), `app/repositories/flashcards_share_repository.py`, `docs/backend/old/completed-plans/CLONE_CUTOVER_REPORT.md`
- Deck Change Requests: `app/services/deck_change_request_service.py`, `app/repositories/deck_change_request_repository.py`, `models/deck_change_request.py`, `docs/backend/old/completed-plans/DECK_CHANGE_REQUEST_SIMPLE_PLAN.md`
- Flama Connect (Yomitan/AnkiConnect): `connect_wsgi.py`, `app/services/flama_connect_service.py`, `models/connect_*.py`
- Flama Audio Local TTS: `flama-audio/`, `frontend/src/features/audio/`, `flama-audio/README.md`
- Payments (payOS): `app/services/payment_service.py`, `app/services/payment/provider/payos_provider.py`, `docs/backend/old/FLAMA_PAYMENT_ARCHITECTURE.md`
- Admin users and roles: `app/api/v1/admin/`, `app/services/admin_service.py`, `app/services/admin_user_api_service.py`, `app/services/user_roles.py`, `models/user_role.py`
- Seeding and CLI: `app/cli.py`, `scripts/reseed_db.*`, `static/seed_data/`

## Repo-Specific Guardrails
- Preserve the overlay-only shared deck model. Do not reintroduce legacy full-copy clone behavior or mutate source notes in clone edit flows.
- Treat `docs/backend/old/completed-plans/CLONE_CUTOVER_REPORT.md` as required context before changing `DeckInstall`, clone scope resolution, browse edit for cloned cards, or cutover logic.
- Legacy Level/Topic/Lesson routes in `app/routes/vocabulary.py` intentionally return `410`. Do not revive that structure unless the user explicitly wants it back.
- Due counts and study ordering depend on timezone and day-boundary helpers in `app/services/anki_scheduler.py` and `app/repositories/study_repository.py`. Do not hand-roll new scheduling logic in routes.
- Flashcard HTML rendering and media safety flow through `app/services/flashcard_renderer.py` plus CSP and `/media/proxy/<asset_id>` constraints. Preserve sanitization and proxy-based media access.
- For UI work, target the React frontend (`frontend/src/`). Jinja templates have been completely deleted; all user-facing UI is in React.
- Mặc định khi người dùng yêu cầu sửa/nâng cấp giao diện (UI/UX), làm việc và điều chỉnh trên React frontend (`frontend/src/`).
- **Native Array & No Anki Export (Không xuất sang Anki)**:
  - Trường `array` lưu **JSON list** các item text hoặc safe rich-text (cho phép list lồng) trong `notes.field_values`. Giá trị ghi trước 2026-10-11 có thể vẫn là chuỗi mỗi dòng 1 item cho tới khi migrate, nên code đọc phải nhận cả hai.
  - Không `str()` giá trị field (list sẽ thành repr Python): dùng `field_value_text()` khi cần text (hiển thị, tìm kiếm, TTS, worksheet), `stored_field_value()` khi chuẩn hoá mà phải giữ list (cả hai trong `models/field_types.py`; frontend: `fieldValueEditorText()` trong `frontend/src/lib/arrayField.ts`).
  - Flama chỉ import một chiều từ Anki/text, **không** có và không làm chức năng xuất sang Anki; ràng buộc chuỗi phẳng của Anki không áp dụng cho `array`.
  - Renderer (backend lẫn frontend) **không** tự định dạng hay chuyển đổi mảng: list được đưa nguyên vào Mustache, chỉ riêng `{{field}}` trên cả list in ra giống `String(array)` của mustache.js. Template tự xử lý bằng `{{#field}}{{.}}{{/field}}` hoặc `<script>`.
- **Zero Visual Regression**: Khi refactor kiến trúc frontend (tách hook, bẻ nhỏ component, thay thẻ HTML thô bằng UI Primitives), BẮT BUỘC bảo toàn 100% màu sắc, dải gradient thương hiệu, padding, font size, icon, đổ bóng và layout vị trí gốc trừ khi người dùng yêu cầu redesign.
- **Opportunistic FSD Migration on Touch (Quy tắc di cư FSD khi chạm file)**:
  - Do quy mô frontend lớn (`frontend/src/`) không thể tái cấu trúc toàn bộ cùng một lúc: **Mỗi khi sửa, refactor hoặc tạo mới bất kỳ file frontend nào, agent BẮT BUỘC phải đồng thời kiểm tra và migrate file đó sang chuẩn Feature-Sliced Design (FSD)**:
    1. *Đúng tầng FSD*: Đảm bảo file nằm đúng tầng kiến trúc (`shared`, `entities`, `features`, `pages`, `app`). Di dời hoặc tách nhỏ file nếu đang đặt sai vị trí hoặc sai trách nhiệm.
    2. *Public API (`index.ts`)*: Khi sửa file trong `src/features/<slice>/`, nếu slice chưa có `index.ts` (hoặc thiếu export), phải tạo/cập nhật `index.ts` làm Public API duy nhất cho slice đó. Mọi import từ bên ngoài vào slice phải qua `@/features/<slice>` thay vì trỏ xuyên sâu vào file nội bộ.
    3. *Triệt tiêu Cross-Feature Imports*: Nếu file đang sửa import trực tiếp từ một feature slice khác cùng cấp (`@/features/other-feature/...`), phải refactor chuyển phần dùng chung đó xuống tầng dưới (`entities/` hoặc `shared/`), tuyệt đối không để hai feature phụ thuộc lẫn nhau.
    4. *Tách biệt UI & Logic*: Nếu component chứa state phức tạp, side-effects (`useEffect`), timers hoặc API calls, phải trích xuất ra custom hook riêng đặt trong thư mục `hooks/` của slice đó.
    5. *Thay thế Legacy API Facade*: Chuyển đổi các lời gọi từ `src/app/api.ts` tập trung cũ sang API client cục bộ của slice (`features/<slice>/api/...`) hoặc `src/shared/api/client.ts`.
    6. *Bảo toàn Zero Visual Regression & Chạy test*: Luôn bảo toàn 100% giao diện, layout, màu sắc gốc và chạy kiểm thử tương ứng (`npm test` hoặc `vitest`) ngay sau khi chỉnh sửa.
- **Chrome DevTools & Browser Profiling**: Mỗi khi khởi chạy hoặc kết nối Chrome để debug, test, profiling hiệu năng, hoặc dùng `chrome-devtools` MCP, **BẮT BUỘC phải dùng 1 profile riêng biệt** (isolated `--user-data-dir`, ví dụ: `C:\Users\chung\.gemini\chrome-profiles\flama-devtools`). **Tuyệt đối KHÔNG** can thiệp, mở remote debugging hay can thiệp vào profile cá nhân mặc định của người dùng nhằm tránh xung đột cookies/sessions và bảo vệ dữ liệu cá nhân.

## Testing
- **Modular Test Execution**: To avoid long test runs across 100+ suites, use `python scripts/run_tests.py` instead of running full test suites:
  - Run tests for modified/staged files: `python scripts/run_tests.py --changed` (or `npm test` in `frontend/`)
  - Run specific domain modules: `python scripts/run_tests.py --module study,flashcards` (or `--module auth`, `--module payment`, `--module decks`, `--module connect_mcp`, etc.)
  - Filter by layer: `python scripts/run_tests.py --module study --backend-only` or `--frontend-only`
  - List available modules & test matrices: `python scripts/run_tests.py --list-modules`
  - Run full suite only for CI/pre-release verification: `python scripts/run_tests.py --all`
- Prefer the narrowest relevant test module first; most feature areas already have focused tests in `tests/`.
- The suite is flat `unittest` with per-file app/database setup and no shared fixture layer. Copy the closest existing test file instead of inventing a new harness.
- If you touch startup, config, media paths, or DB compatibility logic, verify against the real entry point (`wsgi.py` or Docker) instead of relying only on unit tests.
- If you touch clone overlay flows, validate both direct source ownership cases and installed-clone cases.
- SQLite tests are useful, but MySQL-specific schema behavior still matters for startup and migrations.

## Agent Files & Multi-Agent Framework
- Multi-Agent Orchestration Architecture documentation: `docs/architecture/MULTI_AGENT_COLLABORATION.md`.
- Repo-local skills live in `skills/` (source of truth). `.claude/skills/` mirrors them for Claude Code: after editing `skills/`, run `python scripts/sync_claude_skills.py` (the pre-commit hook does it for staged skill changes, and `tests/test_claude_skills_sync.py` fails on drift). Never edit the mirror directly. `.claude/skills/mysql` is vendored and lives only there.
- Use `$flama-agent-orchestrator` when managing complex full-stack features requiring cross-layer coordination across Frontend, Backend, and Database subagents.
- Use `$flama-frontend-architecture` when refactoring, decomposing, or building React SPA components in `frontend/src/`, enforcing Feature-Sliced Design (FSD), extracting custom hooks, consolidating reusable UI primitives, and preserving Zero Visual Regression.
- Use `$flama-backend-architecture` when building or refactoring Flask REST APIs (`app/api/`), service logic (`app/services/`), repositories (`app/repositories/`), validators (`app/validators/`), Anki scheduling, or Flama Connect protocol.
- Use `$flama-database-architecture` when reviewing, investigating, analyzing, or evolving the Flama MySQL database schema (`models/`), ORM entity boundaries, marketplace clone overlay models, or planning zero-data-loss Alembic migrations (`migrations/`).
- Use `$mysql` (`.claude/skills/mysql/SKILL.md`, vendored from PlanetScale) for MySQL/InnoDB query optimization, `EXPLAIN` analysis, index design, N+1 fixes, data types, locking/deadlocks, and online DDL. Pair it with `$flama-database-architecture` for Flama-specific domain modeling.
- Use `$antigravity-cli` when installing, verifying, or operating the local `agy` command, including restoring its PATH shim and selecting safe versus full-access execution.
- Use `$antigravity-manager-api` when checking or operating the local Antigravity Manager HTTP API for account status, quota refresh, or explicit account switching. Never store its API key in the repository.
- The user authorizes `agy` as an implementation worker for assigned tasks. Follow `$antigravity-cli` worker orchestration: isolate file ownership, review every diff, and rotate only the `agy` account through Manager when the applicable quota is at or below the documented threshold.
- Use `$codex-cli` when discovering, verifying, running, or delegating tasks/reviews to the local OpenAI Codex CLI (`codex.exe`).
- Use `$docs-architect` when the task is to create or update repository documentation such as `README.md`, `README_SETUP.md`, `docs/*.md`, troubleshooting notes, or operational runbooks.
- Use `$nihongo-agent-architect` when the task is to create or update repo-local agent guidance such as `AGENTS.md`, skill folders under `skills/`, or `agents/openai.yaml`.
- Use `$impeccable` when designing, reviewing, auditing, critiquing, styling, or polishing frontend UI/UX in `frontend/src/`.
- Use `$stitch-skills` (bao gồm `$generate-design`, `$react-components`, `$shadcn-ui`, `$manage-design-system`, `$extract-design-md`, `$code-to-design`) khi cần tương tác với Google Stitch MCP để sinh màn hình, quản lý design system, trích xuất HTML sang Stitch, hoặc tạo React component từ thiết kế Stitch.
- Use `$chrome-devtools` khi cần profiling hiệu năng, đo lường Core Web Vitals, kiểm tra render cycles, rò rỉ bộ nhớ (memory leaks), phân tích network waterfall, hoặc debug giao diện chuyên sâu qua Chrome DevTools MCP.
- Keep agent guidance short, repo-specific, and workflow-oriented. Avoid generic Flask or prompt-engineering tutorials.
