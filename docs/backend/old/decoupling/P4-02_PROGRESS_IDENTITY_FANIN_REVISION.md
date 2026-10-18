# P4-02 — Learner/Note identity, fan-in and revision contract

> Phase: 4
>
> Priority: P0 decision
>
> Status: **COMPLETED / ACCEPTED** — joint logical review and production P4-01 gate closed on 2026-09-13
>
> Dependency: P4-00 and P4-01
>
> Primary lane: Data architecture

## Mục tiêu

Chốt logical subject, contributor accounting, quarantine và concurrency contract trước khi tạo physical row.

## Công việc

1. Define logical identity for owned Note, installed source Note and installed local-added Note. Separate learner identity from source author/installer ownership.
2. Compare at least:
   - collapse current Cards directly into one Note row;
   - retain a Note envelope plus explicit CardProgress contributors.
3. Define contributor vector including progress/card identity, revision, canonical raw hash, event pointer and external provenance.
4. Define buckets: no-current-progress, single, equivalent state/distinct lineage, divergent, NULL, orphan, reset/deleted, cutover/rekey, unsupported/corrupt.
5. Prohibit winner selection by latest timestamp, max counter, max revision or average state for ordinary fan-in.
6. Define monotonic subject generation/revision and reset/delete/rekey tombstone fencing while `CardProgress.revision` stays unchanged.
7. Define lockable learner/Note coordination and global lock order before CardProgress locks; include first-create, sibling Cards and different learners sharing one source Note.
8. Define expected quarantine versus unexpected mirror failure behavior.
9. Map existing P1-02 conflicts onto Note mirror without reopening its product rules.

## Output

- Accepted ADR with identity/cardinality/ownership/lifecycle tables.
- State-vs-lineage equivalence definition.
- Lock order and race matrix.
- Quarantine/disposition/error codes.
- Owned/overlay/reset/rekey examples.

## Completion handoff — 2026-09-13

- Accepted design ADR: [Phase 4 learner/Note identity, fan-in and revision](../../architecture/phase-4-progress-identity-fanin-revision-adr-2026-09-10.md).
- Accepted logical key: exactly `(CardProgress.user_id, Card.note_id)`; Template, Card, deck, install, source owner and external IDs remain contributor/context/provenance material.
- Accepted storage direction: lockable learner/Note envelope plus explicit contributor rows. The exact physical design is owned by [P4-05](../../architecture/phase-4-physical-shadow-schema-adr-2026-09-13.md); this task itself creates no schema.
- Ordinary fan-in has no winner. Single and semantically equivalent fan-in may be mirrored while preserving all contributor/lineage evidence; divergent/unsupported/corrupt fan-in is quarantined.
- `subject_generation` fences topology/reset/delete/rekey/backfill, while `mirror_revision` versions only the derived projection. Per-Card `CardProgress.revision` remains the sole current scheduler conflict token.
- Accepted global order: existing transaction-owner/Connect source-identity prefix locks, sorted subject coordination locks, sorted CardProgress contributor locks, authoritative mutation/event flush, then one mirror finalization per subject. P1-02 local/source order is preserved inside the contributor stage, never before subject locks.
- P1-02 result codes are mapped without changing their apply/no-op/conflict semantics.
- Runtime/schema change: none.
- [P4-03](../../architecture/phase-4-algorithm-state-availability-adr-2026-09-12.md) defines the exact raw/state codecs, `algorithm_state_hash`, availability/control anchors and resulting `semantic_state_hash` used by this fan-in contract.
- [P4-04](../../architecture/phase-4-history-provenance-lifecycle-adr-2026-09-12.md) defines lineage completeness, retained scheduler facts and reset/delete/rekey fence retention.
- The refreshed production snapshot found 16,424 single-contributor learner/Note groups and zero fan-in, quarantine, unresolvable or overlapping-context groups at matching head `20260913_000038` with zero drift.
- The [joint acceptance record](../../architecture/phase-4-logical-contract-joint-acceptance-2026-09-13.md) closes all logical consistency gates. MySQL race proof remains correctly assigned to P4-11 rather than being treated as an unresolved design choice.

## Acceptance

- Every current progress row can be accounted without silent merge.
- A valid review that creates fan-in divergence preserves the CardProgress write and atomically marks mirror untrusted.
- Unexpected mirror failure rolls back the authoritative unit when mirror is enabled.
- Stale backfill cannot cross reset/delete/rekey/new-contributor generation.
- No Phase 5 authority rule is introduced.

## Verification

Architecture cross-review against models, audit queries, P1-02, clone cutover and MySQL evidence. Runtime change: none.

## Rollback

ADR can be superseded before P4-05. After schema rollout, identity/generation changes require a new additive migration and reconciliation plan.
