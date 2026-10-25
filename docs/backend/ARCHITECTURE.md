# Flama Backend Architecture Specification

- **Domain**: Flask Modular Monolith & Companion Services
- **Root Paths**: `app/`, `models/`, `connect_wsgi.py`, `flama-audio/`
- **Specification Status**: Active / Production Ground Truth
- **Backend Stack**: Python 3.12, Flask, SQLAlchemy 2.0, Flask-Migrate (Alembic), Flask-Login, MySQL 8 / SQLite, Werkzeug

---

## 1. System Overview & Service Topology

The Flama backend is a Python/Flask modular monolith designed to power a fully decoupled React 19 SPA, complemented by two specialized companion services:

```
+--------------------------------------------------------------------------------------------------+
|                                    Flama Backend Service Topology                                |
+--------------------------------------------------------------------------------------------------+
                                                 |
         +---------------------------------------+---------------------------------------+
         |                                       |                                       |
         v                                       v                                       v
+-----------------------------+     +-----------------------------+     +-----------------------------+
|   Flama Core Flask API      |     |     Flama Connect Bridge    |     |   Flama Audio Companion     |
|   `wsgi.py` (Port 4789)     |     |   `connect_wsgi.py` (4790)  |     |   .NET 8 WPF (Port 4791)    |
|   - Flask Application Fact. |     |   - Isolated WSGI Service   |     |   - Kestrel Local HTTP      |
|   - REST API under `/api`   |     |   - Yomitan / AnkiConnect   |     |   - VoiceVox Engine         |
|   - 102 SQLAlchemy Models   |     |   - Smart Scheme CORS       |     |   - Kokoro TTS Engine       |
|   - Anki SM-2 / FSRS Sched. |     |   - Extension Auto-Approval |     |   - Pairing Handshake       |
|   - Marketplace & payOS     |     |   - MCP AI Search Protocol  |     |   - Portable Binary         |
+-----------------------------+     +-----------------------------+     +-----------------------------+
               |                                   |                                   |
               +-----------------+-----------------+                                   |
                                 |                                                     |
                                 v                                                     v
                   +---------------------------+                         +---------------------------+
                   |  MySQL Database (Primary) |                         | Local Audio Device / Mic  |
                   |  - In-Memory for Tests    |                         | Synthesis Output (.WAV)   |
                   +---------------------------+                         +---------------------------+
```

### System Processes
1. **Flama Core (`wsgi.py`, Port 4789)**: Primary API server serving REST resources, static assets, media proxy, and the React SPA shell via Gunicorn in production.
2. **Flama Connect (`connect_wsgi.py`, Port 4790)**: High-throughput Yomitan / AnkiConnect protocol bridge and Model Context Protocol (MCP) server running in process isolation.
3. **Flama Audio (`flama-audio/`, Port 4791)**: Desktop companion (.NET 8 WPF + Kestrel) providing zero-cost, offline neural Japanese text-to-speech.
4. **Study Worker (`study_worker.py`)**: Standalone background worker process consuming asynchronous study session commits without HTTP request overhead.

---

## 2. Flask Application Factory & Bootstrap Lifecycle

### 2.1 Factory Patterns (`app/__init__.py`)

The application avoids global app state by utilizing the Application Factory pattern:

#### 1. `create_app(config=None, audit_mode=False)` (lines 32–313)
- **Elimination of Jinja2**: Configures `template_folder=None`. All server-side Jinja rendering is permanently disabled; the SPA shell is delivered statically via `app/spa.py`.
- **Media Cache Hardening**:
  ```python
  # app/__init__.py:17-30
  class MediaHardenedSessionInterface(PublicMediaSessionInterface):
      """Ensure media responses never leak Vary: Cookie or Set-Cookie."""

      def save_session(self, app, session, response) -> None:
          super().save_session(app, session, response)
          if has_request_context() and (
              request.path == "/media/proxy" or request.path.startswith("/media/proxy/")
          ):
              response.vary.discard("Cookie")
              if not response.vary:
                  response.headers.pop("Vary", None)
              while "Set-Cookie" in response.headers:
                  response.headers.remove("Set-Cookie")
  ```
  Prevents session tokens and private cookies from contaminating public reverse-proxy media caches.
