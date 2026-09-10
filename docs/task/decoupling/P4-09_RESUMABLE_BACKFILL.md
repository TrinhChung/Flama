# P4-09 — Resumable, fenced learner/Note shadow backfill

> Phase: 4
>
> Priority: P0 data gate
>
> Status: TODO
>
> Dependency: P4-08; P4-01 current evidence
>
> Primary lane: CLI / Backfill / Repository

## Mục tiêu

Backfill historical `CardProgress` into trusted mirror or audited quarantine while active mirrors protect concurrent writes.

## Công việc

1. Add a dedicated CLI/service; dry-run is default and apply is explicit.
2. Use stable keyset pagination over source identity; never OFFSET.
3. Persist immutable run metadata: code/schema/codec versions, source bounds, settings, started/completed time and evidence digest.
4. Recommended first rehearsal limits: maximum 250 source progress rows or 100 learner/Note subjects per transaction; tune only from measured MySQL evidence.
5. For each subject:
   - read sorted contributors and build canonical vector/hash;
   - acquire subject then contributor locks;
   - re-read and verify contributor identity/revision/hash and subject generation;
   - write trusted mirror or typed quarantine;
   - persist disposition and checkpoint in the same transaction.
6. Account single, equivalent state/distinct lineage, divergent, NULL, orphan, corrupt/unknown, reset/deleted and cutover/rekey cases.
7. Never reconstruct current state from history or create synthetic Notes.
8. Prove repeated runs are idempotent and a stale chunk cannot overwrite newer mirror generation.
9. Add kill/restart and injected failure at read, lock, upsert, disposition and checkpoint boundaries.
10. Export bounded redacted progress/results, not user content or raw secrets.

## Output

- Dry-run-first CLI and resumable service/repository.
- Run/checkpoint/disposition records.
- Accounting report and quarantine samples.
- Crash/resume/concurrency/idempotency tests.

## Acceptance

- `source rows = contributor rows accounted + explicitly unresolvable rows` for the frozen run bound.
- Every learner/Note has one deterministic outcome.
- No source state/history/provenance mutation.
- Checkpoint never advances past an uncommitted batch.
- Repeated/resumed run converges without duplicate rows.
- Concurrent review/import/reset/delete/rekey/new CardProgress cannot be lost or overwritten.

## Verification

```text
python scripts/run_tests.py --module study,database,cli,connect_mcp,decks --backend-only
```

Plus disposable MySQL crash/resume and two-connection concurrency suite.

## Rollback

Stop backfill, disable mirror flag if needed, retain run/checkpoints/dispositions, fix cause and resume or start a new versioned run. Product remains on `CardProgress`.

## Không làm

- Không run against production without P4-11 rollout approval.
- Không overwrite quarantine with guessed state.
- Không delete old or additive data.
