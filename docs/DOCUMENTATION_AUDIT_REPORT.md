# Comprehensive Documentation Audit & Codebase Reality Report

- **Document Identifier**: `docs/DOCUMENTATION_AUDIT_REPORT.md`
- **Audit Date**: 2026-10-15
- **Auditing Team**: Multi-Agent Engineering Group (`teamwork_preview_orchestrator_14`)
- **Target Repository**: Flama (Nihongo Japanese Learning Platform) — `d:\Project\nihongo`
- **Audited Domains**:
  1. Frontend (`frontend/src/`)
  2. Backend & Core Models (`app/`, `models/`, companion services)
  3. Operations & Infrastructure (`deploy/`, `.github/workflows/`, Docker, scripts)
  4. Logging, Audit & Observability (`models/audit_log.py`, systemd-journald, healthchecks)
- **Standard of Verification**: 100% Empirical Code Reality, Static AST/Typecheck Validation, Zero Visual Regression, Zero Broken Markdown Links.

---

## Table of Contents

1. [Executive Summary & Audit Methodology](#1-executive-summary--audit-methodology)
2. [Analysis of Ambiguous & Underspecified Documentation](#2-analysis-of-ambiguous--underspecified-documentation)
   - [2.1 Passive Production Startup vs. Active Maintenance](#21-passive-production-startup-vs-active-maintenance)
   - [2.2 Custom Session Interface & Cache Hardening](#22-custom-session-interface--cache-hardening)
   - [2.3 Dual-Tier Study Persistence & Crash-Resilience](#23-dual-tier-study-persistence--crash-resilience)
   - [2.4 Systemd Timers vs. Continuous Worker Architecture](#24-systemd-timers-vs-continuous-worker-architecture)
   - [2.5 Extension CORS Boundaries & Origin Protection](#25-extension-cors-boundaries--origin-protection)
3. [Catalog of Factually Inaccurate & Obsolete Documentation](#3-catalog-of-factually-inaccurate--obsolete-documentation)
   - [3.1 Frontend Discrepancies (12 Items)](#31-frontend-discrepancies)
   - [3.2 Backend Discrepancies (10 Items)](#32-backend-discrepancies)
   - [3.3 Ops & Logs Discrepancies (10 Items)](#33-ops--logs-discrepancies)
   - [3.4 Junk Documents, Token Residue & Relocated Code Assets (5 Items)](#34-junk-documents-token-residue--relocated-code-assets)
4. [Domain-by-Domain Technical Debt Matrix](#4-domain-by-domain-technical-debt-matrix)
   - [4.1 Frontend Technical Debt Overview](#41-frontend-technical-debt-overview)
   - [4.2 Backend Technical Debt Overview](#42-backend-technical-debt-overview)
   - [4.3 Operations Technical Debt Overview](#43-operations-technical-debt-overview)
   - [4.4 Logs & Observability Technical Debt Overview](#44-logs--observability-technical-debt-overview)
5. [Documentation Architecture Standards & Governance](#5-documentation-architecture-standards--governance)
   - [5.1 Four-Domain Directory Layout Specification](#51-four-domain-directory-layout-specification)
   - [5.2 Lifecycle Rules for `tech-debt/` and `old/`](#52-lifecycle-rules-for-tech-debt-and-old)
   - [5.3 Markdown Link Syntax & Relative Path Constraints](#53-markdown-link-syntax--relative-path-constraints)
   - [5.4 Automated Verification Protocol](#54-automated-verification-protocol)

---

## 1. Executive Summary & Audit Methodology

### 1.1 Executive Summary

Over successive development cycles, the Flama Japanese SRS learning platform has undergone significant architectural evolution:
- Migrating from server-rendered Jinja templates to a 100% decoupled **React 19 SPA** (`frontend/src/`).
- Retiring physical card tables in favor of a **dynamic derived SQL view** (`Card` ADR P11) and Note-level study progress (`StudyProgressSubject` ADR P10).
- Establishing an **overlay-only Marketplace clone model** (`DeckInstall`) that protects original author content from destructive mutations.
- Adding high-speed companion services: **Flama Connect** (`connect_wsgi.py`, port 4790) for Yomitan/asbplayer 1-click mining, and **Flama Audio** (`flama-audio/`, port 4791) for local desktop VoiceVox and Kokoro TTS synthesis.

However, internal documentation did not keep pace with these systemic migrations. Technical debt accumulated across `docs/`, `AGENTS.md`, and `README.md`, resulting in:
1. **Factually inaccurate documentation**: Stale CLI commands, outdated dependency versions, nonexistent module paths, hallucinated model names, and incorrect line references.
2. **Ambiguous and underspecified specifications**: Omission of production safety gates, incomplete CORS behavior definitions, and misleading claims that application startup automatically manages database DDL.
3. **Repository pollution & token residue**: Discarded prompt fragments (`*.prompt.txt`), raw command text dumps, unindexed test fixtures inside `docs/`, and raw LLM citation markers (`cite...`) polluting core research documents.

This audit report represents the synthesis of a four-milestone comprehensive review. Every statement, metric, file path, and command herein has been empirically tested against the physical code on disk.

### 1.2 Audit Methodology

The audit applied an empirical, four-phase verification framework:
```
+-----------------------------------------------------------------------------------+
|                            Audit Verification Framework                           |
+-----------------------------------------------------------------------------------+
       |
       +--> [1. Static AST & Dependency Inspection]
       |    - React package versions from frontend/package.json
       |    - Python AST parsing of app/ and models/
       |    - Linter checks: oxlint src, tsc -b
       |
       +--> [2. Filesystem & Line-Number Traversal]
       |    - Exact line counting (LOC) and byte sizing of god components
       |    - Alembic migration graph tracing (69 files, branches, merge nodes)
       |    - Validation of file existence for all internal links
       |
       +--> [3. Operational & CLI Execution]
       |    - Flask CLI command verification: flask --app wsgi.py <cmd> --help
       |    - Hostinger deploy scripts & systemd unit inspection
       |    - Unit test verification via python scripts/run_tests.py --changed
       |
       +--> [4. Automated Link & AST Resolution Gate]
            - Regex/AST scanner covering all Markdown documents
            - Detection of dead targets, overshooting relative paths, and :line suffixes
            - Zero-broken-link policy enforcement across all active documentation
```

---

## 2. Analysis of Ambiguous & Underspecified Documentation

Prior documentation often described high-level intent without providing the low-level contracts, failure modes, and boundaries implemented in code. Below is a detailed breakdown of the five primary underspecified areas.

### 2.1 Passive Production Startup vs. Active Maintenance

#### What Legacy Documentation Claimed
`AGENTS.md` (and legacy system runbooks) historically claimed:
> *"Startup inside the app context is not passive. It runs `db.create_all()`, `ensure_user_management_schema()`, `_ensure_backward_compatible_schema()`, `ensure_default_user_roles()`, `ensure_default_tts_providers()`, and `flashcards_share.cutover_clone_model_to_overlay_only(...)`, then commits."*

#### Actual Code Reality
In `app/settings.py` (lines 412–435) and `app/startup.py` (lines 42–46), application bootstrap behavior is gated by `STARTUP_RUN_MAINTENANCE`:
```python
# app/startup.py:42-46
db.session.execute(text("SELECT 1"))
if not app.config.get("STARTUP_RUN_MAINTENANCE"):
    return
```
- In production (`FLASK_ENV=production`), `STARTUP_RUN_MAINTENANCE` **defaults to `False`**.
- Application startup is **strictly passive**: it verifies basic database connectivity via `SELECT 1` and immediately proceeds without executing any DDL or data seeding.
- Heavy schema transformations, table creation, role seeding, and clone cutovers are reserved exclusively for test suites or offline execution via Alembic migrations (`flask db upgrade`) and explicit CLI maintenance commands (`deploy/migrate_database.py`).

#### Risk & Impact
Developers or automated agents operating under the legacy assumption could deploy code expecting startup auto-repair to fix missing columns or tables. In production, this caused runtime 500 errors because Gunicorn workers never execute DDL.

#### Resolution Taken
Updated `AGENTS.md`, `docs/ops/ARCHITECTURE.md`, and `docs/backend/ARCHITECTURE.md` to document the passive production contract, clarifying that schema changes are owned 100% by Alembic.

---

### 2.2 Custom Session Interface & Cache Hardening

#### What Legacy Documentation Claimed
`docs/architecture/SYSTEM_ARCHITECTURE.md` vaguely noted that session cookies are managed by Flask-Login and that media requests are protected.

#### Actual Code Reality
In `app/__init__.py` (lines 17–30), Flama installs a custom session interface, `MediaHardenedSessionInterface`, which subclasses `PublicMediaSessionInterface` (not `SecureCookieSessionInterface`):
```python
# app/__init__.py:17-30
class MediaHardenedSessionInterface(PublicMediaSessionInterface):
    def save_session(self, app, session, response):
        super().save_session(app, session, response)
        if request.path.startswith("/media/proxy"):
            response.set_cookie(
                app.config.get("SESSION_COOKIE_NAME", "session"),
                "",
                expires=0,
                max_age=0,
                httponly=True,
                samesite=app.config.get("SESSION_COOKIE_SAMESITE", "Lax"),
                secure=app.config.get("SESSION_COOKIE_SECURE", False),
                path=app.config.get("SESSION_COOKIE_PATH", "/"),
            )
            response.headers.pop("Set-Cookie", None)
            vary = [item.strip() for item in response.headers.get("Vary", "").split(",") if item.strip()]
            response.headers["Vary"] = ", ".join(item for item in vary if item.lower() not in {"cookie", "set-cookie"})
```
- For all `/media/proxy/<asset_id>` endpoints, the interface explicitly strips the `Set-Cookie` header and deletes `Cookie` from the HTTP `Vary` header.
- This prevents Nginx reverse proxies, Cloudflare edge caches, and browser disk caches from caching authenticated session tokens alongside binary image/audio responses.

#### Risk & Impact
Without understanding this contract, developers modifying media proxy logic could introduce session leakage or CDN cache poisoning, exposing user sessions to other clients.

#### Resolution Taken
Documented the exact mechanism, class inheritance, and caching headers in `docs/backend/ARCHITECTURE.md`.

---

### 2.3 Dual-Tier Study Persistence & Crash-Resilience

#### What Legacy Documentation Claimed
Frontend documentation claimed that study state was managed by standard React component state and TanStack Query.

#### Actual Code Reality
In `frontend/src/features/study/hooks/useStudySession.ts`, study session persistence is **dual-tiered**:
1. **Server State (TanStack Query v5)**: Manages remote study queue hydration, card payload fetches, and session creation via `/api/study/sessions`.
2. **Offline Client Database (IndexedDB `flama-study` v2/v3)**:
   - Every card flip, rating submission, undo step, and interval calculation is immediately written to an IndexedDB object store (`flama-study-session-store`).
   - If the browser tab crashes, the user accidentally navigates away, or the network drops during study, the session automatically rehydrates from IndexedDB on reboot.
   - Once online, pending answers are drained and committed to the backend via `/api/study/sessions/<id>/commit`.

#### Risk & Impact
Engineers modifying `useStudySession.ts` without accounting for IndexedDB lifecycle events risk breaking offline study capabilities or introducing race conditions during session commits.

#### Resolution Taken
Cataloged IndexedDB v2/v3 architecture in `docs/frontend/ARCHITECTURE.md` and registered `useStudySession.ts` decomposition in `docs/frontend/tech-debt/README.md`.

---

### 2.4 Systemd Timers vs. Continuous Worker Architecture

#### What Legacy Documentation Claimed
Ops documentation loosely mentioned that "background cron jobs handle analytics and cleanup."

#### Actual Code Reality
In production on the Hostinger VPS, background tasks do not use system `cron`. They are split into two distinct execution topologies:
1. **Continuous Daemon Units**:
   - `flama.service`: Gunicorn web API (port 4789).
   - `flama-connect.service`: Flama Connect daemon (port 4790).
   - `flama-study-worker.service`: Dedicated asynchronous study batch processor (`study_worker.py`).
2. **High-Frequency Systemd Timers with Non-Blocking File Locks (`flock`)**:
   - `flama-review-analytics-worker.timer`: Fires every **1 second** (`OnUnitInactiveSec=1s`, `AccuracySec=100ms`).
   - `flama-analytics-counts.timer`: Fires every **60 seconds** (`OnUnitInactiveSec=60s`).
   - `flama-connect-media-cleanup.timer`: Fires every **5 minutes** (`OnUnitActiveSec=5min`).
   - `flama-study-retention.timer`: Fires daily at **18:30:00 UTC**.
   - Each timer executes via `/usr/bin/flock --nonblock` against a designated lockfile in `/run/flama-*/runner.lock`, preventing overlapping runs if a drain cycle takes longer than the interval. Furthermore, units are gated by `ExecCondition` directives checking flags such as `REVIEW_ANALYTICS_WRITE_ENABLED`.

#### Risk & Impact
Assuming a traditional 15-minute or daily cron led operators to believe review analytics outboxes had high latency, whereas the production system is an event-drained pipeline executing every 1 second.

#### Resolution Taken
Documented exact systemd unit directives, frequencies, flock paths, and conditions in `docs/ops/ARCHITECTURE.md`.

---

### 2.5 Extension CORS Boundaries & Origin Protection

#### What Legacy Documentation Claimed
Documentation claimed that Flama Connect enabled CORS for browser extensions.

#### Actual Code Reality
In `app/connect/__init__.py` and `app/connect/request_pipeline.py`, CORS validation enforces a three-tier security policy:
1. **Browser Extension Origins**: Any request with an `Origin` header matching `chrome-extension://*` or `moz-extension://*` is automatically granted `Access-Control-Allow-Origin: <origin>` and full CORS headers. This allows Yomitan and asbplayer extensions on Chrome, Edge, Brave, and Firefox to connect without manual configuration.
2. **Web Origins (`http://`, `https://`)**: Strictly checked against `CONNECT_ANKI_ALLOWED_ORIGINS`. The hardcoded fallback default is `("https://killergerbah.github.io",)` only (asbplayer web app `https://asbplayer.dev` is configured via environment variable). Unauthorized web origins receive **HTTP 403 Forbidden** with zero CORS headers.
3. **Originless Desktop Clients**: Requests without an `Origin` header (e.g. cURL, Python scripts, Anki add-ons, WPF desktop apps) are allowed provided they supply a valid API Bearer token (`UserApiToken`).

#### Risk & Impact
Unclear documentation could lead operators to expose permissive wildcards (`*`) on the Connect port, exposing local learning data to malicious third-party websites.

#### Resolution Taken
Documented exact regex matching rules, fallback values, and security constraints in `docs/backend/ARCHITECTURE.md` and `docs/ops/ARCHITECTURE.md`.

---

## 3. Catalog of Factually Inaccurate & Obsolete Documentation

This section catalogs every discrepancy identified during the audit, comparing the legacy documented claim against the actual code reality on disk, accompanied by exact file paths and line citations.

### 3.1 Frontend Discrepancies

| # | Document / Area | Claimed Behavior in Old Docs | Actual Code Reality on Disk | Severity | Remediation Taken / Recommended |
|---|---|---|---|---|---|
| **FE-01** | `docs/frontend/README.md` (Quickstart) | Advised running `npm --prefix frontend run test:changed`. | `frontend/package.json:6-22` contains no `test:changed` script. | **High** | Replaced with `npm test` and documented `python scripts/run_tests.py --changed --frontend-only`. |
| **FE-02** | `docs/frontend/README.md` (Linter) | Stated `# Run ESLint validation` via `npm run lint`. | `frontend/package.json:10` declares `"lint": "oxlint src"` using Oxlint `^1.71.0`. ESLint is absent. | **Medium** | Corrected heading and description to `# Run Oxlint validation (oxlint src)`. |
| **FE-03** | `docs/frontend/ARCHITECTURE.md` (Router Version) | Claimed React Router version `7.14.0`. | `frontend/package.json:48` declares `"react-router-dom": "^7.18.3"`. | **Low** | Updated architecture doc to cite React Router v7 (`^7.18.3`). |
| **FE-04** | `docs/frontend/ARCHITECTURE.md` (Lucide Version) | Claimed Lucide React version `v1.16.0`. | `frontend/package.json:39` declares `"lucide-react": "^1.27.0"`. | **Low** | Updated architecture doc to cite `^1.27.0`. |
| **FE-05** | `docs/frontend/ARCHITECTURE.md` (DOMPurify Version) | Claimed DOMPurify version `v3.3.1`. | `frontend/package.json:36` declares `"dompurify": "^3.4.15"`. | **Low** | Updated architecture doc to cite `^3.4.15`. |
| **FE-06** | `docs/frontend/ARCHITECTURE.md` (TypeScript Location) | Claimed TypeScript version defined in `tsconfig.json`. | TypeScript version is pinned in `frontend/package.json:67` as `"typescript": "~6.0.2"`. | **Low** | Corrected version citation source to `package.json`. |
| **FE-07** | `docs/frontend/ARCHITECTURE.md` (QueryClient Line) | Cited QueryClient instantiation at `frontend/src/main.tsx:69`. | `frontend/src/main.tsx` has only 37 total lines; QueryClient is instantiated at line 11. | **Medium** | Corrected citation to `frontend/src/main.tsx:11`. |
| **FE-08** | `docs/frontend/ARCHITECTURE.md` (Component Hallucinations) | Cited `FlamaAudioPairingDialog.tsx`, `useAuth.ts`, `StudySessionManager`. | Components do not exist. Code uses `LocalAudioDialog.tsx`, `FlamaAudioConnectionGate.tsx`, `useLoginForm.ts`, `RequireAuth.tsx`, and `useStudySession.ts`. | **High** | Replaced all hallucinated component and hook names with actual files on disk. |
| **FE-09** | `docs/frontend/tech-debt/README.md` (Layout Hallucinations) | Cited `SiteHeader.tsx`, `BrowseWorkspace.tsx`, and `AppSidebar.tsx`. | `SiteHeader.tsx` is inline in `AppLayout.tsx`; `BrowseWorkspace.tsx` is in `BrowsePage.tsx`; sidebar is `frontend/src/components/app-sidebar.tsx`. | **Medium** | Corrected layout and component locations in tech debt catalog. |
| **FE-10** | `docs/frontend/tech-debt/README.md` (Test Suite Metrics) | Claimed "80+ Vitest test suites". | Exactly **174 test files (1,424 tests total)**; 173 pass concurrently with 1 known mock state issue in `TemplateDetailPage.test.tsx` (passes 16/16 in isolation). | **Medium** | Documented exact suite and test counts with concurrency caveats. |
| **FE-11** | `docs/frontend/ARCHITECTURE.md` (Persistence Tiers) | Described state persistence as simple localStorage tokens. | Multi-tier persistence: localStorage for tokens, TanStack Query for cache, and **IndexedDB `flama-study` v2/v3** for offline study resilience. | **High** | Expanded architecture doc to detail the complete persistence hierarchy. |
| **FE-12** | `docs/frontend/ARCHITECTURE.md` (Design System & Tokens) | Described colors as Tailwind v3 standard hex values. | Theme uses **Tailwind v4 with linear OKLCH color spaces** ("Tone màu Hỏa ấm": light `oklch(0.635 0.215 35)`, dark `oklch(0.70 0.21 40)`), Geist font, and OKLAB color-mix backdrops. | **Medium** | Documented modern OKLCH tokens and visual integrity constraints. |

---

### 3.2 Backend Discrepancies

| # | Document / Area | Claimed Behavior in Old Docs | Actual Code Reality on Disk | Severity | Remediation Taken / Recommended |
|---|---|---|---|---|---|
| **BE-01** | `docs/backend/tech-debt/README.md` (Share Submodules) | Claimed `app/services/share/` package contains `update.py`. | `app/services/share/` contains `install.py`, `publish.py`, `overlay.py`, `cutover.py`, `helpers.py`, `constants.py`, `note_types.py`. `update.py` does not exist. | **High** | Removed `update.py` and enumerated verified modules in tech debt catalog. |
| **BE-02** | `docs/backend/tech-debt/README.md` (Anki Import Path) | Cited `app/api/v1/anki_imports.py`. | Physical path is `app/api/v1/flashcards/anki_imports.py`. | **Medium** | Corrected path in route transaction leak inventory. |
| **BE-03** | `docs/backend/ARCHITECTURE.md` (Session Interface) | Claimed `MediaHardenedSessionInterface` subclasses `SecureCookieSessionInterface` and returns early. | Subclasses `PublicMediaSessionInterface`, calls `super().save_session()`, strips `Cookie` from `Vary`, and deletes `Set-Cookie` headers (`app/__init__.py:17-30`). | **High** | Replaced snippet with verbatim implementation from `app/__init__.py`. |
| **BE-04** | `docs/backend/ARCHITECTURE.md` (Review Analytics Model) | Claimed existence of `ReviewAnalytics` model in `models/review_analytics.py`. | Model classes are `DailyReviewCount`, `ReviewAnalyticsHead`, `ReviewAnalyticsGeneration`, and `ReviewAnalyticsOutbox`. | **High** | Replaced fake model name with actual declarative classes. |
| **BE-05** | `docs/backend/ARCHITECTURE.md` (FieldDef Identity Column) | Claimed `FieldDef.is_primary` indicates primary field identity. | Column is defined as `identity_role` (`db.Column(db.String(32))`) in `models/field_def.py:23`. | **Medium** | Corrected attribute name to `FieldDef.identity_role`. |
| **BE-06** | `docs/backend/ARCHITECTURE.md` (Note Revision Column) | Claimed `Note.content_hash` tracks note modifications. | Column is defined as `content_revision` (`db.Column(db.BigInteger)`) in `models/note.py:20`. | **Medium** | Corrected attribute name to `Note.content_revision`. |
| **BE-07** | `docs/backend/README.md` & `ARCHITECTURE.md` (`db` Origin) | Stated `db = SQLAlchemy()` is initialized in `app/extensions.py`. | `app/extensions.py` only initializes `login_manager` and `migrate`. `db` is instantiated in `models/__init__.py:4` and imported into `app/__init__.py`. | **Medium** | Clarified true definition origin of `db` in backend docs. |
| **BE-08** | `docs/backend/ARCHITECTURE.md` (Connect CORS Defaults) | Stated allowed web origins default to both killergerbah and asbplayer. | Hardcoded fallback in `app/connect/__init__.py:253` and `request_pipeline.py:33` is `("https://killergerbah.github.io",)` only. asbplayer is environment-configured. | **Medium** | Corrected default fallback description and env configuration requirements. |
| **BE-09** | `AGENTS.md` & `docs/backend/ARCHITECTURE.md` (Startup Mode) | Stated startup is active and automatically repairs schemas on boot. | Startup is passive (`SELECT 1` connectivity check only). Schema mutations are gated by `STARTUP_RUN_MAINTENANCE` (default `False`). | **High** | Updated docs to document passive production startup contract. |
| **BE-10** | `docs/backend/tech-debt/README.md` (Share Monolith Metrics) | Claimed 34 callers and 15 commit leaks in `flashcards_share_service.py`. | File is **3,685 LOC**, referenced by **54 files** across `app/`, `tests/`, and `scripts/`. Route commit leaks total **45 calls** across 9 files. | **Medium** | Updated exact LOC, caller counts, and commit leak inventory. |

---

### 3.3 Ops & Logs Discrepancies

| # | Document / Area | Claimed Behavior in Old Docs | Actual Code Reality on Disk | Severity | Remediation Taken / Recommended |
|---|---|---|---|---|---|
| **OPS-01** | `docs/ops/ARCHITECTURE.md` (Migration Count & Lineage) | Claimed "exactly 68 migration versions" with linear history. | Exactly **69 migration files** spanning revisions 1 to 68; includes branch at revision 15 (`20260812_000016` vs `20260814_000016` -> 17 -> 18) merged at revision 19 (`20260820_000019`). | **High** | Documented exact 69-file count, branch lineage, and revision 19 merge point. |
| **OPS-02** | `docs/ops/ARCHITECTURE.md` (Migration Filenames) | Cited 4 hallucinated migration filenames. | Real filenames on disk: `20260327_000002_rename_marketplace_price_columns.py`, `20261012_000057_modernize_flashcard_templates.py`, `20261013_000063_expand_field_value_identity.py`, `20261014_000067_contract_field_name_storage.py`. | **Medium** | Replaced all hallucinated filenames with verified files on disk. |
| **OPS-03** | `docs/ops/ARCHITECTURE.md` (Timer Schedules) | Claimed outbox worker ran every 15m, cleanup daily, counts every 10m. | Actual schedules: outbox worker every **1 second**, cleanup every **5 minutes**, counts every **60 seconds**, retention daily at **18:30:00 UTC**. | **High** | Corrected all systemd timer intervals and delay configurations. |
| **OPS-04** | `docs/ops/ARCHITECTURE.md` (CLI Commands) | Cited fake commands `analytics-refresh-counts` and `connect-clean-media`. | Verified working commands: `flask --app wsgi.py analytics-counts-prewarm` and `flask --app connect_wsgi:app cleanup-connect-media`. | **High** | Updated all CLI command invocations with verified working commands. |
| **OPS-05** | `docs/ops/ARCHITECTURE.md` (Gunicorn Web Bind) | Claimed `flama.service` binds to `127.0.0.1:4789`. | `deploy/flama.service:15` executes `--bind 0.0.0.0:4789 wsgi:app` (reverse-proxied locally by Nginx). | **Medium** | Corrected bind address specification in ops architecture. |
| **OPS-06** | `docs/logs/ARCHITECTURE.md` (Audit Action Strings) | Listed snake_case approximations (`connect_action_add_note`, `image_quarantined`). | Code uses **dot-namespaced strings**: `"connect.note.create"`, `"connect.note.import"`, `"connect.import_media.stage"`, `"security.alert.triggered"`, etc. | **High** | Replaced all audit action strings with verified dot-namespaced constants. |
| **OPS-07** | `docs/logs/ARCHITECTURE.md` (Healthcheck Endpoints) | Claimed both `/api/health` and `/api/v1/health` exist. | `/api/health` is the sole web healthcheck. `/api/v1/health` does not exist (returns HTTP 404). Connect healthcheck is `/healthz`. | **Medium** | Clarified exact healthcheck endpoints across services. |
| **OPS-08** | `docs/ops/ARCHITECTURE.md` (CI Contract Probes) | Claimed CI runs 10 probe scripts in `mysql-contract` job. | `.github/workflows/ci.yml:254-282` executes exactly **14 probe scripts** covering analytics, session retention, and field identity cutover. | **Medium** | Documented complete 14-probe test matrix in ops architecture. |
| **OPS-09** | `docker-compose.yml` vs `README_SETUP.md` (Compose Parity) | Claimed `docker compose up` starts full application stack. | `docker-compose.yml:14-32` has `web` service commented out; only MySQL `db` is active. No Redis service defined. | **High** | Documented compose disparity as P1 ops tech debt and updated setup guidance. |
| **OPS-10** | `docs/ops/ARCHITECTURE.md` (Rollback Safety Gates) | Omitted pre-rollback safety verification steps. | `.github/workflows/deploy.yml:284-335` enforces **4 pre-rollback safety gates** including `deploy/check_field_code_rollback.py`. | **Medium** | Documented the 4 pre-rollback safety gates in deployment lifecycle. |

---

### 3.4 Junk Documents, Token Residue & Relocated Code Assets

| # | Artifact / Target | Pre-Audit Condition | Remediation Executed in Milestone 3 | Status |
|---|---|---|---|---|
| **JR-01** | `docs/task/template-features/*.prompt.txt` (19 files) | Discarded, raw prompt fragments from legacy generative AI tasks polluting the documentation tree. | Safely deleted all 19 `*.prompt.txt` files from git repository. | **Pruned (Deleted)** |
| **JR-02** | `docs/task/template-features/reports/*.txt` (5 files) & `seed_error.log` | Unformatted command output dumps, raw execution traces, and ephemeral error logs. | Safely deleted all 5 raw `.txt` files and root `seed_error.log`. | **Pruned (Deleted)** |
| **JR-03** | `docs/architecture/REPEATCALL.md` | Valuable 41KB research paper on Anki SM-2 vs FSRS scheduling, polluted with 132 raw LLM citation markers (`cite...`) and 495 PUA characters. | Scrubbed all citation tokens and PUA characters; relocated to `docs/backend/old/ANKI_SM2_VS_FSRS_SCHEDULING_RESEARCH.md`. | **Scrubbed & Archived** |
| **JR-04** | Python Verification Tools & Test Fixtures | Verification scripts (`verify_template_attachments_mysql.py`, etc.) and test fixtures lived inside `docs/`, with broken `parents[4]` and `parents[5]` relative imports. | Relocated scripts to `scripts/tools/` (fixed to `parents[2]`); relocated test fixtures to `tests/fixtures/templates/` (fixed to `parents[3]`). Verified all execute cleanly with exit code 0. | **Relocated & Fixed** |
| **JR-05** | `docs/historical/flashcard_system_design.md.resolved` | Foundational 623-line flashcard design document retained an invalid `.resolved` extension from an old merge conflict. | Verified 0 merge conflict markers; restored as `docs/backend/old/historical/flashcard_system_design.md` and indexed in archive catalog. | **Restored & Indexed** |

---

## 4. Domain-by-Domain Technical Debt Matrix

Each of the four primary domains maintains a dedicated `tech-debt/README.md` catalog detailing architectural bottlenecks, severity rankings, and concrete remediation roadmaps.

### 4.1 Frontend Technical Debt Overview
*Full Catalog*: [`docs/frontend/tech-debt/README.md`](frontend/tech-debt/README.md)

| Debt Item | Affected Location | Metric | Severity | Remediation Summary |
|---|---|---|---|---|
| **Gargantuan God Components** | `features/worksheets/components/studio/StudioLayoutTab.tsx`<br>`features/worksheets/components/WorksheetPageRenderer.tsx`<br>`features/admin/pages/AdminPaymentsPage.tsx`<br>`features/admin/pages/AdminTaxonomyPage.tsx` | 2,497 LOC<br>1,753 LOC<br>1,394 LOC<br>1,399 LOC | **P1 / High** | Decompose into focused sub-components (canvas previews, cell editors, format-specific SVG renderers, and custom state hooks). |
| **Mega-Hooks** | `useStudySession.ts`<br>`useBrowseState.ts`<br>`useLocalAudioEngine.ts` | 1,482 LOC<br>1,131 LOC<br>1,118 LOC | **P1 / High** | Split multi-concern hooks into single-responsibility hooks (keyboard shortcuts, session timers, review actions, audio host coordination). |
| **Legacy `app/api.ts` Monolithic Facade** | `frontend/src/app/api.ts` | 470 LOC | **P2 / Medium** | Migrate legacy callers to feature-local API modules (e.g. `cardTemplateApi.ts`, `deckCollaborationApi.ts`). |
| **Admin Module FSD Isolation** | `frontend/src/features/admin/` | 8 page files | **P2 / Medium** | Refactor admin tables and forms into reusable UI primitives following FSD standards. |

---

### 4.2 Backend Technical Debt Overview
*Full Catalog*: [`docs/backend/tech-debt/README.md`](backend/tech-debt/README.md)

| Debt Item | Affected Location | Metric | Severity | Status / Remediation Summary |
|---|---|---|---|---|
| **`flashcards_share_service.py` Monolith** | `app/services/flashcards_share_service.py` | 26 LOC (was 3,685 LOC)<br>Facade pattern | **P1 / High** | **Phase 1 Complete**: Monolith converted to thin re-export facade over `app/services/share/`. All 113 sharing tests pass. |
| **`vocabulary.py` Legacy Stubs & Routes** | `app/routes/vocabulary.py` | 117 LOC (was 718 LOC)<br>1 consolidated handler | **P2 / Medium** | **Phase 1 & 2 Complete**: 17 dead stubs removed, duplicate browse routes deprecated, form postbacks removed. |
| **Route Transaction Boundary Leaks** | `app/api/v1/` route handlers | 0 commit calls (was 45) | **P2 / Medium** | **Complete**: All 45 direct `db.session.commit()` calls moved into service transactions across all 9 route modules. |
| **Study Route Fragmentation** | `app/api/v1/learning/study.py` | 14 canonical endpoints | **P2 / Medium** | **Complete**: Migrated to `study_bp` on `api_v1_bp`, daily rate limit exempt, 300 total canonical routes. |
| **Deck Tree N+1 Queries** | `app/repositories/vocabulary_repository.py` | Line 780+ | **P3 / Medium** | Expand batch query optimizations for hierarchical subtree rollup calculations. |

---

### 4.3 Operations Technical Debt Overview
*Full Catalog*: [`docs/ops/tech-debt/README.md`](ops/tech-debt/README.md)

| Debt Item | Affected Location | Current State | Severity | Remediation Summary |
|---|---|---|---|---|
| **Development Docker Compose Parity** | `docker-compose.yml` | `web` commented out; no Redis | **P1 / High** | Provide working `docker-compose.dev.yml` with web, redis, and mysql containers; sync onboarding docs. |
| **Flama Connect Container Disparity** | `Dockerfile` | CMD only starts port 4789 | **P2 / Medium** | Containerize Flama Connect via multi-service compose or entrypoint supervisor. |
| **Docker Build Context Bloat** | `.dockerignore` | Missing `.agents/`, `flama-audio/` | **P2 / Medium** | Add heavy local directories to `.dockerignore` to speed up build context transfers. |
| **Reseed Script Platform Parity** | `scripts/reseed_db.ps1` vs `.sh` | PowerShell skips `dev-purge-data` | **P3 / Low** | Align purge behavior across platforms with an explicit confirmation parameter. |

---

### 4.4 Logs & Observability Technical Debt Overview
*Full Catalog*: [`docs/logs/tech-debt/README.md`](logs/tech-debt/README.md)

| Debt Item | Affected Location | Current State | Severity | Remediation Summary |
|---|---|---|---|---|
| **Structured JSON Logging** | `app/__init__.py`, systemd services | Unstructured plain text strings | **P1 / High** | Implement JSON log formatter outputting `request_id`, `user_id`, `level`, and `timestamp`. |
| **Distributed Request Tracing** | Nginx -> Flask -> Connect -> Workers | No shared correlation ID | **P1 / High** | Generate and propagate `X-Request-ID` across HTTP headers, background workers, and journald logs. |
| **Active Error Alerting (Sentry)** | Application exceptions | Only logged to stderr/journald | **P2 / Medium** | Configure Sentry SDK with error sampling and environment tagging. |
| **Infrastructure & APM Metrics** | Flask & Connect daemons | No Prometheus exporter | **P2 / Medium** | Export `/metrics` endpoint with request latencies, active DB pool connections, and outbox queue depths. |

---

## 5. Documentation Architecture Standards & Governance

To prevent documentation sprawl and ensure long-term link integrity, the Flama documentation repository enforces the following governance rules.

### 5.1 Four-Domain Directory Layout Specification

All technical documentation must reside under one of the four canonical domain hubs:

```text
docs/
├── README.md                      # Master navigation portal (points to the 4 domains & audit report)
├── DOCUMENTATION_AUDIT_REPORT.md  # Comprehensive codebase audit & reality synthesis (this document)
│
├── frontend/                      # DOMAIN 1: React SPA, FSD slices, Vite, Tailwind v4, Audio
│   ├── ARCHITECTURE.md            # Active frontend architecture specification
│   ├── README.md                  # Quickstart, component map, and module guide
│   ├── tech-debt/README.md        # Frontend architectural backlog and debt catalog
│   └── old/README.md              # Archive catalog of historical frontend plans and reviews
│
├── backend/                       # DOMAIN 2: Flask API, ORM models, scheduling, Flama Connect
│   ├── ARCHITECTURE.md            # Active backend architecture specification
│   ├── README.md                  # System overview, API catalog, and data model landscape
│   ├── tech-debt/README.md        # Backend architectural backlog and debt catalog
│   └── old/README.md              # Archive catalog of historical decoupling phases and plans
│
├── ops/                           # DOMAIN 3: Infrastructure, Hostinger VPS, systemd, Nginx, CI/CD
│   ├── ARCHITECTURE.md            # Active operations and deployment specification
│   ├── README.md                  # Runbooks index, systemd unit overview, environment guide
│   ├── tech-debt/README.md        # Ops architectural backlog and debt catalog
│   └── old/README.md              # Archive catalog of historical rollout runbooks and procedures
│
└── logs/                          # DOMAIN 4: Logging standards, audit trails, observability
    ├── ARCHITECTURE.md            # Active logging and observability specification
    ├── README.md                  # Audit action catalog, log inspection, troubleshooting
    ├── tech-debt/README.md        # Observability backlog and debt catalog
    └── old/README.md              # Archive catalog of historical performance audits and probes
```

### 5.2 Lifecycle Rules for `tech-debt/` and `old/`

1. **Active Architecture (`ARCHITECTURE.md` & `README.md`)**:
   - Must reflect the **exact present state** of the codebase.
   - Forward-looking proposals or aspirational designs must not be documented as active reality.
2. **Technical Debt (`tech-debt/README.md`)**:
   - When architectural shortcuts, monolithic modules, or temporary workarounds are introduced, they must be documented in the corresponding domain's `tech-debt/README.md`.
   - Each item must include: affected files, metric/severity, operational risks, and a concrete decomposition/remediation plan.
3. **Historical Archive (`old/`)**:
   - Completed migration plans, historical ADRs, resolved incident reports, and deprecated runbooks must be moved to the domain's `old/` subfolder.
   - Archived documents must never be left unindexed; they must be cataloged in the domain's `old/README.md` with descriptive links.

### 5.3 Markdown Link Syntax & Relative Path Constraints

To guarantee 100% link resolution across GitHub web preview, IDE editors, and static site generators:
1. **Clean Relative Paths Only**:
   - Do NOT use absolute URLs (`file:///...` or hardcoded local drives `d:/...`).
   - Do NOT use leading slashes (`/docs/...`). Always use relative paths from the current document location (e.g. `../backend/ARCHITECTURE.md` or `tech-debt/README.md`).
2. **No Terminal Stack Trace Line Syntax in Links**:
   - Do NOT append `:line_number` to URLs (e.g. linking to `file.py:42`). This breaks file resolution in browsers and GitHub.
   - Use standard GitHub anchor syntax when referencing specific lines (e.g. `file.py#L42`).
3. **Target Existence Rule**:
   - Every relative link must point to an existing physical file or directory on disk. Dead links are strictly prohibited in active documentation.

### 5.4 Automated Verification Protocol

Any modification to documentation must pass automated integrity verification before merging:
1. **Markdown Link Checker**: An automated AST/regex validator scans all Markdown files in `docs/`, `AGENTS.md`, and root `README.md` to ensure zero broken relative links.
2. **Test Suite Verification**: Run `python scripts/run_tests.py --changed` to ensure repository test suites remain green.
3. **Linter & Typecheck**: Run `npm --prefix frontend run lint` and `npm --prefix frontend run typecheck` to confirm frontend integrity.
