# P4-08 — External sync and lifecycle transactional mirror

> Phase: 4
>
> Priority: P0
>
> Status: **IMPLEMENTED / LOCAL VERIFIED — UNCOMMITTED**
>
> Dependency: P4-07
>
> Primary lane: Connect / Import / Deck lifecycle / Share cutover

## Mục tiêu

Extend the same learner/Note mirror contract to every non-native mutation, reset, rekey and destructive lifecycle path while preserving existing P1-02 conflict and savepoint semantics.

## Công việc

1. Modern Anki progress snapshot:
   - mirror only applied/forced material changes;
   - preserve source hash and applied-local-revision atomically;
   - duplicate/no-op/conflict/unresolved does not mutate trusted mirror.
2. Legacy `importCards`/package import:
   - mirror inside current per-note savepoint;
   - preserve partial package success and media compensation;
   - use external snapshot provenance, not native Action semantics.
3. Revlog import:
   - keep history-only current-state rule;
   - update contributor/history accounting only when required by P4-04.
4. Reset:
   - resolve all owned + installed-source/local subjects before delete;
   - cancel sessions and advance mirror tombstone/generation atomically.
5. Clone cutover/rekey:
   - capture old→new progress/Card/Note mapping;
   - preserve final authoritative merge result and provenance;
   - do not reuse cutover “newest wins” for ordinary fan-in.
6. Cover deck/note/card/template delete, MCP delete, Browse/content bulk delete, seed replacement and import template reconciliation.
7. Do not rely on ORM callbacks for bulk operations.
8. Use the global subject→CardProgress lock order across external/native paths.
9. Add unexpected mirror failure rollback and expected quarantine tests for each transaction/savepoint owner.

## Output

- External/lifecycle adapters using the shared coordinator.
- Complete current writer/delete coverage matrix.
- Reset/rekey/tombstone and partial-success tests.
- Real logical-overlay source/local-added evidence.

Implementation and verification evidence: [Phase 4 external/lifecycle mirror verification](../../architecture/phase-4-external-lifecycle-mirror-verification-2026-09-14.md).

## Completion handoff — 2026-09-14

- Modern and legacy Connect snapshots finalize only applied current-state changes and retain source Card/Note lineage; no-op, conflict and unresolved results do not advance a trusted mirror.
- Revlog creates normalized `CONNECT_REVLOG` facts only, preserves `CardProgress` revision/pointer/current state and classifies mixed snapshot/history conservatively.
- Reset, Card/Template/Note/deck delete, MCP/browse bulk delete, seed replacement and import reconciliation use one no-commit lifecycle adapter with generation fences and retained contributor/history evidence.
- Clone cutover locks all old/new subjects before P1-02 progress locks, mirrors only the committed destination authority and retains paired rekey lifecycle rows without mutating source Note/Card content.
- Generation rollover now keeps old contributor rows immutable, so prior history facts cannot silently point at a contributor moved into a newer epoch.
- The requested backend matrix passed 755 tests across 68 files. Disposable local MySQL passed external savepoint rollback, multi-subject reset/delete, post-reset generation and native-vs-external race checks; the existing P4-07 MySQL fan-in/worker/fault probe also remains green.
- `STUDY_PROGRESS_SHADOW_WRITE_ENABLED` remains default-off. No shadow reads, backfill, production change, commit, push or merge are part of this handoff.

## Acceptance

- Every material CardProgress create/update/delete/rekey has a mirror/disposition outcome.
- P1-02 typed conflict/no-op/force behavior is unchanged.
- Revlog never executes scheduler or overwrites current state.
- Reset cannot be overwritten by stale backfill with reused low revisions.
- Bulk deletes cannot leave a trusted mirror pointing at deleted contributors.
- Source Notes/Cards are not mutated by install/overlay operations.

## Verification

```text
python scripts/run_tests.py --module connect_mcp,decks,flashcards,seed,study --backend-only
```

Plus disposable MySQL savepoint, reset/delete and native-vs-external race tests.

## Rollback

Disable mirror flag. Existing external conflict/savepoint/reset/cutover behavior continues on `CardProgress`; retain dispositions for diagnosis.