- **Proxy Configuration**: When `TRUST_PROXY=True`, wraps the WSGI pipeline in `werkzeug.middleware.proxy_fix.ProxyFix(x_for=1, x_proto=1, x_host=1)`.
- **Extension Initialization**:
  - `db.init_app(app)` (SQLAlchemy 2.0 mapping; `db` is instantiated in `models/__init__.py`)
  - `migrate.init_app(app, db)` (Alembic schema migrations; initialized from `app/extensions.py`)
  - `login_manager.init_app(app)` (Flask-Login session manager; initialized from `app/extensions.py`)
- **Model Registration**: Explicitly imports over 45 SQLAlchemy models during initialization to guarantee complete metadata binding before migrations or queries execute.
- **Error Handlers**:
  - `FieldIdentityConflict` -> HTTP 409
  - `StaleDataError` -> HTTP 409 (Optimistic concurrency lock conflict)
  - `RequestValidationError` -> HTTP 400
  - HTTP 404 -> Automatically delegates non-API routes to `serve_react_spa()` for client-side routing.

#### 2. `create_audit_app(config=None)` (lines 315–323)
Strict read-only factory for forensic auditing, test inspection, and schema verification. Disables all maintenance mutators, cutover routines, and background seeders.

### 2.2 Startup Lifecycle & Passive Production Check (`app/startup.py`)

Startup inside the app context executes `run_startup_maintenance(app)`:
1. **Connectivity Probe**: Executes `SELECT 1` against the configured database.
2. **Maintenance Gate (`STARTUP_RUN_MAINTENANCE`)**:
   - **Production Mode**: **`STARTUP_RUN_MAINTENANCE=False`**. The database schema is strictly managed by versioned Alembic migrations. The server boots immediately after the `SELECT 1` check.
   - **Development / Test Mode (`STARTUP_RUN_MAINTENANCE=True`)**:
     - `db.create_all()`
     - `ensure_user_management_schema(db.session)`
     - `ensure_backward_compatible_schema()` (905 lines of defensive DDL inspections in `app/startup_schema.py` patching legacy table drift)
     - `ensure_default_user_roles(db.session)`
     - `ensure_default_taxonomy_data(db.session)`
     - `ensure_default_tts_providers(db.session)` (if `STARTUP_RUN_DEFAULT_TTS_PROVIDER_SEED=True`)
     - `flashcards_share.cutover_clone_model_to_overlay_only(...)` (if `STARTUP_RUN_CLONE_CUTOVER=True`)

### 2.3 CLI Command Architecture (`app/cli.py`)
Over 1,870 lines of administrative commands registered under `@app.cli.command`:
- **Study Authority & Phase 9**: `study-authority-enrollment`, `study-authority-learners`, `study-authority-read-audit`, `study-phase9-readiness`, `study-session-retention`.
- **Analytics & Outbox Processing**: `review-analytics-status`, `review-analytics-reconcile`, `review-analytics-backfill`, `review-analytics-drain`.
- **Deck Counts & Prewarming**: `deck-counts-status`, `deck-counts-prewarm`, `forecast-summary-prewarm`.
- **Marketplace & Seeding**: `taxonomy-seed`, `deck-release-bootstrap`, `market-stats-reconcile`, `marketplace-samples-backfill`.
- **Asset Pipelines**: `seed-production-strokes`, `cleanup-wrong-strokes`.

---

## 3. REST API Layer Architecture

### 3.1 Canonical API Architecture (`app/api/v1/`)
All modern endpoints are consolidated under the `/api` prefix via `api_v1_bp` (`app/api/v1/__init__.py`).

#### Usage Quotas
Web app requests under `/api` are not metered: studying, browsing, the dashboard and settings are free.
`app/services/quota_service.py` meters three kinds instead:
- **api**: Flama Connect actions authenticated by a user API token (`app/connect/request_pipeline.py`); a `multi` batch costs one unit per action.
- **mcp**: `tools/call` on private tools (`app/connect/mcp.py`); `initialize`, `tools/list` and public tools are free.
- **media**: bytes a user uploads or crawls and the server stores (note media, pasted images, image library uploads, Connect media); limits are in MB.

