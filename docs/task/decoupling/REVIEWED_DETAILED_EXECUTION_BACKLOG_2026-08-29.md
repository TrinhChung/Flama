# Reviewed detailed execution backlog — Phase 0–3 decoupling

> P1/P2 closeout — 2026-09-08: [the execution report](./completed/P1_P2_EXECUTION_CLOSEOUT_2026-09-08.md) closes P1-03/P1-04 and P2-02..P2-07. This backlog retains the original cross-phase dependencies and historical records.

> Phase 3/INT-01 closeout — 2026-09-09: [the final execution report](./completed/PHASE_3_AND_INT_01_CLOSEOUT_2026-09-09.md) closes P3-01..P3-07 and INT-01. The remaining detail below is historical planning context.

> Review date: 2026-08-29
>
> Status: HISTORICAL; Phase 0–3 and INT-01 closed
>
> Scope: historical execution breakdown for P3-01 through P3-07 and INT-01

> Latest evidence review: [`docs/architecture/decoupling-progress-review-2026-08-30.md`](../../architecture/decoupling-progress-review-2026-08-30.md)
>
> Hard boundary: no Phase 4 model, migration, second progress authority, physical clone fallback or source Note/Card mutation

## 1. Verified current state

| State | Tasks | Evidence/next action |
|---|---|---|
| Completed and moved to `completed/` | P0-01..P0-04, P1-01..P1-04, P2-01..P2-07 | Code, handoffs and combined gates passed; async admission remains disabled by default and is not certified for production Redis/MySQL. |
| Completed 2026-09-09 | P3-05, P3-07 | Decisions accepted; see the architecture ADRs and final closeout. |
| Completed 2026-09-09 | P3-01–P3-06, INT-01 | Runtime, UI, real-overlay gate, and integration closeout passed. |

Latest local gate verification:

```text
python -m unittest tests.test_study_architecture_audit_cli tests.test_study_architecture_audit_service tests.test_study_behavior_acceptance_baseline
Result: 33 tests passed
```

The MySQL SELECT-only evidence is recorded separately in the completed P0-03 bundle.

## 2. Execution waves

```text
Wave 0  P0-03
   |
   +--> Wave 1A  P1-01
   +--> Wave 1B  P2-02 -> P2-03 -> P2-04 -> P2-05
   +--> Wave 1C  P3-05 decision -> P3-07 decision

P1-01 -> P1-02 -> P1-03 -> P1-04
P1-03 + P2-04 -> P2-06
P1-04 + P2-03 + P2-06 -> P2-07

P1/P2 gates + P3-05 + P3-07
   -> P3-01 -> P3-02 -> P3-03 -> P3-04 -> P3-06
   -> INT-01
```

Tasks sharing `study_session_service.py`, `useStudySession.ts` or composition contracts run sequentially. Do not merge independent-looking changes that create two transaction, restore or selection authorities.

## 3. Wave 0 — close Phase 0

### P0-03 — MySQL baseline verification

Status: `COMPLETED`; retained below as historical execution evidence.

| Slice | Detailed work | Required output |
|---|---|---|
| P0-03.1 | Read `CURRENT_USER()`, `DATABASE()` and grants without printing the URI; reject write, DDL or grant privileges | Redacted identity/schema/grant proof |
| P0-03.2 | Verify audit manifest digest and every listed file hash against the exact code state | Zero-mismatch manifest verification |
| P0-03.3 | Run `wsgi_audit.py` twice through the maintenance-disabled audit factory | Two raw candidate JSON artifacts and exit codes |
| P0-03.4 | Normalize only observation timestamps and compare recursively | Determinism report with empty semantic diff |
| P0-03.5 | Promote candidates, compute checksums and reconcile Markdown/JSON counts and warnings | One authoritative evidence bundle |
| P0-03.6 | Run audit, Study backend and Connect MCP focused suites | Command/result table |
| P0-03.7 | Review every warning disposition and publish GO/NO-GO | P0-03 handoff; move to `completed/` only on GO |

