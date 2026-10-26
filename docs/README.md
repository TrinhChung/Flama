# Flama Technical Documentation Portal

Welcome to the central documentation portal for **Flama** (Nihongo Flashcard Learning Platform). This repository contains technical architecture guides, API specifications, operational runbooks, and debt catalogs across all subsystems.

---

## 🏛️ Master Architecture & Codebase Reality Audit

- [MCP NoteType and template workflow](backend/MCP_AUTHORING_WORKFLOW.md): capability review, reusable template tools, typed fields/inputs, creation sequence, preview diagnostics and deferred array work.
- [MCP template authoring implementation](plans/MCP_TEMPLATE_AUTHORING_IMPLEMENTATION_PLAN_2026-10-25.md): #248/#116 candidate diagnostics, Study artifacts, browser fixtures and MCP App packaging; includes local verification and host rollout limits.
- [Publish scope and release UX proposal](plans/PUBLISH_SCOPE_AND_RELEASE_UX_IMPLEMENTATION_PLAN_2026-10-25.md): proposed Deck, Note Type and Template publication boundaries, review flows and acceptance checks; implementation remains pending.
- [Browse data and performance review](architecture/BROWSE_PERFORMANCE_DATA_REVIEW_2026-10-24.md): table/query inventory, historical over-fetch fixes, current bottlenecks and read-only local MySQL measurements. [Task breakdown](plans/BROWSE_PERFORMANCE_TASKS_2026-10-24.md) explains rationale, historical constraints, trade-offs and acceptance criteria; [technical-debt phase](architecture/BROWSE_TECH_DEBT_IMPLEMENTATION_2026-10-24.md) records the baseline tooling and local deck-name ordering fix.
- [Deck, Note Type and Template stability](architecture/deck-notetype-template-stability-design.md): immutable releases, pinned presentation, receipt parity, asynchronous subscriber delivery and rollout checks.
- [Marketplace bundle completeness review](architecture/marketplace-bundle-completeness-review-2026-10-21.md): five findings fixed and verified locally, with test evidence and production limits.
- [Marketplace local rollout rehearsal](runbooks/MARKETPLACE_BUNDLE_LOCAL_ROLLOUT_20261021.md): reviewed publication plans, local results, verification and rollback.
- [Test architecture P0 review](architecture/TEST_ARCHITECTURE_RFC.md): SPA contract checked in the frontend job, parked harness prototype and remaining MySQL rollout gates. Follow-up: [CI/CD test upgrade plan](plans/TEST_CICD_UPGRADE_IMPLEMENTATION_PLAN_2026-10-23.md).

| Master Report | Description |
|---|---|
| [**`DOCUMENTATION_AUDIT_REPORT.md`**](DOCUMENTATION_AUDIT_REPORT.md) | **Authoritative Codebase Reality & Documentation Audit Report**: Exhaustive analysis of legacy documentation inaccuracies, underspecified areas, factual discrepancies catalog across Frontend/Backend/Ops/Logs, technical debt matrix, and documentation governance. |
| [Shared skill audit and review](architecture/MULTI_AGENT_SKILLS_AUDIT_AND_UNIFICATION.md) | Source inventory, Codex review, shared-skill synchronization and missing export queue. |
| [Frontend FSD proposal and review](architecture/FLAMA_FRONTEND_FSD_CONSOLIDATION_AND_AGENT_ALIGNMENT_PROPOSAL.md) | Proposed migration, corrections required before implementation, and reviewer status. |
| [Claude Code independent review](architecture/MULTI_AGENT_SKILLS_REVIEW_CLAUDE_CODE_2026-10-20.md) | Conditional sign-off, local development skill contribution and remaining integration findings. |

---

## 🧭 Four Core Engineering Domains

The Flama technical documentation is structured into four primary engineering domains. Each domain contains an active architecture guide, a technical debt backlog, and a preserved historical archive:

```text
docs/
├── frontend/  ── UI SPA, React 19, Vite, Tailwind v4, Audio Companion, i18n
├── backend/   ── Flask REST Monolith, SQLAlchemy Models, Scheduling, Flama Connect
├── ops/       ── Hostinger VPS Topology, Systemd Units, Quiesced Migrations, CI/CD
└── logs/      ── 12-Factor Journald Streams, MySQL Audit Trails, Healthchecks
```

