# P4-10 — Shadow comparison and reconciliation audit

> Phase: 4
>
> Priority: P0 exit gate
>
> Status: TODO
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

## Rollback

Disable online comparison and mirror writes if needed; keep audit/read-only tooling and `CardProgress` authority.
