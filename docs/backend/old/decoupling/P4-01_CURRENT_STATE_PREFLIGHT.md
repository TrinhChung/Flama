# P4-01 — Current MySQL, schema, data and writer preflight

> Phase: 4
>
> Priority: P0 gate
>
> Status: **COMPLETED / ACCEPTED** — production head, zero-drift schema and deterministic SELECT-only refresh verified on 2026-09-13
>
> Dependency: accepted Phase 0 evidence as historical baseline
>
> Primary lane: Read-only audit / Database

## Mục tiêu

Tạo current, signed, read-only evidence đủ để chốt physical design và backfill; không suy production state từ SQLite hoặc report cũ.

## Công việc

1. Freeze commit, Alembic heads, model inventory, runtime settings và audit schema version.
2. Extend audit accounting cho:
   - total `CardProgress`, valid learner→Card→Note, NULL and orphan subjects;
   - learner/Note single/fan-in groups;
   - raw-state equality tách khỏi event/source lineage equality;
   - every contributor `last_review_event_id`, ReviewEvent và Connect reference;
   - canonical/noncanonical queue, due/time precision, burial/leech, scheduler labels and memory fields;
   - owned, installed-source and installed-local Note identity, including overlapping context memberships;
   - active sessions/batches/imports relevant to rollout.
3. Compare migration declarations, ORM metadata, startup-created tables and actual `information_schema`: PK/FK/delete actions, uniqueness, indexes, defaults, charset/collation, JSON/datetime/float types.
4. Disposition the missing repository migration reference for `study_session_batches` independently; Phase 4 migration must not hide it.
5. Reconfirm complete writer/delete/reset/rekey inventory and transaction/savepoint owners.
6. Run through `wsgi_audit.py`/`create_audit_app()` with startup mutation disabled and a SELECT-only account.
7. Run twice on one snapshot and compare deterministic fields; redact user content/secrets.
8. Store report/checksum, command, timing, exit code and drift table.

## Output

- Updated audit contract/tests.
- Current MySQL verification report and redacted machine-readable artifact or secured artifact checksum.
- Schema drift and writer inventory with blocker/warn/pass disposition.
- Explicit data-volume inputs for P4-05/P4-09/P4-11.

## Current handoff — 2026-09-13

- Implemented audit contracts: `study-architecture-audit.v4` and `study-phase4-preflight.v1`.
- Added a grant-first MySQL guard that refuses non-`SELECT`-only principals before application-table inspection.
- Added schema/model/migration/default/table-option drift inventory, progress/lineage/disposition accounting and a machine-readable writer lifecycle inventory.
- P4-02 cross-check hardened the audit with missing-learner disposition and independent overlapping context-membership counts; the exclusive context partition remains for compatibility.
- Added `scripts/run_phase4_preflight_bundle.py` for two fixed-time runs, deterministic comparison, timings, exit codes and checksums.
- Fixed two audit-only portability defects found by the production run: use a non-reserved alias for `CURRENT_USER()` and normalize MySQL collation/Boolean reflection while comparing unique sets separately from ordinary indexes.
- Repository investigation report: [Phase 4 current-state preflight](../../architecture/phase-4-current-state-preflight-2026-09-10.md).
- Production evidence was captured at `2026-09-12T11:16:29Z` with an ephemeral principal limited to `SELECT, SHOW VIEW`; the normal application principal was not used and the ephemeral principal was verified absent after the run.
- Both fixed-time runs were byte-equivalent at the canonical-report layer, with no changed JSON paths. The secured bundle remains outside the repository at `/var/lib/flama-audit/phase4-preflight-20260912T111629Z`.
- Production has 16,424 valid progress rows: all 16,424 are preliminary mirror candidates, with zero unresolvable rows, zero quarantine candidates and zero learner/Note fan-in groups. Every accounting partition passed.
- The captured production evidence remains at repository/database head `20260910_000036` and reports the 15 normalized actionable drift entries observed before remediation.
- [P4-01A](./P4-01A_SCHEMA_DRIFT_REMEDIATION.md) now declares `study_session_batches` independently in `20260913_000037` and reconciles the remaining model/migration contracts in `20260913_000038`; local MySQL reaches the new head with zero preflight schema drift.
- The normal production migration unit applied both revisions in release `11eefb15938cc8f4847df6d2d4014f40f41f3d13` and the refreshed deterministic SELECT-only bundle confirms repository/database head `20260913_000038`, a valid batch-table contract and `drift_count=0`.
- The accepted refresh is stored at `/var/lib/flama-audit/phase4-preflight-20260912T225725Z-11eefb1`; both canonical reports hash to `59bdd8e680f09d0ed78a9164426abcf19ada81311d738dcf1947c15628aa1d63`, comparison reports changed paths `[]`, and all recorded file checksums verify.
- Both runs report P4 gate `PASS`, zero P4 blockers/warnings and zero active-open sessions, active Connect imports or active/enqueued batches. The wider audit's seven historical warnings remain explicitly tracked but do not block this current-state/schema gate.
- [Joint acceptance](../../architecture/phase-4-logical-contract-joint-acceptance-2026-09-13.md) closes P4-01 with P4-02/P4-03/P4-04 and authorizes P4-05 design.

## Completion handoff — 2026-09-13

```text
Task ID: P4-01
Primary outcome: deterministic production MySQL current-state/schema/writer evidence with complete source accounting.
Production release: 11eefb15938cc8f4847df6d2d4014f40f41f3d13.
Repository/database head: 20260913_000038 / 20260913_000038.
Schema drift: 0; batch contract issues: none.
Current progress: 16,424 source = 16,424 mirror + 0 quarantine + 0 unresolvable.
Determinism: two canonical reports equal; changed paths empty; checksums verified.
Safety: startup mutation disabled; ephemeral SELECT/SHOW VIEW principal removed after collection.
Runtime/schema change in P4-01: none.
Follow-up: P4-05 physical design, then P4-06 implementation.
```

## Acceptance

- `total source = mirrored candidates + quarantine candidates + unresolvable`, before any migration.
- Fan-in state and lineage counts reconcile independently.
- No audit DDL/DML, startup maintenance or application-runtime entrypoint.
- Every schema/data unknown that changes DDL or backfill has an owner and blocks P4-05 until resolved.
- Historical P0 evidence is labeled baseline, not current fact.

## Verification

```text
python scripts/run_tests.py --module study,database,cli --backend-only
python wsgi_audit.py --compact
```

Do not run application tests against production DB.

## Rollback

Read-only task; discard and regenerate any artifact that violates redaction policy without rewriting Git history.

## Không làm

- Không tạo migration/model.
- Không run backfill hoặc repair.
- Không connect bằng normal `wsgi.py` để lấy evidence.