### 1. [Frontend Domain (`docs/frontend/`)](frontend/)
*Client-side Single Page Application architecture, component hierarchy, state persistence, and design system.*

- [**Frontend Architecture Guide**](frontend/ARCHITECTURE.md): Comprehensive overview of React 19, Vite 8, Tailwind v4 OKLCH fire palette, Feature-Sliced Design (25 feature slices, 2 entities, 30 shadcn UI primitives, 10 shared primitives), client-side renderer, and IndexedDB v2/v3 offline persistence.
- [**Frontend Hub & Component Map**](frontend/README.md): Quickstart guide, Oxlint/Vitest validation, directory map, and routing structure.
- [**Frontend Technical Debt Catalog**](frontend/tech-debt/README.md): Active inventory of 10 gargantuan components (>800 LOC), 3 mega-hooks (`useStudySession.ts`, `useBrowseState.ts`, `useLocalAudioEngine.ts`), and legacy `app/api.ts` facade.
- [**Frontend Historical Archive**](frontend/old/README.md): Preserved specifications including [Card Template Sandbox Renderer](frontend/old/CARD_TEMPLATE_SANDBOX_RENDERER.md), [Typography System](frontend/old/TYPOGRAPHY_SYSTEM.md), and [Frontend Architecture Selection Research](frontend/old/FRONTEND_ARCHITECTURE_SELECTION_RESEARCH.md).

---

### 2. [Backend Domain (`docs/backend/`)](backend/)
*Application factory, canonical REST APIs under `/api`, 102 SQLAlchemy models, Anki scheduling, and Flama Connect.*

- [**Backend Architecture Guide**](backend/ARCHITECTURE.md): Comprehensive overview of Flask factory in `app/__init__.py`, passive production startup (`SELECT 1`), canonical REST blueprints, derived SQL `Card` view (ADR P11), `StudyProgressSubject` (ADR P10), overlay-only Marketplace clone model, and Flama Connect Yomitan adapter (port 4790).
- [**Backend Hub & System Landscape**](backend/README.md): System architecture overview, dependency graph, entry points (`wsgi.py`, `connect_wsgi.py`), and persistence map.
- [**Backend Technical Debt Catalog**](backend/tech-debt/README.md): Active inventory of the 3,685-LOC `flashcards_share_service.py` monolith (54 callers), `vocabulary.py` legacy 410 stubs, and 45 route-level `db.session.commit()` transaction leaks.
- [**Backend Historical Archive**](backend/old/README.md): Preserved archive of historical designs and completed plans:
  - [Clone Cutover Report](backend/old/completed-plans/CLONE_CUTOVER_REPORT.md): Cutover to overlay-only shared deck model.
  - [Deck Change Request Simple Plan](backend/old/completed-plans/DECK_CHANGE_REQUEST_SIMPLE_PLAN.md): Collaboration and conflict resolution engine.
  - [payOS Payment Architecture](backend/old/FLAMA_PAYMENT_ARCHITECTURE.md): Orders, payment attempts, and webhook processing.
  - [Anki SM-2 vs FSRS Research](backend/old/ANKI_SM2_VS_FSRS_SCHEDULING_RESEARCH.md): Deep algorithm analysis (cleaned of citation tokens).
  - [Foundational Flashcard Design](backend/old/historical/flashcard_system_design.md): Restored initial flashcard architecture (623 lines).
  - [Decoupling Phase ADRs](backend/old/decoupling-phases/): Completed historical ADRs (Phases 0–10).

---

### 3. [Operations & Infrastructure Domain (`docs/ops/`)](ops/)
*Production VPS topology, systemd isolation, quiesced migrations, Docker, and CI/CD pipelines.*

