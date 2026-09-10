# P4-06 — Additive schema and lossless compatibility mapper

> Phase: 4
>
> Priority: P0
>
> Status: TODO
>
> Dependency: P4-05
>
> Primary lane: Models / Migration / Pure mapping

## Mục tiêu

Implement approved additive tables and pure, exact mapping from `CardProgress` without changing runtime authority or automatically populating data.

## Công việc

1. Add flat model modules, relationships and explicit app metadata registration.
2. Add one Alembic revision from verified current head; do not depend on `db.create_all()`.
3. Add flags with defaults off; no startup backfill/repair.
4. Implement raw snapshot codec covering every `CardProgress` field and contributor identity/pointer/provenance.
5. Implement exact `legacy-anki/1.0.0` + state-schema compatibility mapper and decoder registry.
6. Implement normalized availability anchor projection using explicit frozen policy/timezone inputs.
7. Validate status/queue/ranges/finite floats/JSON size/hash/schema version; typed quarantine for invalid/unknown input.
8. Add independent golden fixtures for NULLs, fractional intervals, due time/day, suspension/burial, leech, memory fields, pointer and revision.
9. Test migration-only upgrade/downgrade on SQLite and disposable MySQL; compare model metadata to actual schema.
10. Verify flags-off `wsgi.py`/Gunicorn startup and all existing reads/writes.

## Output

- Additive models and migration.
- Pure raw/state/availability codecs and validator registry.
- Config flags off by default.
- Migration report and golden vectors.

## Acceptance

- No existing table/column is dropped, rewritten or made authoritative.
- Raw snapshot round-trip is lossless and deterministic.
- Golden expected values are not calculated by the implementation under test.
- Invalid/unknown state cannot be marked trusted.
- Upgrade works from the real pre-Phase4 schema without startup create-all.
- Zero mirror/backfill rows are created by normal flags-off startup.

## Verification

```text
python scripts/run_tests.py --module database,study,core --backend-only
python scripts/run_tests.py --module cli --backend-only
```

Plus disposable MySQL migration upgrade/downgrade and flags-off restart proof.

## Rollback

Disable flags and keep additive tables. Downgrade only in disposable rehearsal or separately approved pre-production rollback.

## Không làm

- Không add writer hooks/backfill.
- Không read shadow in product queries.
- Không add physical composition/application tables.
