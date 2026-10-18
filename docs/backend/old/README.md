# Archived Backend Documentation

This directory (`docs/backend/old/`) serves as the historical archive for retired backend architecture documentation, decoupling ADRs, completed engineering plans, performance investigations, and legacy task specifications.

---

## Purpose & Archival Policy

1. **Preservation of Context**: Documents placed here preserve historical rationale, algorithm research, and migration milestones without confusing the active codebase state.
2. **Read-Only Reference**: Files in this directory are preserved for archival and reference purposes only. They do not represent the current state of the Flama Flask backend or ORM models.
3. **Active Ground Truth**: For current backend architecture, data models, and services, refer to:
   - [**`docs/backend/ARCHITECTURE.md`**](../ARCHITECTURE.md) — Authoritative Flask factory, REST APIs, ORM models, scheduling, and companion services.
   - [**`docs/backend/README.md`**](../README.md) — Backend navigation hub, data flow, and module catalog.
   - [**`docs/backend/tech-debt/README.md`**](../tech-debt/README.md) — Backend technical debt, performance hotspots, and pending unifications.

---

## Archive Index

### Algorithmic Research & Architecture Specifications

| Document | Original Location | Description |
|---|---|---|
| [**`ANKI_SM2_VS_FSRS_SCHEDULING_RESEARCH.md`**](ANKI_SM2_VS_FSRS_SCHEDULING_RESEARCH.md) | `docs/architecture/REPEATCALL.md` | Deep research paper comparing Anki SM-2 vs FSRS scheduling algorithms, interval formulas, day boundaries, and fuzzing (cleaned of raw LLM citation tokens). |
| [**`CLAUDE_MCP_CONNECTOR_INVESTIGATION.md`**](CLAUDE_MCP_CONNECTOR_INVESTIGATION.md) | `docs/task/Tri/CLAUDE_MCP_CONNECTOR_INVESTIGATION.md` | Investigation and feasibility assessment for Claude Desktop Model Context Protocol (MCP) integration. |
| [**`FLAMA_MCP_CONNECT.md`**](FLAMA_MCP_CONNECT.md) | `docs/architecture/FLAMA_MCP_CONNECT.md` | Initial architecture and protocol specification for Flama MCP and Connect service bridging. |
| [**`FLAMA_PAYMENT_ARCHITECTURE.md`**](FLAMA_PAYMENT_ARCHITECTURE.md) | `docs/architecture/FLAMA_PAYMENT_ARCHITECTURE.md` | Original architecture document for payOS payment gateway integration, webhooks, and order lifecycle. |

### Decoupling Phases (25 Architecture Decision Records)

The [**`decoupling-phases/`**](decoupling-phases/) directory houses all completed Architecture Decision Records (ADRs) executed during the study engine and progress authority decoupling:

