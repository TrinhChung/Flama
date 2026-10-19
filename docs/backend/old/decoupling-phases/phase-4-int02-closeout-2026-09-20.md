# Phase 4 / INT-02 integration closeout — 2026-09-20

> Decision: **Phase 4 COMPLETE for pre-release development; INT-02 CLOSED**
>
> Code baseline: `develop` at `263b65e`. This document and the accompanying tracker updates are uncommitted documentation changes.
>
> Authority: `CardProgress` remains the sole operational progress read/write source. Phase 4 learner/Note tables are derived shadow storage; all three shadow flags default off. No production flag enablement, Note authority cutover, data copy or schema contraction occurred during this closeout.
>
> Scope limit: [P4-11 was accepted only as a pre-release development dependency](./phase-4-p4-11-pre-release-closeout-2026-09-20.md). Its deferred production load/fault/limit work is **not passed** and remains a mandatory production-enablement/P5-09 gate.

## Exit decision

The P4-00 frozen-session correction, P4-01 preflight, P4-02..P4-05 accepted data contracts, P4-06 additive schema/mapper, P4-07/P4-08 atomic writer/lifecycle mirrors, P4-09 resumable backfill, P4-10 read-only reconciliation and risk-scoped P4-11 development rehearsal are accounted for in the [task tracker](../task/decoupling/README.md). This INT-02 run rechecked the combined suite and a disposable local MySQL rehearsal. With no newly observed unexplained difference or product-authority change, Phase 4's **development implementation** is closed. It is not a production rollout approval.

| Gate | Result | Evidence / limit |
|---|---|---|
| P4-00..P4-05 entry and contracts | PASS from accepted task/ADR records | [Phase 4 execution plan](../task/decoupling/P4_EXECUTION_PLAN_2026-09-10.md); no new contract revision in this closeout |
| P4-06 additive migration and flag-off boot | PASS on disposable local and prior isolated VPS MySQL | [P4-11 rehearsal](./phase-4-reconciliation-rollout-rehearsal-2026-09-20.md); no live production migration in this run |
| P4-07/P4-08 writers, lifecycle, overlay | PASS in focused and full regression suites; prior MySQL probes | Native/session/worker, Connect import/snapshot/revlog, reset/delete and clone cutover tests; installed-source/local scope tests retain overlay-only behavior |
| P4-09 bounded backfill | PASS in focused/full suites and fresh disposable MySQL run | Fresh 1,002-row local probe: 11 batches, 24.474 seconds, resumable/race behavior previously verified separately |
| P4-10 reconciliation | PASS | Fresh local two-run SELECT-only audit: identical checksums, zero unexplained differences; prior local 16,424-row and VPS small-cohort evidence retained |
| P4-11 pre-release gate | ACCEPTED WITH EXPLICIT DEFERRALS | [Decision record](./phase-4-p4-11-pre-release-closeout-2026-09-20.md); not a pass for representative production load/fault thresholds |
| INT-02 code/integration gate | PASS | Commands and boundary review below; no Phase 5 authority code or production enablement |

## Fresh verification in this closeout

| Command / check | Result |
|---|---|
| `.\.venv\Scripts\python.exe scripts/run_tests.py --module study,connect_mcp,decks,flashcards,database,cli --backend-only` | PASS, 86 backend test files (409.23 s). Expected negative-path logs and deprecation warnings did not fail the runner. |
| `.\.venv\Scripts\python.exe scripts/run_tests.py --module study --frontend-only` | PASS, 179 tests / 22 files. |
| `npm --prefix frontend run typecheck` | PASS. |
| `npm --prefix frontend run lint` | PASS, warnings only in existing unrelated frontend files. |
| `.\.venv\Scripts\python.exe scripts/run_tests.py --changed` | PASS with **no tests selected**: working-tree changes were documentation only. This is not substituted for the full suite. |
| `.\.venv\Scripts\python.exe scripts/run_tests.py --all` | PASS: 1,267 backend tests (2 skipped) across 131 files; 437 frontend tests across 66 files; runner exit 0 (569.34 s). |
| `.\.venv\Scripts\python.exe scripts/probe_phase4_reconciliation_mysql.py --schema-snapshot-baseline --rollout-rehearsal --extra-rows 1000` | PASS on local MySQL 8.0.40 / `utf8mb4_0900_ai_ci`: migration 38→39/downgrade/re-upgrade, 98-table synthetic backup/restore checksum, flags-off `wsgi.py` before/after restart, 1,002 source rows, 11 backfill batches, two identical SELECT-only audit reports, zero unexplained differences, indexed plans. Disposable databases and SELECT-only principal removed. |
| `git diff --check` | PASS; Git emitted only local LF→CRLF notices. |