Limits live in `quota_policies` (per kind: monitor/enforce, day/month/year period, role defaults) and `user_quota_overrides` (per user and kind, optional expiry), both edited on `/admin/quotas`. One Redis script checks the limit and increments the day, month and year counters plus per-period usage and over-limit rankings (kept about 400 days). In monitor mode nothing is blocked; over-limit traffic is only ranked. Limits are cached per worker for 30 seconds. `RATE_LIMIT_DAILY_ENABLED=false` turns metering off, and `RATE_LIMIT_DAILY_TIMEZONE` sets the period boundaries.

#### Canonical Blueprints Matrix
| Blueprint | Source Path | Base Prefix | Responsibility |
|---|---|---|---|
| `health_bp` | `app/api/v1/health.py` | `/health` | Liveness and readiness probes |
| `identity_bp` | `app/api/v1/identity/` | `/identity` & `/auth` | Authentication, password reset, login, OAuth URLs |
| `decks_bp` | `app/api/v1/decks/` | `/decks` | Deck tree hierarchy, CRUD, access keys, deck moves |
| `flashcards_v1_bp` | `app/api/v1/flashcards/`| `/` | Note types, field definitions, template attachments, media uploads |
| `analytics_bp` | `app/api/v1/analytics/` | `/analytics` | Dashboard review statistics, retention heatmaps |
| `admin_bp` | `app/api/v1/admin/` | `/admin` | User RBAC, fee schedules, audit logs, TTS keys |
| `billing_bp` | `app/api/v1/billing/` | `/billing` | payOS payments, checkout creation, webhook ingestion |
| `learning_bp` | `app/api/v1/learning/` | `/browse` & `/study` | Vocabulary search, virtualized card table, batch edits, study session queue & ratings (`study_bp`) |
| `marketplace_*` | `app/api/v1/marketplace/`| `/marketplace` | Shared deck marketplace, reviews, taxonomy, deck installs |
| `creator_*` | `app/api/v1/creator/` | `/creator` | Creator deck licensing keys (`creator_deck_keys_bp`) |
| `download_bp` | `app/api/v1/download.py` | `/download` | Authenticated file and media asset downloads |
| `profile_bp` | `app/api/v1/profile/` | `/profile` | User profile, avatar management, biography |
| `wallet_bp` | `app/api/v1/wallet/` | `/wallet` | Creator revenue balances, payout requests |
| `settings_bp` | `app/api/v1/settings/` | `/settings` | Scheduler configuration, integration tokens |
| `strokes_bp` | `app/api/v1/strokes/` | `/strokes` | Kanji/Hanzi SVG stroke order delivery |
| `images_bp` | `app/api/v1/images.py` | `/images` | Centralized image library search |
| `tickets_bp` | `app/api/v1/tickets.py` | `/tickets` | User support tickets and threaded replies |
| `worksheets_bp` | `app/api/v1/worksheets/`| `/worksheets` | PDF Japanese practice worksheet generator |

### 3.2 Blueprint Consolidation & Canonical Study Routes
Core REST endpoints are consolidated under the canonical API hierarchy:
1. **`app/api/v1/` (`api_v1_bp`)**: Canonical modular REST API (300 endpoints).
   - Core flashcard study endpoints (`/api/study/sessions`, `/api/study/next`, `/api/study/cards/<id>/answer`, `/api/study/sessions/<id>/commit`) are canonicalized under `app/api/v1/learning/study.py` as `study_bp` within `learning_bp`.
   - All 45 route-level `db.session.commit()` calls in `app/api/v1/` have been removed in favor of service transaction boundaries.
