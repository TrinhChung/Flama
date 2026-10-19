# P4-09 — Resumable, fenced learner/Note shadow backfill

> Phase: 4
>
> Priority: P0 data gate
>
> Status: **IMPLEMENTED / LOCAL VERIFIED — UNCOMMITTED**
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

Implementation and verification evidence: [Phase 4 resumable backfill verification](../../architecture/phase-4-resumable-backfill-verification-2026-09-14.md).

## Completion handoff — 2026-09-14

- Added `flask study-progress-backfill`; it is read-only by default and requires explicit `--apply`. The default-off backfill gate admits both modes, while apply additionally requires the mirror-write gate so concurrent writers participate in the same subject fence.
- Apply freezes repository/database/mapper/state/projection identities plus the CardProgress high-water mark and source count in one versioned run contract. Resume refuses a changed code/schema/settings digest.
- Source traversal is stable `CardProgress.id` keyset pagination with fixed initial limits of 250 source rows and 100 learner/Note subjects per transaction. No OFFSET path exists.
- Each batch observes the complete subject authority vector, expires observation-only ORM state, locks every subject in canonical order, locks/reloads contributor rows, and compares generation, mirror revision, source identity/revision/raw hash and full authority vector before finalization.
- Disposition writes and checkpoint advancement share the mirror transaction. Injected failures at read, lock, upsert, disposition and checkpoint boundaries leave the cursor before the failed batch.
- `RETRY_PENDING` retains a stale observed source until a fresh CAS succeeds. If reset/delete/rekey removes that row, retained contributor/lifecycle evidence produces a typed tombstone/detach/rekey disposition instead of resurrecting state.
- Current progress only is in scope. No `ReviewEvent` is replayed, no synthetic Note is created, and neither source Note/Card content nor `CardProgress` is mutated by the backfill.
- SQLite coverage passes dry-run, keyset resume, idempotent completed replay, fan-in divergence, NULL Card, unclassified/logical-overlay context, every fault boundary, stale revision, concurrent contributor creation and reset.
- Disposable local MySQL migration `000038 -> 000039` passes crash/resume, completed replay, two-connection Card-create/reset races and deadlock-free generation/vector CAS. No production run, commit, push or merge is part of this handoff.

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