Stop on missing/unsafe grants, unexpected schema, audit `BLOCK`, non-timestamp drift or checksum mismatch.

## 4. Wave 1A — canonical backend review ownership

### P1-01 — Canonical native review transaction

Status: `COMPLETED`; P1-01.1 through P1-01.7 passed their output gate and the task moved to `completed/`.

| Slice | Detailed work | Required output |
|---|---|---|
| P1-01.2 | Define typed transport-neutral command/core input, result and errors; define explicit non-committing core contract | Approved types with no HTTP/MCP DTO leakage |
| P1-01.3 | Centralize policy serialization and extract transition, progress application, canonical event construction and side effects | One non-committing native mutation core |
| P1-01.4 | Keep direct REST/MCP adapters and existing response/error mapping around the shared core | Direct/MCP parity tests |
| P1-01.5 | Keep lease, sequence, idempotency, bulk locks and outer transaction in session service; delegate native writes to core | Batch no longer builds a second canonical event |
| P1-01.6 | Normalize first-progress insert, stale revision and suspension failures; inject failures after flush/side effects | Typed concurrency errors and atomic rollback proof |
| P1-01.7 | Remove obsolete builders/serializers and publish post-call graph | Search proof of one authoritative native builder |

Primary ownership: `study_service.py`, `study_session_service.py`, `study_policy_service.py`, REST/MCP adapters and Study/Connect tests.

Gate: REST, MCP and batch produce equivalent progress/canonical metadata; batch remains atomic/idempotent; no schema change.

### P1-02 — External progress revision/conflict contract

Status: `COMPLETED 2026-08-30`; handoff moved to [`completed/P1-02_EXTERNAL_PROGRESS_REVISION_CONTRACT.md`](./completed/P1-02_EXTERNAL_PROGRESS_REVISION_CONTRACT.md).

| Slice | Detailed work | Required output |
|---|---|---|
| P1-02.1 | **COMPLETED 2026-08-29** — inventoried snapshot, revlog, Connect, import, cutover, reset and repair mutators including locks, revisions, events and commit owner | Complete mutation table in the P1-02 task file |
| P1-02.2 | **COMPLETED 2026-08-29** — approved conflict matrix against direct/MCP/open batch sessions | Priority, revision and typed-result matrix in the P1-02 task file |
| P1-02.3 | **COMPLETED 2026-08-30** — response token/unversioned semantics, deterministic cutover locks, `max(revision)+1`, canonical cutover export and reset compatibility delegation landed | Updated mutation paths and provenance mapping |
| P1-02.4 | **COMPLETED 2026-08-30** — typed snapshot/legacy/revlog/reset/cutover assertions plus disposable MySQL 8.0.40 two-connection proof | No silent last-write-wins proof |

Gate: every external mutation detects newer state, preserves replay idempotency and never mutates source content.

### P1-03 — ReviewEvent provenance hardening

| Slice | Detailed work | Required output |
|---|---|---|
| P1-03.1 | Inventory every native/external ReviewEvent producer and existing payload variants | Before-producer inventory |
| P1-03.2 | Define versioned native, snapshot, revlog and repair provenance shapes | Canonical contract and bounded field policy |
| P1-03.3 | Add typed allowlist/range/depth/size validation and construct final event once | Shared builder/validator ownership seam |
| P1-03.4 | Classify legacy gaps without inferred data; update audit dispositions | Stable legacy categories |
| P1-03.5 | Test malformed/oversized payloads and native/external parity | No partial write and no false native provenance |

Gate: all new events meet the contract; legacy events remain readable; no event/schema backfill.

### P1-04 — Algorithm/decoder retirement lifecycle