2. **`app/routes/`**: Legacy blueprints and SSR stubs (pruned during October 2026 debt remediation):
   - `app/routes/flashcards/study.py`: Preserved for compatibility with legacy test patch harnesses.
   - `app/routes/flashcards/change_requests.py`: Houses `/api/deck-change-requests/...`.
   - `app/routes/flashcards/share.py`: Houses legacy `/api/shared/decks/...`.
   - `app/routes/vocabulary.py`: Pruned from 718 LOC to 117 LOC (17 dead 410 stubs and duplicate browse endpoints removed).

### 3.3 Authentication & Authorization
- **Session Authentication**: Cookie-based via `Flask-Login` (`HttpOnly=True`, `SameSite='Lax'`). CSRF validated through Flask-WTF (`X-CSRFToken` header).
- **Bearer Tokens**: `UserApiToken` models support headless API and Flama Connect client access.
- **Role Decorators (`app/api/common/security.py`)**:
  - `@admin_required`: Restricts route to `is_admin_user(current_user) == True`. Returns 403 JSON `{"error": "FORBIDDEN"}`.
  - `@creator_required`: Restricts route to creators and administrators.
- **OAuth 2.0 & MCP Authentication (`app/routes/oauth.py`)**:
  - Full RFC 6749 authorization code grant flow (`/oauth/authorize`, `/oauth/token`).
  - RFC 7636 PKCE validation (`code_challenge` using SHA-256).
  - RFC 9728 Protected Resource metadata at `/.well-known/oauth-protected-resource`.

---

## 4. Persistence Architecture & Data Models (`models/`)

The repository contains **102 distinct model files** under `models/`, inheriting from declarative `models.db.Model`.

### 4.1 The Virtual Entity Paradigm: `Card` is Not a Physical Table (ADR P11)
A foundational design decision in Flama is that the physical `cards` table has been retired:
- **File**: `models/card.py:165-189`
- `Card` is mapped to an ORM subquery view (`_presentations`) that dynamically pairs `Note` and `StudyApplication`:
  ```python
  # models/card.py
  _presentations = select(
      (_notes.c.id + literal('.') + _applications.c.id).label("id"),
      _notes.c.id.label("note_id"),
      _applications.c.template_id.label("template_id"),
      _applications.c.id.label("application_id"),
      _applications.c.status_code.label("application_status"),
      ...
  ).select_from(_pair_join).subquery("card_presentations")
  ```
- **Composite Key**: `<note_id>.<application_id>`. This composite identity remains completely stable across template edits and never duplicates rows when templates are modified or reordered.
- Wire compatibility is preserved via the `card_presentation_aliases` table: old random Card IDs (still named by 98% of `review_events`, older study sessions and every Flama Connect source ref) resolve to their pair. Aliases no longer decide membership: since 2026-10-24 every Note is shown through every ACTIVE application of its NoteType. The `card_presentation_cutover_*` tables are an archive no read depends on; the cutover archived a Card for every original pair (111,743 of 111,743, and production still matched), and a derived Card cannot drift from Note x application.

### 4.2 Study Progress & Authority Decoupling (ADR P10)
Study progress is decoupled from card presentation records:
- **`StudyProgressSubject` (`models/study_progress_subject.py`)**: Canonical progress record keyed by `(learner_user_id, logical_note_key)`.
  - Holds scheduling state in `state_payload` JSON.
  - Normalized queues: `new`, `learning`, `review`, `relearning`.
  - Scheduling dates: `due_at` (timestamp) and `due_day` (day ordinal index).
