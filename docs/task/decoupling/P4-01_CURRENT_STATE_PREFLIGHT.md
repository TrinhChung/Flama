# P4-01 — Current MySQL, schema, data and writer preflight

> Phase: 4
>
> Priority: P0 gate
>
> Status: IN PROGRESS — current MySQL evidence captured; actionable schema drift and the independent batch-table migration disposition remain blocked
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

## Current handoff — 2026-09-12

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
- Repository and database Alembic heads both equal `20260910_000036`, but 15 normalized actionable drift entries remain: 12 server-default mismatches, one ordinary-index mismatch, one `student_offer_mode` width mismatch and the missing `study_session_batches` table.
- Independent repository blocker: `study_session_batches` is declared/used, absent from production and absent from Alembic migration declarations. It must be resolved independently and must not be hidden in P4-06.
- Until the schema drift and missing-table migration disposition are resolved, P4-01 remains open and P4-05 remains blocked. P4-02..P4-04 may consume the measured production distributions but still require joint acceptance.

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
