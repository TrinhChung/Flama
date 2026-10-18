# P4-07 — Native, session and worker transactional mirror

> Phase: 4
>
> Priority: P0
>
> Status: **IMPLEMENTED / LOCAL VERIFIED — COMMITTED ON DEVELOP (`bd96abc`)**
>
> Dependency: P4-06
>
> Primary lane: Study service / Session / Worker

## Mục tiêu

Mirror all native authoritative mutations once per learner/Note inside the existing transaction without changing current scheduler/revision/receipt behavior.

## Công việc

1. Add a shared no-commit coordinator with explicit prepare/lock/finalize phases.
2. Determine affected learner/Note subjects and acquire the approved subject lock before CardProgress locks.
3. Cover direct REST and MCP through the canonical native command.
4. Cover synchronous session commit after all replayed events, final CardProgress state and `last_review_event_id` are flushed.
5. Cover async worker before DB commit; standardize deterministic lock ordering where needed.
6. Finalize once per learner/Note, not once per replayed event; preserve current per-Card revision semantics.
7. Preserve session commit receipts, duplicate client events, worker Redis processed marker order, retry and DLQ behavior.
8. For fan-in divergence, write quarantine/disposition and contributor vector in the same transaction while allowing the valid authoritative review.
9. For unexpected SQL/codec/serialization failure with mirror enabled, rollback the existing authoritative unit.
10. Add first-create, sibling-Card, concurrent session/direct/MCP, duplicate delivery and fault-injection tests on MySQL.

## Output

- Reusable mirror coordinator with no internal commit.
- Native/session/worker adapters.
- Lock-order documentation and observability counters.
- Atomicity/idempotency/concurrency tests.

Implementation and verification evidence: [Phase 4 native/session/worker mirror verification](../../architecture/phase-4-native-session-worker-mirror-verification-2026-09-13.md).

## Acceptance

- Flags off preserves byte/behavior-compatible current path.
- Flags on commits CardProgress, ReviewEvent/session receipt and mirror atomically.
- Final mirror includes final event pointers and every contributor.
- Same Note sibling writes cannot deadlock or silently overwrite mirror generation.
- Retry/duplicate delivery creates no duplicate generation or trusted stale mirror.

## Verification

```text
python scripts/run_tests.py --module study,connect_mcp --backend-only
```

Plus two-connection MySQL race/deadlock/failure-injection suite.

## Rollback

Disable mirror flag; keep `CardProgress` and session/worker behavior authoritative. Retain mirror rows for diagnosis.

## Không làm

- Không enable shadow reads.
- Không change wire version or review semantics.
- Không route MCP to generic Actions.
