# P4-11 pre-release closeout — risk-scoped acceptance

> Date: 2026-09-20 | Decision: **P4-11 CLOSED FOR PRE-RELEASE DEVELOPMENT ONLY**
>
> Basis: product owner directed that the application is not yet publicly released and its small user population must not block decoupling on a production-traffic-volume criterion. This deployment premise is owner-provided, not independently measured here.
>
> This is an explicit narrowing of the original P4-11 acceptance, **not** a claim that the full production-load or failure matrix passed. `INT-02` was open at this decision and [subsequently closed for development](./phase-4-int02-closeout-2026-09-20.md). No production flag enablement, Note authority cutover, or production data write is approved by this decision.

## Observed evidence supporting the narrowed gate

The [rehearsal evidence](./phase-4-reconciliation-rollout-rehearsal-2026-09-20.md) is the measured source. Its 16,424-row local synthetic run (matching the earlier observed source-row count and queue histogram, but only one learner/deck) completed 165 bounded backfill batches, two identical SELECT-only audits with zero unexplained differences, indexed lookup checks, migration round-trip, synthetic backup/restore checksum and flags-off restarts. The local engine was MySQL 8.0.40 with a different default collation from the VPS.

An isolated database on the VPS MySQL 8.0.46, with the application database's default collation and SQL mode, passed migration 38→39 round-trip, synthetic backup/restore checksum, flags-off `wsgi.py` restarts, backfill, two SELECT-only reconciliations and indexed lookup checks on 12 synthetic progress rows. Four more disposable VPS probes passed schema/codec/duplicate-key savepoint, bounded backfill/resume and create/reset/delete races, native fan-in/mirror-fault/lock-timeout atomicity, and external lifecycle/native–external race. The live application database was read-only during these probes; its head was last observed at `20260913_000039`. It was not rechecked for this decision.

The recorded focused integration run passed 948 backend tests, 179 Study frontend tests, frontend typecheck and lint with existing warnings. In the current code, all three `STUDY_PROGRESS_SHADOW_*` flags still default to `False` in `app/settings.py`. `CardProgress` remains product read/write authority; the Phase 4 tables are derived shadow storage.

## Explicit exceptions and where they move

| Original P4-11 target not demonstrated | Decision at this pre-release gate | Mandatory later gate |
|---|---|---|
| Production-version **representative multi-user/overlay load and real concurrent traffic** | Waived as a prerequisite for continuing development, based on the owner's pre-release/low-user premise. Local row count does not simulate that distribution; the 12-row VPS probe does not establish capacity. | Before any production shadow flag enablement or NOTE authority cohort: production-version disposable synthetic multi-user/overlay workload and measured concurrency; [P5-09](../task/decoupling/P5_EXECUTION_PLAN_2026-09-20.md). |
| Metadata-lock/traffic measurement, row/storage amplification, p95/p99 batch tail, quantitative abort/cohort limits | Not measured reliably; SSH-tunnel timings are not server capacity. No numerical release limit is claimed. | Measure and approve limits/runbook in P5-09 before production enablement. |
| Complete MySQL fault matrix: rekey versus backfill, forced deadlock/disconnect, JSON/size, real-writer duplicate key, worker retry/DLQ | Partial race/fault evidence only; remaining cases are **not passed**. | Add production-version disposable fault tests in P5-09; hard stop on any loss of `CardProgress` atomicity or stale trusted mirror. |
| Representative source-data backup and full production rollback timing | Synthetic checksum/flags-off rollback passed locally and on VPS small cohort; no production backup or restore was performed. | Separate production deployment approval and backup/restore/rollback plan; no schema downgrade as routine rollback. |

## Conditions of closure

1. P4-11 is closed only as a **development dependency** so `INT-02` and Phase 5 design/implementation planning can proceed. The original release-grade criteria above remain open operational risks and must not be silently marked passed.
2. Phase 4 shadow write/compare/backfill flags stay off in production unless a separate enablement decision first addresses the deferred matrix and sets measured abort/rollback limits. Continue serving `CardProgress`; do not use shadow as product read authority.
3. `INT-02` was required to run its final integration/static-authority review and `--changed`/`--all` pre-release test gate before Phase 4 itself could close. [That gate subsequently passed](./phase-4-int02-closeout-2026-09-20.md). Closing P4-11 alone did not close INT-02 or approve Phase 5 production cutover.
4. If the pre-release/low-traffic premise changes, or a deployment would turn on Phase 4 flags before P5-09, reopen the operational rehearsal gate before that deployment. Any unexplained reconciliation difference or failed atomicity test is a hard stop regardless of traffic size.

**Decision:** accept the measured migration/flags-off/backfill/reconciliation/rollback subset for the current development milestone, with the above explicit risk deferral. No unmeasured capacity, fault, or release-readiness claim is made.