- **`StudyAuthorityEnrollment` (`models/study_authority_enrollment.py`)**: Controls whether a learner routes to `NOTE` authority (consolidated modern progress) or `LEGACY` authority.
- **`StudyAuthorityCommandReceipt`**: Idempotency token preventing duplicate review execution during network retries.
- **`ReviewEvent` (`models/review_event.py`)**: Append-only immutable historical audit log of every answer rating.
- **Review Analytics (`models/review_analytics.py`)**: Pre-aggregated daily review statistics tables (`DailyReviewCount`, `ReviewAnalyticsHead`, `ReviewAnalyticsGeneration`), supported by outbox event logging (`ReviewAnalyticsOutbox`).
- **Analytics evidence (counts read rows as stored)**: dashboard, overview and forecast counts take their Note scope from `deck_note_scope` or `collection_note_scope` (`app/repositories/note_analytics_scope_repository.py`) and read `study_progress_subjects` as stored: a damaged row (detached, drifted logical key, quarantined without state) miscounts only its own Note. Since 2026-10-24 these reads run no evidence scan; that guard dated from the P5–P11 cutovers, cost 100–160 ms per API on the production dump, and turned one damaged row into a 409 for the whole page. Damage is found by the offline `study-authority-read-audit` (run it after any data migration or backfill). Study queue counts and Browse pages still fail closed on their bounded rows (`study_repository.query_study_queue_counts`, `browse_card_repository.page_window_integrity`; the Browse Note list runs `guard_scope()`). The contract is pinned by `tests/test_note_query_retirement.py` (`test_progress_readers_contract_*`) and, for the MySQL overview path, `scripts/probe_dashboard_due_counts_mysql.py`.

### 4.3 Logical Overlay Clone Model (Marketplace)
To prevent database bloat when users install community decks, Flama implements a **Logical Overlay** model:
- `DeckInstall` (`models/deck_install.py`): Tracks deck installations (`clone_mode='logical_overlay'`). Source notes are never duplicated.
- `DeckCloneDeckMap` (`models/deck_clone_deck_map.py`): Maps author's source deck hierarchy to learner's local tree.
- `DeckCloneNoteFieldOverride` (`models/deck_clone_note_field_override.py`): Stores learner-specific edits to fields without mutating author's original note.
- `DeckCloneAddedNote` (`models/deck_clone_added_note.py`): Allows learners to add private notes into installed shared decks.
- `DeckChangeRequest` (`models/deck_change_request.py`): Pull-request-style contributions from learners back to original deck authors.
- `DeckRelease` (`models/deck_release.py`): Immutable versioned release snapshot of a published deck.

### 4.4 Core Entity Catalog
- `User` (`models/user.py`): User credentials, timezone, avatar, biography.
- `UserRole` (`models/user_role.py`): RBAC role mappings (`admin`, `creator`, `user`).
- `Deck` (`models/deck.py`): Hierarchical tree via `parent_id` (self-referential foreign key), `owner_user_id`, `position`.
- `NoteType` (`models/note_type.py`): Note schema owning field definitions and template applications.
- `FieldDef` (`models/field_def.py`): Field definition (`name`, `field_type`, `position`, `identity_role`). Native JSON array support.
- `Note` (`models/note.py`): Content container holding `field_values` (JSON dict), `tags` (JSON array), and `content_revision`.
- `StudyApplication` (`models/study_application.py`): Binds `NoteType` to `Template` versions (`ACTIVE` / `RETIRED`) with `input_bindings` JSON.
- `Template` (`models/template.py`): HTML / Mustache markup (`front_html`, `back_html`, `shared_css`).

---

## 5. Service & Repository Layer Architecture

### 5.1 Service Layer (`app/services/` — 167 modules)
Services own business logic orchestration and transaction boundaries:
- **`anki_scheduler.py`**: Pure scheduling math (SM-2 and FSRS algorithms).
- **`browse_card_service.py`**: Browse table orchestration, dynamic filtering, sorting, and batch card updates.
- **`deck_management_service.py`**: Deck lifecycle, cycle-resistant tree moves, and progress resetting.
- **`deck_release_service.py`**: Snapshotting and publishing immutable releases of shared decks.
- **`flashcard_renderer.py`**: Mustache compilation, field replacement, furigana rendering, and CSP sandbox generation.
- **`flashcards_share_service.py`**: Lightweight compatibility facade (26 LOC) re-exporting from modular `app/services/share/` package (comprising `install.py`, `publish.py`, `overlay.py`, `cutover.py`, `helpers.py`, `constants.py`, `note_types.py`).
- **`study_session_service.py`**: Study session lifecycle, queue building, and answer rating validation.
- **`payment/`**: Canonical payment implementation: checkout/pricing (`checkout.py`), order lifecycle (`orders.py`), entitlement grants (`fulfillment.py`), PayOS webhooks (`webhook.py`), and response presentation (`status_display.py`, `presenters.py`). `base.py` owns shared constants and `PaymentServiceError`; `payment_service.py` only re-exports this package for compatibility.

