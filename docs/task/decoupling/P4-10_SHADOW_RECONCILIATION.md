# P4-10 — Shadow comparison and reconciliation audit

> Phase: 4
>
> Priority: P0 exit gate
>
> Status: LOCALLY COMPLETE — intentionally uncommitted; P4-11 deployment gate open
>
> Dependency: P4-09
>
> Primary lane: Read-only audit / Study query parity

## Mục tiêu

Prove the derived mirror explains all current CardProgress data and reproduces state/availability behavior under fixed contexts without serving shadow data to users.

## Công việc

1. Extend audit schema with mirror/storage/codec/run versions and deterministic accounting.
2. Compare every source raw snapshot hash, contributor identity/revision, last-event pointer and Connect provenance.
3. Reconcile single/equivalent/divergent/NULL/orphan/reset/deleted/rekey/corrupt dispositions independently.
4. Validate exact state decoder and sample current-scheduler transitions against frozen golden inputs.
5. Compare due counts, buckets and complete ordering at fixed `now`, timezone, day boundary, learn-ahead and deck policy.
6. Cover new, learning time/day, relearning, review due-day precedence, suspended, finite/indefinite burial and no-progress.
7. Preserve current Card multiplicity/tie-breakers when projecting Note mirror back for comparison.
8. Cover owned/mixed-template, real installed-source and installed-local Note contexts.
9. Compare after every writer type: direct REST, MCP, sync commit, worker, Anki snapshots/import, reset, cutover/rekey and delete.
10. Separate understood representation tolerance from unexplained mismatch. Every tolerance has name, field, bound, count and sample.
11. Run twice on one snapshot to prove deterministic output and stable checksums.

## Output

- Versioned read-only audit/comparator and schema.
- Full accounting, parity and tolerance report.
- Golden/fixed-time query and transition fixtures.
- Writer coverage matrix with pass/fail evidence.

## Acceptance

- Every source row, contributor and reference is accounted.
- Zero unexplained raw/state/availability/query-order difference.
- Every quarantine matches an accepted disposition and cannot be read as trusted state.
- No product API/repository uses the mirror for a decision.
- Audit runs via mutation-disabled entrypoint and is deterministic.

## Verification

```text
python scripts/run_tests.py --module study,analytics,database,cli --backend-only
python wsgi_audit.py --compact
```

Plus disposable MySQL full reconciliation at representative volume.

## Local implementation evidence (2026-09-19)

Observed: `study_progress_reconciliation_service` provides a versioned read-only
report embedded in audit v5 only when `STUDY_PROGRESS_SHADOW_COMPARE_ENABLED=true`.
With the flag off, the audit does not query shadow tables. The comparator
accounts for raw hashes, generations, contributor/subject state, availability,
last-review pointers, applied Connect lineage, backfill dispositions, query
counts/order and explicit quarantine. It compares decoded shadow state against
the current `CardState` projection using the learner's resolved deck policy.
The accepted representation tolerances are a product fallback for null
`due_at`, a derived review `due_day`, and later Connect source-Note content
edits with unchanged identity and strictly advanced `updated_at`; each has
named fields, bounds, counts and samples. Source-Card snapshot hash drift
still blocks the gate.

Evidence: `tests/test_study_progress_reconciliation.py` covers deterministic
read-only runs, raw/provenance drift, Connect drift, quarantine, day-boundary
counting, installed source and installed-local notes in child deck scopes,
product transition goldens, and malformed transition failure. The local
disposable MySQL probe (`scripts/probe_phase4_reconciliation_mysql.py`) passed
with 1,002 and then 16,424 source rows, a SELECT-only principal,
REPEATABLE-READ snapshot, two identical reports, zero unexplained differences
and indexed query plans. The 16,424-row backfill used 165 bounded batches
in 413.002 s; two reconciliation runs took 313.468 s total. The probe
removed its temporary databases and principal. No production database was
touched. The 2026-09-20 modular integration run passed 948
backend tests across 86 files; 179 Study frontend tests passed too.

The transactional mirror suite now calls the reconciler after real direct REST,
MCP, session, async worker, reset, card delete and note delete flows, including
equivalent and divergent sibling fan-in. A valid contributor may retain its
availability row during subject-level divergence quarantine; the comparator
verifies that row but excludes the entire subject from trusted query parity.
`test_anki_import_api.py` now reconciles applied Connect revlog and legacy
progress imports; `test_flashcard_api_integration.py` reconciles a real
legacy-clone-to-overlay cutover. The report includes a required writer matrix
whose absent classes remain `NOT_OBSERVED`, never silently `PASS`.

Residual scope: P4-10's local representative-row-count acceptance is met,
but the synthetic MySQL cohort uses one owned learner/deck context;
installed overlay parity is proved by integration tests, not a
production-shaped MySQL mix. The exact production MySQL version/collation,
concurrent traffic and full failure matrix remain P4-11 deployment gates.
No shadow-backed product read has been enabled. See the
[2026-09-20 evidence report](../../architecture/phase-4-reconciliation-rollout-rehearsal-2026-09-20.md).

## Rollback

Disable online comparison and mirror writes if needed; keep audit/read-only tooling and `CardProgress` authority.
