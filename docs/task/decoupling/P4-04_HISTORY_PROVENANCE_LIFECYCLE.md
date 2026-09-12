# P4-04 — History, provenance and lifecycle contract

> Phase: 4
>
> Priority: P0 decision
>
> Status: IN PROGRESS / PROVISIONAL — logical ADR drafted; current MySQL distribution captured, while P4-01 schema remediation and joint decision gates remain open
>
> Dependency: P4-01; consistency with P4-02/P4-03
>
> Primary lane: Study history / Connect / Lifecycle

## Mục tiêu

Chốt evidence cần giữ cho migration, future history initializer và reset/delete/rekey mà không biến `ReviewEvent` thành current-state authority.

## Công việc

1. Classify native history, Anki revlog, external state snapshots, clone cutover/repair and destructive lifecycle commands.
2. Define per-contributor event pointer and external reference accounting; equivalent state does not imply one winner history pointer.
3. Define `history_completeness` and provenance vocabulary for native-complete, imported-partial, snapshot-only, repaired, unknown and detached cases.
4. Specify minimum chronological scheduler-grade facts/summary needed after the approved 30-day detail-retention phase.
5. Define future initializer input/fallback contract for incomplete history without implementing Algorithm switching.
6. Define reset tombstone/generation, Note deletion, Template/Card cascade, deck deletion, seed replacement, import reconciliation and clone rekey outcomes.
7. Preserve historical IDs/snapshots when current Card/Note relations disappear; define FK versus detached-ID trade-offs.
8. Confirm revlog remains history-only under P1-02.

## Output

- Accepted history/provenance/lifecycle ADR.
- Completeness and lifecycle state machine.
- Current writer/delete path matrix.
- Minimum retained scheduler history contract for Phase 7.
- Phase 5 initializer handoff requirements.

## Progress — 2026-09-12

The repository-grounded [P4-04 provisional ADR](../../architecture/phase-4-history-provenance-lifecycle-adr-2026-09-12.md) now defines:

- separate provenance and conservative history-completeness vocabularies;
- per-contributor pointer/external-reference accounting with no fan-in winner;
- minimum scheduler-grade facts retained beyond execution detail;
- reset, Card/Template/Note deletion, import replacement and clone rekey transitions;
- tombstone/detached retention gates and the future Phase 5 initializer handoff.

Runtime change: none. Schema change: none. The production snapshot found 15,992 valid latest-event pointers, 432 null pointers, no invalid/cross-subject pointer, and complete source/ref accounting. Acceptance remains blocked by P4-01 schema remediation, the independent `study_session_batches` migration disposition and joint P4-02/P4-03/P4-04 review.

## Acceptance

- Current state never reconstructed from incomplete events during backfill.
- All event/source references have an accounting rule through reset/delete/rekey.
- Phase 4 stores enough evidence to explain every mirror/quarantine result.
- No detail purge, authority cutover or actual Algorithm switch occurs.

## Verification

Cross-review against `ReviewEvent`, Connect refs, P1-02, session history, clone cutover and all bulk-delete callsites. Runtime change: none.

## Rollback

ADR can be superseded before schema approval. Once provenance statuses are persisted, new semantics must be additive and old codes remain readable.