| Slice | Detailed work | Required output |
|---|---|---|
| P1-04.1 | Inventory server executable, client evaluator and all wire/state/template decoders by exact version | Support artifact matrix |
| P1-04.2 | Define active, deprecated, lease-only and retired states plus retention inputs | Retirement ADR/runbook |
| P1-04.3 | Add server/client status introspection and stable unavailable behavior if needed | Exact-version support seam |
| P1-04.4 | Test new session, active old lease, restored retired session and historical readability | Cross-deploy compatibility matrix |

Gate: no latest-version fallback; supported leases survive; historical readability is not treated as replay support.

## 5. Wave 1B — frontend correctness

### P2-02 — Session mutation mutex

1. Inventory submit, undo, restore, retry, commit, auto-commit and conflict-recovery mutations.
2. Add one synchronous owner-token acquire/release boundary before every async operation.
3. Ensure stale `finally` cannot release a newer owner; cover error, abort and unmount.
4. Add same-tick conflict tests for every pair listed in the task.

Output: one mutex, stable busy result and concurrency matrix. Gate: never append/send duplicate mutations and no visual change.

### P2-03 — Restore validation and quarantine

1. Define supported current and legacy persisted event variants.
2. Validate identity, sequence, membership, action/trigger/rating, offset and policy before hydration.
3. Move invalid data atomically to a bounded, idempotent quarantine with stable non-content reasons.
4. Prove quarantined events never enter active state or commit payload.

Output: strict validator, reason enum, fixture matrix and integration proof. Gate: valid v2 restores; ambiguous history fails closed.

### P2-04 — Semantic interaction contract

1. Inventory controls/bottom-bar callers and define one semantic `ReviewAction` callback.
2. Remove the public raw-rating callback from reusable UI.
3. Keep action-to-rating mapping in one named compatibility adapter.
4. Add exact single-emission tests and verify reveal/disabled/undo behavior.

Output: semantic component API and adapter. Gate: zero visual regression and one gesture emits one action.

### P2-05 — Trusted keyboard decision

1. Document iframe/sandbox/origin/IME/forged-message threat model.
2. Compare no-bridge with any browser-enforced trusted mechanism; reject child claims/nonces/raw commands.
3. Implement only if browser-enforced trust is proven; otherwise record explicit no-bridge decision.
4. Verify parent, iframe, editable, IME, repeat and forged-message cases using an isolated Chrome profile.

Output: ADR plus safe implementation or accepted limitation. Gate: renderer content cannot select action/rating or cause progress writes.

## 6. Wave 1C — composition decisions

### P3-05 — Mixed-NoteType scope policy

1. Reconcile P0-03 empty/single/mixed distribution with repository examples.
2. Compare grouped, NoteType-first and single-NoteType-session options by UX, fairness, identity, overlay and old clients.
3. Decide session cardinality, deterministic ordering, default/empty behavior and progress-subject set.
4. Define API grouping/errors and frontend launch states for owned/overlay/local-added scopes.

Output: approved ADR and API/UI contract. Gate: no hidden “one Deck = one NoteType” assumption and no ambiguous fallback.

### P3-07 — Applied composition/binding contract

1. Approve responsibility/identity model for reusable definition, version, inputs, application, occurrence and compatibility ID.
2. Define direct `FieldDef.id` binding validation and explicitly defer unsupported transformations.
3. Define version/pin/fork/unpublish/detach/delete and authorization lifecycle.
4. Define legacy Template/Card, overlay, import, Anki/Connect projection and P3-04 frozen material.
5. Compare alternatives without selecting SQL/table layout.

Output: approved logical ADR and error/lifecycle matrices. Gate: repeated application does not create progress; rename-safe IDs and overlay invariants hold.

## 7. Wave 2 — Trigger and wire convergence

### P2-06 — Built-in Trigger Runtime design

