# Phase 4 schema drift remediation — 2026-09-13

> Mode: DESIGN
>
> Engine: MySQL 8.0 OLTP
>
> Scope: P4-01 entry blockers only; no progress authority or runtime behavior change

## Outcome

The repository now declares the previously missing `study_session_batches`
table through an independent Alembic revision and reconciles the remaining
P4-01 model/migration drift through a second forward-only repair. Local MySQL
rehearsal reaches repository/database head `20260913_000038` with zero schema
drift under the Phase 4 preflight comparator.

Production applied both revisions in release
`11eefb15938cc8f4847df6d2d4014f40f41f3d13`. The fresh SELECT-only bundle
confirms matching head `20260913_000038`, zero schema drift and no batch-table
contract issue.

## Observed state

- `StudySessionBatch` was introduced with runtime readers/writers but without
  an Alembic revision.
- Production evidence at head `20260910_000036` showed the batch table absent.
- Twelve database server defaults came from existing additive migrations but
  were absent from ORM `server_default` declarations.
- `student_offer_mode` was migrated as `VARCHAR(32)` while the ORM enum compiled
  as `VARCHAR(16)`, and its model-declared index was absent.
- Local MySQL additionally retained nullable marketplace taxonomy metadata from
  the original additive migration.

## Systems of record

| Concern | Authority before repair | Repair |
|---|---|---|
| Batch runtime shape | `models/study_session_batch.py` | `20260913_000037` declares and validates it |
| Existing server defaults | prior Alembic revisions and deployed MySQL | ORM metadata now declares the same defaults |
| Student offer width | migration/deployed `VARCHAR(32)` | ORM enum length pinned to 32 |
| Taxonomy nullability | ORM target; deployment-dependent database shape | null backfill followed by conditional `NOT NULL` |
| Progress state | `card_progress` | unchanged |

## Invariants

- No source Note/Card copy is introduced for logical overlay installs.
- No progress row is rekeyed, merged, backfilled or mirrored.
- Existing batch rows survive rollback and future re-upgrade.
- DDL does not silently adopt an incompatible pre-existing batch table.
- Widening `student_offer_mode` is allowed; an unproven shrink is rejected.

## Alternatives and trade-offs

### A. Put the batch table in P4-06

Rejected. It would erase the provenance gap and couple an existing async
runtime dependency to the new progress-shadow rollout.

### B. Use create-if-missing and trust existing tables

Rejected. It is operationally convenient but can stamp missing constraints or
indexes as valid. Failures would surface later under worker concurrency.

### C. Independent contract-aware migration and reconciliation

Selected. It adds validation complexity to the migration, but preserves both
known histories: strict Alembic databases where the table is absent and
startup-bootstrapped databases where it may already exist.

Keeping the historical server defaults is preferred over dropping them. They
are deterministic, already deployed, and safe for non-ORM writers; declaring
them in the model removes drift without table-wide data rewrites.

## Migration sequence

```text
20260910_000036
        |
        v
20260913_000037  batch table: create or validate compatible existing shape
        |
        v
20260913_000038  defaults, safe width/nullability convergence, missing index
        |
        v
fresh SELECT-only P4-01 evidence
```

Both revisions are additive/forward repairs. Runtime rollback is feature-flag
rollback; schema downgrade intentionally performs no destructive contraction.

## Verification evidence

- Focused migration and audit slice: 24 tests passed after one test-only
  transaction-visibility correction.
- Local MySQL upgraded from `20260910_000036` to `20260913_000038`.
- `study_session_batches` contract issues: none.
- Phase 4 local schema comparison: zero drift and matching Alembic head.

## Production verification completed

- The normal release migration unit applied `000037` and `000038`; no
  application test was run against production.
- The deterministic two-pass bundle used an ephemeral `SELECT, SHOW VIEW`
  principal and the principal was removed afterward.
- Repository/database head matches, schema drift is zero, the batch contract
  has no issue and active/enqueued batch count is zero.
- [Joint P4-01/P4-02/P4-03/P4-04 acceptance](./phase-4-logical-contract-joint-acceptance-2026-09-13.md)
  closes the gate and allows P4-05 physical design.
