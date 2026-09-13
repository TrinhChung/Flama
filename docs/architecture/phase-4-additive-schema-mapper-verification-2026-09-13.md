# Phase 4 — Additive schema and mapper verification

> Date: 2026-09-13 | Task: P4-06
>
> Status: **IMPLEMENTED / PR #166 MYSQL REGRESSION FIXED LOCALLY**
>
> Runtime authority: unchanged (`CardProgress`) | Production migration: not run

## Delivered boundary

P4-06 implements the accepted physical design without connecting it to a
production writer, backfill process or read-authority path:

- ten additive `study_progress_*` ORM tables with explicit metadata registration;
- Alembic head `20260913_000039`, based on `20260913_000038`;
- fail-closed validation for a compatible historical `db.create_all()` schema;
- empty-only guarded downgrade;
- three independent shadow flags, all defaulting to `false`;
- lossless `raw-card-progress.v1` codec covering every ORM-visible
  `CardProgress` column;
- exact `legacy-anki/1.0.0` + `anki-card-state.v1` mapper and decoder registry;
- contributor availability anchors plus an evaluator requiring frozen clock,
  timezone, day boundary, learn-ahead, effective Card scope and policy version;
- transaction-neutral subject first-create/lock and stale-fence primitives;
- a disposable local-MySQL migration/round-trip probe.

No current study, import, reset, clone-cutover or deletion callsite imports the
new mapper/repository. No startup hook creates data. No shadow read-authority
configuration exists.

## Codec evidence

The independent golden fixtures verify:

- canonical base-10 integer strings, including values above the JavaScript safe
  integer range;
- exact finite IEEE-754 binary64 tokens;
- distinct raw hashes for positive and negative zero while semantic state
  normalizes both zero signs;
- UTC timestamps with six fractional digits;
- unchanged nullness and exact string values;
- `learn` as the sole `learning` alias, with a different raw hash but equal
  state/semantic hashes;
- unknown queues, partial memory pairs, non-finite numbers, hash mismatch and
  invalid availability context failing with typed codes;
- UTF-8 identity capacity at the exact 144-byte boundary;
- a metadata inventory assertion that fails if `CardProgress` gains an
  unclassified column.

Golden digests are literal test fixtures rather than values calculated by the
implementation under test.

## Migration evidence

SQLite verification covers missing-table upgrade, compatible-table revalidation,
incompatible-table fail-closed behavior, empty downgrade, non-empty downgrade
rejection, default-off startup and no-self-commit first-create behavior.

The disposable MySQL probe now leaves the database collation at the MySQL 8
default instead of forcing `utf8mb4_unicode_ci`. This reproduces the
`utf8mb4_0900_ai_ci` parent-column contract used by CI and the primary local
database. Random databases remain guarded by the `flama_p4_shadow_probe_*`
prefix and are deleted after completion. The probe reproduces the pre-P4
baseline, stamps `20260913_000038`, then performs:

1. upgrade to `20260913_000039`;
2. complete reflected column/type/default/PK/UQ/FK/delete/index/check/table-option
   comparison for all ten tables;
3. duplicate-safe learner/Note first-create;
4. MySQL JSON/raw-codec and `DATETIME(6)` microsecond round-trip;
5. user-privacy cascade cleanup;
6. guarded empty downgrade to `20260913_000038`;
7. upgrade again to `20260913_000039`;
8. real `db.create_all()` startup pre-creation before Alembic revalidation;
9. exact effective-collation comparison for `live_note_id -> notes.id` and
   `live_card_id -> cards.id`;
10. final zero-row accounting for every new table.

The two live UUID columns resolve the parent column charset/collation at DDL
time. Shadow table defaults remain `utf8mb4_unicode_ci`; no legacy table is
altered. The full CI command (`flask --app wsgi.py db upgrade` with startup
maintenance and `db.create_all()` enabled) passed from an empty database under
both `utf8mb4_0900_ai_ci` and `utf8mb4_unicode_ci`.

Result: every table reported zero contract issues and zero final rows. Both FK
collation pairs matched their parents. A final `information_schema` check found
no remaining `flama_p4_shadow_probe_*` database.

## Regression evidence

```text
Focused P4-06 tests after FK fix:           17 passed
Changed-file database/study modules:       205 passed
MySQL default-collation probe:              passed
Full CI MySQL command, 0900_ai_ci:          passed
Full CI MySQL command, unicode_ci:          passed
Python compileall:                           passed
wsgi.py flags-off import:                    app / false / false / false
Alembic repository head:                     20260913_000039
git diff --check:                            passed
```

The environment has neither Ruff nor Black installed, so those optional tools
were not used. The repository's required modular test runner and MySQL probe
both passed.

## Rollout state and next task

- No production or primary local database was migrated.
- The MySQL regression fix remains uncommitted on PR branch
  `local/p4-06-shadow-schema-codecs` for user review.
- Runtime rollback remains “keep all three flags false”; the additive tables are
  inert.
- P4-07 is next after P4-06 is reviewed/committed: wire the mapper through one
  no-commit coordinator into native/session/worker transactions, still with the
  write flag off by default.