1. Trace semantic Action to Algorithm flow after P1-03/P2-04.
2. Define one transaction owner and built-in exact-version Trigger input/result/errors.
3. Define primary versus follow-up effects, ordering, retries, idempotency and cycle prevention.
4. Compare permanent adapter versus minimal dispatcher and split any approved runtime work into a separate bounded implementation slice.

Output: ADR, sequence flow and version/error matrix. Gate: no arbitrary handler/custom automation and unknown versions fail closed.

### P2-07 — Wire v3 and v2 lease compatibility

1. Freeze v2 shapes and define discriminated v3 Action/Trigger/Algorithm/event identities.
2. Add exact-version Python/TypeScript validators and dispatch.
3. Roll out v3 creation while retaining measured v2 restore/commit support.
4. Test old/new client-server combinations, retired versions and rollback window.

Output: v3 schema, v2 handler, telemetry and rollout runbook. Gate: no heuristic conversion/fallback and active v2 leases remain valid.

## 8. Wave 3 — Phase 3 implementation

### P3-01 — Exactly-one composition API

Replace optional list input with one authorized resolved selection, fail closed for malformed/unauthorized/out-of-scope/ambiguous cases, and preserve only the approved old-client fallback. Output: request/error contract and authorization tests.

### P3-02 — Clone-aware query-first discovery

Build one effective-scope resolver for discovery and session query; map source/local presentation identities; apply selection before the session limit; preserve scheduler ordering and overlay-only behavior. Output: shared resolver and owned/source/local/mixed tests.

### P3-03 — Pre-session selection UI

Implement discover → resolve/select → open → active state machine; never open before selection; remove client-side filtering as authority; preserve active Study visuals. Output: launch state machine and zero-regression tests.

### P3-04 — Frozen composition restore

Freeze the selected application, legacy Template, bindings/fingerprints and runtime versions in existing snapshot JSON; restore from frozen material; reject mismatched commit and unsupported versions. Output: cross-language snapshot/restore tests with no migration.

### P3-06 — Real overlay-only exit gate

Replace physical clone simulation with a real published `DeckInstall`, source cards and local-added cards; prove discovery, selection, session, restore, authorization, no copying and no source mutation. Output: backend/frontend exit matrix and evidence summary.

## 9. Wave 4 — INT-01 closeout

1. Review diffs by task ownership and reject unrelated/schema work.
2. Search for duplicate builders/serializers, raw ratings, iframe commands, premature session open, client-only filtering, physical clone fixtures and second progress authorities.
3. Run direct/MCP/batch/external, mutex/restore/security, version and real-overlay flows.
4. Reconcile SQLite and accepted MySQL audit evidence.
5. Move only fully accepted tasks into `completed/`, update tracker links and publish Phase 4 GO/NO-GO recommendation.

Gate: every task has its required output and evidence; no waived dependency is hidden in prose.

## 10. Verification matrix

| Change area | Minimum command |
|---|---|
| Backend Study/session/event | `python scripts/run_tests.py --module study --backend-only` |
| Frontend Study/session/UI | `python scripts/run_tests.py --module study --frontend-only` |
| MCP/Connect/import | `python scripts/run_tests.py --module connect_mcp --backend-only` |
| Overlay/decks/flashcards | `python scripts/run_tests.py --module decks,flashcards --backend-only` |
| Task handoff | `python scripts/run_tests.py --changed` |
| Integration/pre-release only | `python scripts/run_tests.py --all` |

## 11. Per-task completion protocol

For each task:

1. Confirm dependencies and exclusive file ownership.
2. Record before evidence and the exact invariant being changed.
3. Implement only the listed slices.
4. Run the narrowest tests, then changed-file tests.
5. Review diff, transaction/storage/overlay/security boundaries and unrelated files.
6. Add a handoff block with files, contract changes, commands/results, rollback, limitations and next IDs.
7. Change status to `COMPLETED`, move the Markdown file to `completed/`, repair links and commit only that task's files.

Do not mark a preparation slice, green test count or documentation-only inventory as completion of its parent runtime task.
