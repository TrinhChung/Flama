# P4-05 — Physical shadow schema design

> Phase: 4
>
> Priority: P0 design gate
>
> Status: **COMPLETED / ACCEPTED FOR P4-06 IMPLEMENTATION**
>
> Dependency: P4-02, P4-03, P4-04 accepted; P4-01 schema evidence complete
>
> Primary lane: MySQL schema architecture

## Mục tiêu

Chuyển logical contracts thành một additive MySQL design có lockable subject, exact state, query projection và audit/backfill accounting trước khi viết migration.

## Công việc

1. Compare at least:
   - one envelope row with JSON state/availability/contributors;
   - envelope plus separate state, availability, contributor and disposition/run rows.
2. Evaluate row growth, joins, write amplification, deadlocks, JSON validation, index size and SQLAlchemy/Alembic ergonomics.
3. Specify exact columns/types/nullability/defaults for:
   - learner/Note envelope and monotonic generation;
   - current Algorithm State key/version/schema/JSON/hash/size/status;
   - availability anchors;
   - current/historical contributor evidence;
   - backfill run/checkpoint/disposition/quarantine.
4. Specify PKs, UQs, FKs/delete actions, status constraints, active-row cardinality and indexes for hot audit/query paths.
5. Decide Note delete behavior and retained identity using P4-04; do not inherit Card cascade blindly.
6. Define canonical timestamp/float/JSON encodings across SQLite test fixtures and MySQL 8.
7. Define feature flags, model registration and migration-only boot behavior.
8. Separate existing `study_session_batches` migration drift disposition from new DDL.
9. Produce upgrade/downgrade, online-lock and rollback analysis; no production apply.

## Recommended direction

Envelope plus separate current state, availability and contributor/disposition rows, because it gives a stable learner/Note lock and explicit reconciliation evidence. The ADR may choose another design only with equivalent locking, accountability and query behavior.

## Completion handoff — 2026-09-13

The [accepted physical schema ADR](../../architecture/phase-4-physical-shadow-schema-adr-2026-09-13.md) selects the recommended normalized direction and fixes:

- ten additive table contracts for subject/state/contributor/availability/lineage/history/lifecycle and backfill run/checkpoint/disposition storage;
- exact MySQL types, nullability, defaults, PK/UQ/FK/delete actions, checks and hot-path indexes;
- a binary immutable Note/Card identity beside nullable live FKs, so content cascades cannot erase lifecycle evidence;
- exact bounded JSON/codec/hash rules with relational availability anchors and no stored `eligible_now`;
- the idempotent unique-key first-create protocol and global subject-before-contributor lock order;
- a production-sized initial estimate of roughly 380,846 additive rows from 16,424 progress rows and 125,554 history events;
- additive migration order, complete-contract adoption for any startup-created table, empty-only downgrade and flag-off production rollback;
- independent default-off write, comparison and backfill flags, with no Phase 4 shadow-read authority flag;
- the exact P4-06 file-ownership and verification handoff.

No DDL, model, runtime flag or writer was added by P4-05 itself. P4-06 is now ready for a separately reviewable implementation slice.

## Output

- Accepted physical schema ADR and ERD.
- Exact migration specification and index/access map.
- Data volume/row amplification estimate grounded in P4-01.
- Migration lock/downtime analysis and rehearsal matrix.
- File ownership plan for P4-06.

## Acceptance

- No DDL ambiguity remains for P4-06.
- Unique learner/Note identity and first-create race are DB-enforced or equivalently proven.
- State JSON cannot be read without exact decoder identity/hash validation.
- Availability hot queries do not parse arbitrary Algorithm State JSON.
- Every source row/reference maps to contributor/disposition storage.
- All schema operations are additive; `CardProgress` is untouched.

## Verification

Review generated SQL for MySQL 8, compare ORM/migration metadata and validate against current `information_schema` evidence. Runtime change: none.

## Rollback

Supersede before P4-06. After expansion, runtime rollback is flag-off; no production incident downgrade.
