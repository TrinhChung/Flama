# Phase 4 native/session/worker mirror verification

> Date: 2026-09-13 | Task: P4-07 | Mode: IMPLEMENTATION
>
> Status: **IMPLEMENTED / LOCAL VERIFIED — UNCOMMITTED**
>
> Authority: `CardProgress` and `ReviewEvent` remain authoritative; shadow reads remain disabled

## Outcome

P4-07 adds one transaction-neutral coordinator for the native review writers. Direct REST and MCP enter through `execute_native_review_command`; synchronous session commit and the asynchronous worker prepare the same learner/Note subjects before locking progress, retain every new scheduler-grade ReviewEvent fact, and finalize each affected Note once after final progress and event pointers are flushed.

The feature remains default-off through `STUDY_PROGRESS_SHADOW_WRITE_ENABLED`. The coordinator never commits or rolls back. Existing transaction owners retain those responsibilities.

## Invariants preserved

- Subject identity is exactly `(learner_user_id, Note.id)`, including logical-overlay study where the learner does not own the source Note.
- The transaction-owner prefix lock remains first: StudySession/worker batch and session coordination precede learner/Note locks.
- Subject rows are created/locked in binary learner/Note order before all current sibling `CardProgress` rows are locked in Card/progress order.
- `CardProgress` remains the current-state source. `ReviewEvent` contributes pointer/history evidence but is never replayed to rebuild current state.
- Session batches keep one CardProgress revision per touched Card and one mirror revision per affected Note, regardless of the number of replayed events.
- State-equivalent fan-in retains every contributor and separately hashed lineage. State-divergent fan-in removes the usable shadow state and records `QUARANTINED_STATE_DIVERGENCE` while the valid authoritative review still commits.
- Expected mapping failures become a typed quarantine when bounded raw evidence can be retained. Unexpected SQL, serialization, hash, or invariant failures escape the coordinator and roll back the authoritative unit.
- Duplicate session receipts and worker deliveries do not add a mirror revision or a second history fact.

## Alternatives considered

| Alternative | Benefit | MySQL/SQLAlchemy cost | Decision |
|---|---|---|---|
| Finalize after each ReviewEvent | Small call-site adapter | Incorrectly increments Note mirror revision for multi-event sessions, repeatedly rewrites contributor vectors, and enlarges lock time | Rejected |
| Prepare/lock once and finalize once per transaction/Note | Preserves existing Card revisions, receipts and batch semantics; gives one complete final vector | Requires transaction owners to pass flushed events and use the coordinator's progress locks | Selected |
| Best-effort shadow write outside the authority transaction | Lower request latency and no authority rollback on mirror failure | Can publish stale generations, lose event pointers, and break receipt/mirror atomicity | Rejected |

## InnoDB isolation finding

The first disposable-MySQL race found a real `REPEATABLE READ` issue: non-locking ORM reads performed after a contending subject insert could retain an older consistent snapshot and fail to observe the contributor just committed by the preceding writer. That caused an attempted duplicate `live_card_progress_id` insert even though the subject lock serialized the writers.

The final implementation uses current/locking reads (`SELECT ... FOR UPDATE`) for finalization-critical subject contributors, usable state, availability, lineage refs, pointed ReviewEvents and history deduplication. This is necessary in MySQL; SQLite tests cannot reproduce the snapshot behavior. The second probe passed with concurrent synchronous-session, direct-REST and MCP writers against sibling Cards of one Note.

## Runtime call-site matrix

| Owner | Prefix and prepare point | Finalize point | Provenance |
|---|---|---|---|
| native direct REST | no pre-existing owner row; prepare before progress lock | after event ID and latest pointer flush, before command commit | `NATIVE_DIRECT` |
| native MCP | same canonical native command as REST | same finalizer | `NATIVE_MCP` |
| synchronous StudySession | locked StudySession first; prepare after event validation and before progress locks | after all events, final states, pointers, receipt/audit staging; before commit | `NATIVE_SESSION` |
| asynchronous worker | Redis batch/session locks and locked StudySession first; prepare before progress locks | after all events, final states and pointers; before batch/receipt commit | `NATIVE_ASYNC_BATCH` |

## Stored evidence

Each successful material review updates the subject envelope and complete current contributor vector, one usable state only when fan-in is trusted, per-contributor availability, current latest-event lineage, and one deduplicated `study_progress_history_facts` row per new ReviewEvent. Existing unproven history remains `HISTORY_UNKNOWN`; a first native progress created inside the observed generation is `HISTORY_NATIVE_COMPLETE`.

Process-local counters are exposed under `current_app.extensions["study_progress_shadow_mirror_metrics"]` for prepare attempts, finalized status codes and internal failures. Structured finalization logs include only counts/statuses, not learner answers or secrets.

## Verification

- `python -m unittest tests.test_study_progress_shadow_mirror -v`: 7/7 passed, covering flag-off, first create, REST, MCP, sibling fan-in divergence, multi-event session idempotency, worker duplicate delivery and rollback fault injection.
- `python scripts/run_tests.py --module study --backend-only`: 187 tests passed across 20 suites, including the registered P4-07 suite.
- `python scripts/run_tests.py --module connect_mcp --backend-only`: 166 tests passed.
- `python scripts/run_tests.py --changed --backend-only`: 256 tests passed across 33 database, study and tooling suites.
- `python scripts/probe_phase4_shadow_mirror_mysql.py`: passed on a disposable database which was dropped afterward. Three concurrent writers completed without deadlock; final generation/revision/contributor count was `3/3/3`; async worker status was `completed`; injected failure left no authoritative or shadow write.

The MySQL probe creates only a randomly named database matching `flama_p4_shadow_probe_*`, validates the exact target before deletion, disposes application connections, and drops the database in `finally`.

## Rollout and next boundary

Do not enable shadow writes in production yet. P4-08 must first adapt external progress snapshots/imports, reset, Card/Template/Note deletion, seed replacement and clone cutover/rekey to the same subject-before-progress order and lifecycle fences. Until then, the safe rollback remains leaving `STUDY_PROGRESS_SHADOW_WRITE_ENABLED=false`; all user-facing reads continue to use `CardProgress`.
