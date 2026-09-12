# P4-01A — Independent schema drift remediation

> Phase: 4 entry remediation
>
> Status: IMPLEMENTED AND REHEARSED ON LOCAL MYSQL; production upgrade and fresh SELECT-only evidence pending
>
> Dependency: P4-01 production evidence captured at repository/database head `20260910_000036`
>
> Runtime authority change: none

## Goal

Close the schema blockers discovered by P4-01 without hiding historical drift
inside the later learner/Note shadow-schema migration.

## Invariants

1. `CardProgress` remains the only operational progress authority.
2. Async admission and wire-v3 issuance remain independently flag-off.
3. Existing `study_session_batches` data must never be dropped by rollback.
4. A startup-created batch table is reused only when its complete runtime
   contract is compatible; an unknown shape fails closed.
5. Marketplace overlay and release identities are unchanged.
6. This task contains no learner/Note progress shadow table or mirror writer.

## Work delivered

### Migration `20260913_000037`

- Declares `study_session_batches` independently from Phase 4 shadow storage.
- Creates the table when absent.
- Accepts an exact compatible table previously created by `db.create_all()`.
- Rejects incompatible columns, primary key, unique key, indexes or foreign
  keys before treating the table as migrated.
- Uses a non-destructive downgrade because migration history cannot prove
  whether an existing table was created by Alembic or startup bootstrap.

### Migration `20260913_000038`

- Reconciles the 12 intentional migration server defaults with ORM metadata.
- Keeps `student_offer_mode` at the migration-established `VARCHAR(32)` width.
- Adds the missing `student_offer_mode` index.
- Backfills null marketplace taxonomy metadata to `{}` before enforcing the
  declared `NOT NULL` contract where an older database still permits nulls.
- Fails before mutation when required tables/columns are missing or a string
  shrink cannot be proven safe.

## Alternatives considered

1. **Unconditional create-table migration:** rejected because databases touched
   by historical `db.create_all()` may already contain the table.
2. **`IF NOT EXISTS` without validation:** rejected because it would stamp an
   unknown shape as valid and defer failure to the async worker.
3. **Contract-aware adoption plus forward reconciliation:** selected because it
   handles both known database histories, preserves data and makes drift
   explicit.

## Verification

```text
python -m unittest tests.test_study_session_batch_migration
python -m unittest tests.test_phase4_schema_reconciliation_migration
python scripts/run_tests.py --module study,database,cli --backend-only
```

Local MySQL rehearsal on 2026-09-13:

- start: database head `20260910_000036`, `study_session_batches` absent;
- after `000037`: table present and the migration contract reported no issues;
- after `000038`: database/repository head `20260913_000038`;
- Phase 4 schema inventory: `drift_count=0`, `alembic_head_match=true`.

## Production gate

Do not mark P4-01 accepted from local evidence. Deployment must:

1. take the normal database backup/snapshot required by the release runbook;
2. apply `000037` and `000038` before enabling any async admission;
3. verify head `20260913_000038` and batch-table contract;
4. regenerate the two-run P4-01 bundle with an ephemeral SELECT-only principal;
5. require zero unexplained schema drift and retain the secured checksums.

## Rollback

Keep async admission disabled and perform a forward repair. Both revisions use
non-destructive downgrades; incident response must not drop the batch table,
shrink `student_offer_mode`, or reintroduce known schema drift.