- [**Operations Architecture Guide**](ops/ARCHITECTURE.md): Comprehensive overview of Hostinger Ubuntu VPS deployment, 3 continuous systemd daemons, 4 lock-guarded high-frequency systemd timers, Nginx reverse proxy with `X-Accel-Redirect` media streaming, quiesced database migration workflow, 4 rollback safety gates, and 14 CI contract probes.
- [**Operations Hub & Deployment Map**](ops/README.md): Runbooks index, directory tree, deployment prerequisites, and environment variable schema.
- [**Operations Technical Debt Catalog**](ops/tech-debt/README.md): Parity backlog covering local development `docker-compose.yml` (`web` service commented out), Flama Connect containerization, and `.dockerignore` context optimizations.
- [**Operations Historical Archive**](ops/old/README.md): Preserved operational runbooks including [Flama Audio Windows Release](ops/old/FLAMA_AUDIO_WINDOWS_RELEASE.md), [Flama Connect asbplayer Setup](ops/old/FLAMA_CONNECT_ASBPLAYER.md), and [Database Progress Scalability Rollout](ops/old/DATABASE_PROGRESS_SCALABILITY_ROLLOUT.md).

---

### 4. [Logs & Observability Domain (`docs/logs/`)](logs/)
*Standard stream logging, systemd journal capture, MySQL business audit trails, and health monitoring.*

- [**Logs & Observability Architecture Guide**](logs/ARCHITECTURE.md): Comprehensive overview of 12-factor stdout/stderr streams to `systemd-journald`, dot-namespaced audit actions in MySQL (`AuditLog`, `UserPermissionAuditLog`), security event tracking, and healthcheck endpoints (`/api/health` on 4789, `/healthz` on 4790).
- [**Logs Hub & Action Catalog**](logs/README.md): Quick inspection commands, dot-namespaced audit action table, and SQL incident query snippets.
- [**Logs Technical Debt Catalog**](logs/tech-debt/README.md): Observability roadmap covering structured JSON logging, distributed `X-Request-ID` correlation tracing, Sentry alert integration, and Prometheus metrics.
- [**Logs Historical Archive**](logs/old/README.md): Preserved historical audit reports, performance probes, and incident reviews.

---

## 🛠️ Operational Runbooks & Guides

Active guides and runbooks supporting development, database maintenance, and integrations:

| Category | Guide / Runbook | Description |
|---|---|---|
| **Database & Seeding** | [**`SEEDING_GUIDE.md`**](guides/SEEDING_GUIDE.md) | Comprehensive database seeding guide (reseed workflows, CLI commands, seed data). |
| **Templates & Note Types** | [**`NOTE_TYPE_TEMPLATE_GUIDE.md`**](guides/NOTE_TYPE_TEMPLATE_GUIDE.md) | Syntax and configuration guide for Note Types and Card Templates. |
| **Flashcard V2** | [**`FLASHCARD_V2_RUNBOOK.md`**](runbooks/FLASHCARD_V2_RUNBOOK.md) | Active operational runbook for flashcard note creation, templates, and media handling. |
| **Content Import** | [**`CHUNGBECH_IMPORT_GUIDE.md`**](runbooks/CHUNGBECH_IMPORT_GUIDE.md) | Procedure for importing ChungBech N1 vocabulary TSV files. |
| **Database Architecture** | [**`DATABASE_ARCHITECTURE.md`**](skills/DATABASE_ARCHITECTURE.md) | Flama database review checklist, entity boundaries, and 5-phase zero-downtime migration methodology. |
| **Git & Workflow** | [**`BRANCH_STRATEGY.md`**](skills/BRANCH_STRATEGY.md) | Multi-agent git branching strategy and isolated workspace policies. |
| **SEO & Entity** | [**`BRAND_ENTITY_SEO_STRATEGY.md`**](seo/BRAND_ENTITY_SEO_STRATEGY.md) | Brand defense, Schema.org JSON-LD, and search engine optimization strategy. |
| **SEO Matrix** | [**`KEYWORD_RESEARCH_MATRIX.md`**](seo/KEYWORD_RESEARCH_MATRIX.md) | Search intent mapping and keyword clustering matrix. |

---

## 📋 Documentation Standards & Governance

For standards governing new documentation, archiving obsolete files to `old/`, logging technical debt to `tech-debt/`, and markdown link syntax rules, see **Section 5: Documentation Architecture Standards & Governance** in the [Documentation Audit Report](DOCUMENTATION_AUDIT_REPORT.md#5-documentation-architecture-standards--governance).