### 5.2 Repository Layer (`app/repositories/` — 46 modules)
Repositories encapsulate database query execution:
- `vocabulary_repository.py`: Hierarchical deck tree queries, accessible deck filtering, and subtree rollups.
- `study_repository.py`: Due queries, queue counts aggregation, review due expressions, and `StudyProgressSubject` queries.
- `study_authority_repository.py`: Fenced locking (`lock_study_authority_route`) ensuring serial access during authority cutovers.
- `flashcards_share_repository.py`: Installation queries, overlay resolutions, and clone mapping lookups.
- `stats_query_repository.py`: Aggregate SQL for retention rates, streak calculations, and hourly study distributions.

---

## 6. Anki Scheduler & Study Runtime Logic

### 6.1 Scheduler Engine (`app/services/anki_scheduler.py`)
Implements two spaced repetition algorithms:
1. **SM-2**: Exponential interval expansion based on ease factor (starting ease 2.5, min ease 1.3), learning steps (`1m`, `10m`), graduating interval (1 day), and easy bonus (1.3).
2. **FSRS**: Free Spaced Repetition Scheduler modeling memory stability and difficulty (`FsrsMemoryState`).

### 6.2 Timezone & Day-Boundary Calculation
Study intervals are computed based on day ordinals rather than timestamps to prevent review drift:
- `_day_index(moment, boundary_hour, timezone_name)` (line 703):
  1. Converts UTC timestamp to learner's local timezone.
  2. Shifts the time backward by `boundary_hour` (default 04:00 AM local time).
  3. Returns `date.toordinal()`.
  Sessions between midnight and 04:00 AM count towards the previous calendar day's streak and review counts.
- `_day_index_to_datetime(day_index, boundary_hour, timezone_name)` (line 709):
  Converts an integer day ordinal back to UTC datetime corresponding to 04:00 AM local time.
- Statistics group local days in SQL when `stats_query_repository.fixed_utc_offset_minutes(timezone_name)` returns an offset: the zone's UTC offset is constant on the 1st and 15th of every month from 2000 to 2040 (aliases such as `Asia/Saigon` and half-hour zones qualify). Zones with DST or offset changes use the Python path. Both paths share the same scopes; `scripts/probe_dashboard_due_counts_mysql.py` checks their parity on MySQL.

---

## 7. Companion Services Architecture

### 7.1 Flama Connect (`connect_wsgi.py` / `app/connect/`, Port 4790)
- **Role**: High-performance Yomitan and AnkiConnect protocol bridge enabling 1-click word mining from browser extensions into Flama decks.
- **Decoupling**: Runs in process isolation. Does not load Flask-Login, session cookies, or CSRF filters.
- **Smart Scheme CORS Policy (`app/connect/request_pipeline.py`)**:
  - Automatically approves extension origins: `chrome-extension://*` and `moz-extension://*` (supporting Firefox's per-profile dynamic UUIDs).
  - Web origins (`http://`, `https://`) strictly validated against `CONNECT_ANKI_ALLOWED_ORIGINS` (default fallback is `("https://killergerbah.github.io",)`; web clients like `https://asbplayer.dev` are configurable via environment). Non-whitelisted web origins receive 403 Forbidden without CORS headers.
  - Non-browser/desktop clients (cURL, Python, WPF) with no `Origin` header are allowed when accompanied by a valid API token.
- **Brand Protection Mandate**: The service is branded as **Flama Connect**, never "Anki".

### 7.2 Flama Audio Desktop Companion (`flama-audio/`, Port 4791)
- **Role**: Windows desktop application (.NET 8 WPF + Kestrel HTTP API) providing offline Japanese text-to-speech synthesis without external cloud API keys.
- **Engines**: Local VOICEVOX Engine (`http://127.0.0.1:50021`) and Kokoro TTS.
- **Distribution**: Single-file portable self-contained executable (`FlamaAudio-Portable.exe`). Authenticode signed via GitHub Actions release workflow.