The fresh probe's local timings and one-learner/deck synthetic scope are **not** production throughput or topology evidence. Prior isolated VPS MySQL 8.0.46 probes used 12 synthetic progress rows and did not copy application rows. The last recorded production read-only Alembic head was `20260913_000039`; it was not refreshed in this closeout.

## Boundary findings

### Operational authority remains Card-shaped

- **Observed:** `app/repositories/study_repository.py` and active study services continue to use `CardProgress`; `app/settings.py` defaults shadow write, compare and backfill to `False`. Searches found no `StudyProgressSubject`, `StudyProgressState`, `StudyProgressAvailability` or `StudyProgressContributor` usage in `app/api/`, `app/routes/` or `frontend/src/`.
- **Evidence:** current `develop` at `263b65e`; [P4-10 rehearsal](./phase-4-reconciliation-rollout-rehearsal-2026-09-20.md); focused and full suites above.
- **Potential concern:** an undocumented product read from shadow would create an implicit second authority.
- **Impact:** due/order/state drift or stale user-visible progress before Phase 5 cutover.
- **Unknowns:** no fresh production traffic/profile or per-environment flag inspection was performed in this documentation-only integration run. Production flag status must be checked before any later deployment action.

### Mirror transaction ownership and lifecycle

- **Observed:** native/session/worker/Connect writers call the shadow mirror as part of their existing mutation path. The mirror, lifecycle and reconciliation service files contain no independent `commit()`/`rollback()` calls; bounded backfill owns its separate CLI batch transactions. Reconciliation is not a product reader. Full tests include flag-on/off, writer, clone overlay, lifecycle and negative fault paths.
- **Evidence:** `app/services/study_progress_shadow_mirror_service.py`, `study_progress_lifecycle_mirror_service.py`, `study_progress_reconciliation_service.py`, `study_progress_backfill_service.py`; [P4-09 verification](./phase-4-resumable-backfill-verification-2026-09-14.md); test results above.
- **Potential concern:** production-only concurrency, rekey/backfill and worker/DLQ faults could still produce an untrusted shadow after enablement.
- **Impact:** an incomplete derived state might contaminate a later authority cutover if enrolled without full reconciliation.
- **Unknowns:** the [P4-11 deferral matrix](./phase-4-p4-11-pre-release-closeout-2026-09-20.md) remains open until controlled synthetic, production-version MySQL rehearsal and measured limits at P5-09.

## Residual gates and handoff

1. **GO for Phase 5 development handoff** after this INT-02 closeout: start with [P5-00 inventory and P5-01 ADR](../task/decoupling/P5_EXECUTION_PLAN_2026-09-20.md), using fresh read-only production data if needed. Phase 5's exact DDL/wire/lock policy remains draft, not approved by this Phase 4 report.
2. **NO-GO for production Phase 4 shadow enablement or NOTE authority enrollment** until the deferred P4-11 production-version synthetic multi-user/overlay load, complete fault matrix, metadata-lock/storage/latency limits and rollback plan are discharged at P5-09 (or an equivalent separately reviewed gate). No minimum real-user count is required.
3. Any unexplained reconciliation difference, failed atomicity, source-Note mutation in installed clone flows, or missing rollback evidence reopens the affected gate. Do not remove `CardProgress` or the additive shadow schema; operational fallback remains flags off with `CardProgress` serving reads/writes.

**Closeout verdict:** Phase 4/INT-02 complete for the current pre-release development milestone, with the production-enablement exception explicit and carried into Phase 5. No commit, merge or deployment is implied.
