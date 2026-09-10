# P4-11 — Disposable MySQL rollout and rollback rehearsal

> Phase: 4
>
> Priority: P0 deployment gate
>
> Status: TODO
>
> Dependency: P4-10
>
> Primary lane: Database operations / Deployment evidence

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

## Acceptance

- Migration-only upgrade works and flags-off restart is behaviorally unchanged.
- All concurrency/failure tests preserve authoritative atomicity and produce no trusted stale mirror.
- Backfill completes/resumes inside measured limits without unbounded lock/table scan.
- Full reconciliation has zero unexplained difference.
- Flag disable restores CardProgress-only runtime without schema downgrade.
- Production apply remains a separate explicit operation.

## Verification

Run the full MySQL rehearsal matrix plus relevant modular backend suites. Store no credentials or unredacted user data in Git.

## Rollback

Disable mirror and compare flags; keep additive schema/data. Use restored backup only for rehearsal proof or separately approved disaster recovery, not routine rollback.
