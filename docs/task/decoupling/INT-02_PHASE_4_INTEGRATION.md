# INT-02 — Phase 4 integration and closeout

> Scope: Phase 4 integration
>
> Priority: P0 final gate
>
> Status: IN PROGRESS — local integration subset passes; P4-11 final gate open
>
> Dependency: P4-00 through P4-11
>
> Primary lane: Architecture / Integration / Release review

## Mục tiêu

Xác minh Phase 4 hoạt động như một derived shadow hoàn chỉnh, không tạo second authority hoặc làm thay đổi behavior của Card-based product paths; cập nhật tracker và chuẩn bị recommendation riêng cho Phase 5.

## Công việc

1. Review all diffs by task/file ownership; reject unrelated refactor or hidden authority cutover.
2. Re-run searches for:
   - product reads from shadow;
   - independent mirror commits/catch-and-continue;
   - missing writer/delete/reset/rekey paths;
   - scheduler replay in backfill;
   - silent fan-in winner/default normalization;
   - startup backfill/create-all dependency;
   - schema drift hidden by the Phase 4 migration.
3. Verify P4-00 frozen session behavior, legacy/wire leases and composition binding integrity.
4. Run direct REST/MCP/session/worker/external/reset/cutover/delete flows with flags off and on.
5. Re-run/resume backfill and full read-only audit on disposable MySQL evidence.
6. Confirm logical overlay source/local identity and no source mutation.
7. Confirm every source row/reference has trusted mirror or accepted quarantine/disposition.
8. Confirm CardProgress remains all product read/write authority and Phase 4 flags default off.
9. Run modular tests, typecheck/lint, `--changed`, then full suite as final gate.
10. Update canonical architecture tracker, task index, handoffs and rollout evidence links.
11. Produce Phase 5 go/no-go recommendation without enabling cutover.

## Exit checklist

- P4-00 freeze gate pass.
- P4-01 current schema/data/writer evidence accepted.
- P4-02..P4-05 ADR/schema decisions accepted.
- P4-06 additive migration/mapper pass on SQLite and MySQL.
- P4-07/P4-08 all authoritative writers/lifecycle paths atomic.
- P4-09 backfill accounting/resume/race gates pass.
- P4-10 zero unexplained reconciliation difference.
- P4-11 backup/migration/restart/load/rollback rehearsal pass.
- No product shadow read, second authority, source mutation or destructive cleanup.

## Verification

```text
python scripts/run_tests.py --module study,connect_mcp,decks,flashcards,database,cli --backend-only
python scripts/run_tests.py --module study --frontend-only
python scripts/run_tests.py --changed
npm --prefix frontend run typecheck
npm --prefix frontend run lint
python scripts/run_tests.py --all
```

Run full suite only at this pre-release closeout gate after narrower suites pass.

## Output

- Integration/exit report with commands/results and MySQL evidence.
- Updated canonical tracker and completed task index.
- Quarantine/known limitation inventory.
- Phase 5 recommendation and required separate approvals.

## Progress — 2026-09-20

The [rehearsal report](../../architecture/phase-4-reconciliation-rollout-rehearsal-2026-09-20.md)
records 948 passing modular backend tests, 179 passing Study frontend tests,
passing typecheck/lint (lint has existing warnings), default-off flag/static
authority checks and a 16,424-row disposable MySQL reconciliation with zero
unexplained differences. Local migration/restart/backup/rollback and several
two-connection probes pass. A subsequent isolated VPS MySQL 8.0.46 run passed
migration round-trip, flags-off restart/rollback, checksum-equal synthetic
restore, SELECT-only reconciliation and full audit on 12 synthetic rows with
the production database collation and SQL mode; the application database
remained read-only and at head 39. Four further VPS disposable probes passed
schema/codec, backfill resume/create/reset/delete races, native fan-in/fault/
lock timeout, and external lifecycle/native–external race cases. These results
do **not** close INT-02:
P4-11 still lacks a representative production-version multi-user/overlay
load/traffic rehearsal and the complete failure matrix. The final
`--changed`/`--all` pre-release gate is deferred
until those prerequisites are satisfied. No Phase 5 authority cutover is
authorized. Current Phase 5 recommendation: **NO-GO** pending P4-11 and this
final integration gate; this is an evidence status, not a claim that the
derived shadow is product authority.

## Rollback

If any gate fails, keep Phase 4 `Partial`, disable mirror/compare/backfill apply, retain evidence, and continue CardProgress-only runtime. Do not weaken tests or delete quarantine to claim completion.

## Không làm

- Không enable Note progress authority.
- Không execute production cutover.
- Không implement Phase 5/6/7 storage contraction or purge.