| ADR File | Phase & Focus |
|---|---|
| `phase-4-entry-investigation-2026-09-09.md` | Phase 4 entry criteria and baseline audit |
| `phase-4-current-state-preflight-2026-09-10.md` | Phase 4 current-state preflight inspection |
| `phase-4-progress-identity-fanin-revision-adr-2026-09-10.md` | Learner progress identity and fan-in revision |
| `phase-4-algorithm-state-availability-adr-2026-09-12.md` | Exact algorithm state availability and codecs |
| `phase-4-history-provenance-lifecycle-adr-2026-09-12.md` | Review history provenance and lifecycle retention fence |
| `phase-4-logical-contract-joint-acceptance-2026-09-13.md` | Joint acceptance for logical contracts P4-02..P4-04 |
| `phase-4-physical-shadow-schema-adr-2026-09-13.md` | Additive physical shadow schema architecture |
| `phase-4-schema-drift-remediation-2026-09-13.md` | Batch-table migration and safe schema convergence |
| `phase-4-additive-schema-mapper-verification-2026-09-13.md` | Additive schema mapper verification evidence |
| `phase-4-native-session-worker-mirror-verification-2026-09-13.md` | Same-transaction native/session/worker mirror verification |
| `phase-4-external-lifecycle-mirror-verification-2026-09-14.md` | External snapshot, import, and delete mirror verification |
| `phase-4-resumable-backfill-verification-2026-09-14.md` | Resumable keyset backfill verification evidence |
| `phase-4-reconciliation-rollout-rehearsal-2026-09-20.md` | Reconciliation rollout rehearsal on local/VPS cohorts |
| `phase-4-p4-11-pre-release-closeout-2026-09-20.md` | Pre-release closeout for Phase 4 |
| `phase-4-int02-closeout-2026-09-20.md` | INT-02 closeout record and P5 handoff |
| `phase-5-p5-00-inventory-2026-09-21.md` | Phase 5 code/schema inventory |
| `phase-5-authority-cutover-design-2026-09-20.md` | Phase 5 authority cutover architectural design |
| `phase-5-authority-fence-adr-2026-09-21.md` | Additive LEGACY-only authority fence decision |
| `phase-5-p5-03-legacy-projection-contract-2026-09-21.md` | Inert lossless encoder/comparator contract |
| `phase-5-p5-04-canonical-command-2026-09-21.md` | Canonical command fence across direct/session/worker |
| `phase-5-p5-05-authority-receipt-contract-2026-09-21.md` | Authority receipt verification contract |
| `phase-5-p5-05-session-v4-contract-2026-09-22.md` | Study Session v4 and direct NOTE writer contract |
| `phase-9-contraction-investigation-2026-09-30.md` | Phase 9 schema contraction investigation |
| `phase-9-p9-03-projection-independent-note-adr-2026-09-30.md` | Projection-independent Note authority ADR |
| `phase-10-consolidated-note-progress-adr-2026-10-03.md` | Consolidated note progress schema transition ADR |

### Historical Subdirectories & Packages

| Directory | Original Location | Description |
|---|---|---|
| [**`completed-plans/`**](completed-plans/) | `docs/plans/completed/` | Completed technical execution plans including `CLONE_CUTOVER_REPORT.md`, `DECK_CHANGE_REQUEST_SIMPLE_PLAN.md`, `REST_API_MIGRATION_PLAN.md`, `LEGACY_SCHEMA_MIGRATION_PLAN.md`, `SCHEDULER_FIX_DOCUMENTATION.md`, and `FLAMA_AUDIO_MVP_IMPLEMENTATION_PLAN.md`. |
| [**`completed-tasks/`**](completed-tasks/) | `docs/tasks/completed/` | 14 completed engineering task specifications covering secure image ingestion, Google OAuth login, worksheet PDF generation, transactional email delivery, and student verification. |
| [**`decoupling/`**](decoupling/) | `docs/task/decoupling/` | Planning documents and execution backlog for the Study Decoupling initiative (`P5_EXECUTION_PLAN_2026-09-20.md`, `P5_EXECUTIVE_BRIEF_2026-09-21.md`, and completed sub-tasks). |
| [**`historical/`**](historical/) | `docs/historical/` | Foundational flashcard system architecture ([**`flashcard_system_design.md`**](historical/flashcard_system_design.md)), early architectural reviews, and refactoring plans (`FLAMA_ARCHITECTURE_REVIEW.md`, `FLAMA_POST_REFACTOR_REVIEW.md`, `FLAMA_REFACTOR_PLAN.md`, `FLAMA_PAYMENT_DOMAIN_EXPANSION_PLAN.md`, and `SECURITY_ASSESSMENT_2026-04-06.md`). |
| [**`investigations/`**](investigations/) | `docs/investigations/` | Deep technical investigations including [**`PUBLISH_DECK_LOAD_PERFORMANCE_REPORT.md`**](investigations/PUBLISH_DECK_LOAD_PERFORMANCE_REPORT.md) (RCA and $O(1)$ query optimization for marketplace publish options). |
| [**`artifacts/`**](artifacts/) | `docs/architecture/artifacts/` | Benchmark logs, SQL execution snapshots, and legacy performance audit data. |
