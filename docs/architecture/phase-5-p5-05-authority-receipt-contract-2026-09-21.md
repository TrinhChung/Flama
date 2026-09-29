# P5-05 — durable NOTE authority command receipt

> Superseded implementation status: the receipt foundation is now integrated by [Study Session v4 and explicit enrollment/rollback](./phase-5-p5-05-session-v4-contract-2026-09-22.md). This file remains the detailed receipt design record.

> Date: 2026-09-21 | Mode: IMPLEMENTED / INERT | Status: **PARTIAL**. The durable receipt foundation is complete for the existing-state NOTE command. Wire v4, frontend persistence/restore, worker pinning and product-route integration remain open. Migration 41 does not admit NOTE enrollment.

## Decision and scope

An accepted NOTE Action needs a durable replay identity that is independent of presentation Card, session lifetime and transport. Three storage choices were reviewed:

| Choice | Result |
|---|---|
| Reuse `StudySessionCommit` | Rejected: it permits only one commit per session and its response is session-scoped. Direct REST, MCP and worker operations cannot share that lifetime safely. |
| Treat `ReviewEvent.client_event_id` as the receipt | Rejected: current events allow nullable/multiple provenance shapes and do not preserve the exact accepted response or request fingerprint. |
| Add one authority-command receipt | Chosen: one transport-neutral operation key, exact request fingerprint, accepted revision/hash transition, event/fact links and immutable replay response. |

`study_authority_command_receipts` is additive. The unique identity is `(learner_user_id, SHA-256(operation_key bytes))`; the original key is also retained and compared to detect an impossible hash collision. A receipt is additionally unique by `review_event_id` and `history_fact_id`, so one accepted Action cannot acquire two receipts. Subject ID is nullable only for later lifecycle deletion, while logical Note key, generation and enrollment epoch remain durable replay context.

This receipt is intentionally separate from `StudySessionCommit`. A future wire adapter may store its session response in the generic authority receipt, but must not reinterpret an existing v2/v3 session receipt.

## Exact replay contract

`apply_idempotent_existing_state_note_review` requires a canonical UTF-8 operation key of at most 512 bytes. It must equal the canonical event provenance `request_id`, or `client_event_id` when no request ID exists. The SHA-256 request fingerprint covers:

- receipt schema, learner, logical Note key, subject generation and enrollment epoch;
- expected authority revision and 32-byte semantic state hash;
- compatibility Card ID, exact current/next Algorithm State and runtime transition metadata;
- reviewed time, normalized duration, payload, deck/config/timezone/review-mode context;
- effective NoteType and complete native provenance.

The lookup runs after the caller has acquired the learner/subject lock prefix but before NOTE CAS verification. This ordering is required: an exact retry arrives after the first commit advanced the authority revision, so checking CAS first would incorrectly reject the replay. The outcomes are:

1. no receipt: execute the canonical P5-04 command, flush event/fact, then stage response and receipt in the same caller-owned transaction;
2. same key and same fingerprint/context: return the hash-verified stored response without a state write, event, fact or revision increment;
3. same key with another fingerprint: fail `AUTHORITY_OPERATION_REUSED`;
4. hash/key, epoch/generation/subject, decoder or response hash mismatch: fail closed with a typed receipt error.

Helpers never commit or roll back. Receipt serialization/finalization failure therefore rolls back state, token, every sibling projection, event, fact, lineage and receipt at the existing transaction owner.

## Schema and rollout safety

Alembic `20260921_000041` creates only the receipt table and requires the Phase 4/P5 parent tables. Upgrade is idempotent only when an existing table exactly matches the ORM contract. Downgrade is refused when any receipt exists. It does not widen `ck_study_authority_legacy_only`, create enrollment rows, add a route, or change product reads/writes.

The product owner has approved eventual full NOTE enablement to prioritize release because current data is predominantly test data. That removes live-volume as a rollout blocker; it does not make a partially wired mode safe. The CHECK-widening migration should land with the first end-to-end mode-aware writer/reader slice, after route/wire/side-effect coverage prevents a database row from claiming NOTE while the runtime still serves legacy authority.

## Evidence and remaining work

- Exact commit/replay, divergent key/provenance reuse, corrupt stored-response detection and injected receipt-failure rollback pass in SQLite.
- Five schema tests cover FK/unique metadata, idempotent exact upgrade, incompatible pre-existing table rejection and empty-only downgrade.
- The registered study backend matrix passes **281 tests across 31 files** (279-run baseline plus the two final receipt failure cases, which also pass in the focused run).
- Disposable MySQL **8.0.40** passes head `20260921_000041`, exact table contracts, empty 41→40→39 downgrade/re-upgrade, flags-off WSGI boot, receipt commit and exact replay with unchanged event/fact/receipt counts. The configured application database is not modified.

The immutable Note/epoch v4 envelope, v2/v3 fallback, frontend durable restore/replay, synchronous route integration and native side effects are now implemented. P5-05 remains open only for async v4 rollover worker semantics. First-state materialization, cross-subject same-key race handling, overlay/external lifecycle integration, broader fault injection and the production-version rehearsal remain later gates. No production NOTE enablement is authorized by this receipt record.
