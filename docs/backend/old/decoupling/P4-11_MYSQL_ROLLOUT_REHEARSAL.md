# P4-11 — Disposable MySQL rollout and rollback rehearsal

> Phase: 4
>
> Priority: P0 deployment gate
>
> Status: **CLOSED FOR PRE-RELEASE DEVELOPMENT (risk-scoped acceptance, 2026-09-20)**. Production enablement gate remains open; see the [decision record](../../architecture/phase-4-p4-11-pre-release-closeout-2026-09-20.md).
>
> Dependency: P4-10
>
> Primary lane: Database operations / Deployment evidence

The owner's pre-release/low-user premise narrows this task's **development dependency**. It does not turn the untested production-scale and fault cases below into passing evidence. [INT-02 subsequently closed for development](../../architecture/phase-4-int02-closeout-2026-09-20.md), but no Phase 4 shadow flag or Phase 5 authority may be enabled in production by this closeout.

## Mục tiêu

Chứng minh migration, flags-off restart, atomic mirror, bounded backfill, reconciliation và runtime rollback trên disposable MySQL 8 trước khi có bất kỳ production apply nào.

## Environment

- Match production MySQL minor version, `sql_mode`, charset/collation, timezone and datetime precision.
- Restore an approved redacted/secured representative snapshot or generate a signed synthetic distribution from P4-01 counts.
- Run migration-only path from actual pre-Phase4 schema; do not bootstrap core tables with `db.create_all()`.

## Công việc

1. Backup and restore rehearsal with measured duration/checksum.
2. Upgrade migration and verify ORM/`information_schema`; disposable downgrade/upgrade round-trip.
3. Restart `wsgi.py`/Gunicorn with all Phase 4 flags off; verify no backfill/mirror side effect.
4. Enable mirror on bounded test cohort and exercise every writer/lifecycle path.
5. Run two-connection races: first envelope insert, sibling Cards, direct vs session, worker delivery, native vs external, reset/delete/rekey vs backfill.
6. Inject duplicate key, lock timeout, deadlock, codec/JSON/size, savepoint, DB disconnect and worker retry/DLQ failures.
7. Run bounded backfill; record batch time, locks, retries, rows/sec, row amplification and storage size. Tune batch sizes from measurements.
8. Run full P4-10 audit; require zero unexplained diff.
9. Disable mirror/compare flags and verify immediate product behavior continues exclusively from `CardProgress`.
10. Document rollout order, monitoring, abort thresholds, on-call commands and forward repair. No production execution in this task unless separately authorized.

## Output

- Signed rehearsal report with commands, versions, timing, EXPLAIN and failure matrix.
- Verified backup/restore evidence.
- Recommended production batch/cohort limits grounded in measurements.
- Rollout/rollback runbook and go/no-go verdict for INT-02.

## Original release-grade acceptance (not fully demonstrated)

- Migration-only upgrade works and flags-off restart is behaviorally unchanged.
- All concurrency/failure tests preserve authoritative atomicity and produce no trusted stale mirror.
- Backfill completes/resumes inside measured limits without unbounded lock/table scan.
- Full reconciliation has zero unexplained difference.
- Flag disable restores CardProgress-only runtime without schema downgrade.
- Production apply remains a separate explicit operation.

## Accepted pre-release development gate

The [risk-scoped closeout](../../architecture/phase-4-p4-11-pre-release-closeout-2026-09-20.md) accepts the already recorded local representative-**row-count** and VPS version/collation-matched **small-cohort** migration, checksum backup/restore, flags-off restart, bounded backfill/resume, SELECT-only zero-diff reconciliation, indexed lookup and partial two-connection/fault evidence. This closes P4-11 as a dependency for `INT-02`, **not** as a production rollout pass. Production-shaped multi-user/overlay load, metadata-lock/capacity measurement, complete fault matrix and quantitative abort limits are deferred to P5-09 and must be done before production shadow enablement or NOTE authority enrollment. The original acceptance above remains the record of what was waived, not a claim of completion.

## Verification

Run the full MySQL rehearsal matrix plus relevant modular backend suites. Store no credentials or unredacted user data in Git.

## Local progress — 2026-09-20

The [local evidence report](../../architecture/phase-4-reconciliation-rollout-rehearsal-2026-09-20.md)
records a migration-only disposable path from a reconstructed local head-38
core schema, migration round-trip, checksum-equal synthetic backup/restore,
flags-off `wsgi.py` restarts before and after backfill, a bounded backfill,
indexed lookup plans and a full read-only audit with a SELECT-only principal.
The 16,424-row synthetic local run completed in 165 backfill batches with
zero unexplained reconciliation differences. Its measured times and indexed
query plans are in the report. The local server is MySQL 8.0.40 with
`utf8mb4_0900_ai_ci`; the production preflight recorded MySQL 8.0.46 with
`utf8mb4_unicode_ci`. This is **not** an environment match or an approved
production apply. The complete race/fault matrix, production-shaped
multi-user/overlay cohort, metadata-lock measurement, operational batch/abort
limits and signed rehearsal result remain open.

## Isolated VPS progress — 2026-09-20

With explicit approval, an isolated database on the production VPS ran the
migration 38→39 round-trip, synthetic backup/restore checksum, flags-off
`wsgi.py` restarts, backfill, SELECT-only two-run reconciliation, full audit and
indexed lookup checks on MySQL 8.0.46. The database default matched `flama`'s
`utf8mb4_unicode_ci` and SQL mode. The live `flama` database was read-only:
its observed Alembic head was already `20260913_000039` before and after the
probe. Only DDL, not application rows, was copied to reconstruct a head-38
core schema. The disposable databases and principal were removed and their
absence was verified. All checks passed for **12 synthetic progress rows**;
exact timings and limitations are in the [evidence report](../../architecture/phase-4-reconciliation-rollout-rehearsal-2026-09-20.md#isolated-vps-mysql-rehearsal).
Four further version/collation-matched disposable probes passed: shadow
schema/codec/duplicate-key savepoint, resumable backfill with create/reset/
delete races, native fan-in/fault/lock timeout, and external lifecycle with
native–external race. Each used synthetic model-generated core tables, not a
production data copy. Post-check again found no temporary database/principal.

At the time of this rehearsal, this did **not** meet the original release-grade P4-11 gate. The 16,424-row local cohort ran on MySQL 8.0.40;
the VPS cohort is small and one-user, with tunnel-dominated timings. A
representative, version-matched cohort, the remaining fault/race matrix,
metadata-lock/load measurements, release limits and reviewed go/no-go remain
open. No production application write or authority cutover was performed. The later pre-release closure and explicit deferrals are recorded in the [decision record](../../architecture/phase-4-p4-11-pre-release-closeout-2026-09-20.md).

## Rollback

Disable mirror and compare flags; keep additive schema/data. Use restored backup only for rehearsal proof or separately approved disaster recovery, not routine rollback.
