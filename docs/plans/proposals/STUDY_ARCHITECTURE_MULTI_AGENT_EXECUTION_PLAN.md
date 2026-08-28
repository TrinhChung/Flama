# Study Architecture Multi-Agent Execution Plan

Status: proposed execution backlog  
Last reviewed: 2026-08-28  
Primary architecture reference: `docs/architecture/study-interaction-trigger-algorithm-plan.md`

## 1. Purpose

This document turns the remaining Study, Interaction, Trigger, Algorithm, and Progress architecture work into small assignments that can be executed by multiple agents without overlapping ownership.

It is an execution plan, not authorization to redesign the domain or start Phase 4 database work. Every agent must preserve current study behavior and report any discovered architectural mismatch before expanding its scope.

## 2. Current implementation baseline

The implementation is not at a clean phase boundary yet:

- Phases 0-2 have working compatibility slices, but their exit gates remain partial.
- Phase 3 has composition scaffolding, a scope API, session composition snapshots, and a frontend selector. The current path is still compatibility-oriented: selection does not yet cleanly own session creation and the model does not yet prove reusable NoteType/Template/Field bindings.
- Phase 4 has not started. `CardProgress` remains the sole progress authority.
- Phases 5-9 have not started.
- Cleanup order 1 is complete.
- Cleanup orders 2 and 3 require renewed hardening despite earlier partial completion claims.
- Cleanup order 4 is partial.
- Cleanup orders 5 and 6 remain open.

Important review findings that define the next work:

- Batch review still duplicates part of `ReviewEvent` construction and side-effect orchestration instead of delegating completely to one review command boundary.
- Scheduler-policy serialization still has duplicate representations.
- The first `CardProgress` creation path has an untyped race condition; some REST reads preload progress without the lock used by the write command.
- Restore normalization exists, but restored server events can still accept malformed identity or sequence data, including non-UUID IDs, gaps, duplicate IDs, and invalid offsets.
- The frontend operation ref behaves as an activity marker, not a synchronous mutex; same-tick submit/undo/restore overlap is possible.
- The extracted interaction control still supports dual raw-rating and semantic-action callbacks.
- Keyboard behavior while focus is inside the sandboxed renderer is unresolved.
- The Study Mode selector currently highlights a choice around an already-opened session; the selection is not yet the authoritative input to session creation.
- Composition endpoint authorization and ownership checks need explicit proof.
- Current clone composition coverage uses physical test copies and does not prove the real overlay-only installed-deck path.

## 3. Non-negotiable guardrails

All assignments in Waves 1-3 must obey these constraints:

- Do not add or modify database models or migrations.
- Do not modify production data or startup schema repair.
- Keep `CardProgress` as the only authoritative progress source.
- Do not begin Phase 4 generic progress/state persistence.
- Preserve current four-rating behavior, interval previews, undo behavior, study ordering, and session compatibility.
- Preserve the overlay-only shared-deck model; never reintroduce full-copy clone behavior.
- Keep v2 request compatibility unless the assignment explicitly introduces an additive validation rule.
- Template JavaScript must not receive direct progress-write APIs.
- Do not broaden a cleanup task into a new Trigger Runtime or Algorithm redesign.
- Agents working in the shared worktree must not commit, reset, discard, or reformat unrelated changes.
- Coding agents report changed files, tests run, failures, and unresolved risks. The integration agent alone updates the canonical progress documentation.

## 4. Execution order

```text
Wave 1A: backend review boundary ─┐
Wave 1B: frontend session safety ├─> Wave 2: contract + iframe hardening
Wave 1C: restore validation ──────┘

Wave 1 gate ─> Wave 3: composition backend/frontend
Wave 3 gate ─> Wave 4: audit and ReviewEvent hardening
Wave 4 gate ─> Wave 5: Trigger Runtime design only
All gates ───> final integration review and plan status update
```

Only Wave 1A, 1B, and 1C should run concurrently in the first batch. Later waves should begin only after the listed gate is satisfied.

## 5. Wave 1 — Close correctness gaps in current compatibility paths

### Agent A — Canonical backend review transaction boundary

Suggested task name: `backend_review_boundary`

Objective: ensure REST, MCP, and batch review use one transaction owner for progress mutation, event persistence, scheduler-policy identity, and side effects.

Primary ownership:

- `app/services/study_service.py`
- `app/api/learning/study.py`
- MCP review service/route files discovered from the current call graph
- batch commit service files discovered from the current call graph
- the narrow backend tests for review, batch commit, idempotency, and concurrency

Tasks:

1. Trace every native review write entry point from HTTP/MCP/batch to `CardProgress` and `ReviewEvent`.
2. Identify all duplicated event-building, policy serialization, and post-review side effects.
3. Make one service command own locking, validation, scheduling, progress mutation, event persistence, and the returned canonical result.
4. Make single-review and batch paths adapt their transport input into that command instead of rebuilding its work.
5. Preserve atomic batch behavior and existing idempotency contracts.
6. Resolve or explicitly type the first-progress-row creation race without adding schema.
7. Ensure REST does not rely on stale, preloaded progress when the command later acquires locks.
8. Consolidate scheduler policy/config identity serialization into one implementation.
9. Add focused regression coverage for first review, concurrent/retried review, batch event parity, and REST/MCP parity.

Out of scope:

- New progress tables.
- Algorithm switching behavior.
- New generic Trigger dispatch.
- API response redesign unrelated to canonicalization.

Exit gate:

- Every native write path produces equivalent canonical event metadata through the same command boundary.
- Batch code no longer independently constructs the authoritative review event or scheduler identity.
- Existing API compatibility tests pass.
- Concurrency behavior has a named, tested failure/result contract.

### Agent B — Frontend session operation safety

Suggested task name: `frontend_session_safety`

Objective: serialize submit, undo, restore, and commit actions so same-tick UI events cannot mutate session state concurrently.

Primary ownership:

- React study session hooks and state modules under `frontend/src/`
- review action/interaction controller modules
- focused frontend tests for submit, undo, restore, and batch commit

Tasks:

1. Trace all asynchronous study mutations and document their entry points.
2. Replace the current ref-as-marker behavior with a true synchronous acquisition guard or equivalent serialized operation boundary.
3. Define how rejected duplicate actions surface to the caller without changing visible UX.
4. Verify that keyboard, pointer, retry, restore, and automatic commit paths share the same exclusion rule.
5. Preserve local undo and offline/session recovery behavior.
6. Add same-tick tests, including submit+submit, submit+undo, restore+submit, and commit+submit.
7. Confirm cleanup after success, handled failure, aborted request, and component unmount.

Out of scope:

- Visual redesign.
- Renderer keyboard bridge work, which belongs to Agent E.
- Backend event validation.

Exit gate:

- At most one mutating session operation can acquire ownership at a time.
- Same-tick tests fail against the old implementation and pass against the new boundary.
- Existing layout, labels, shortcuts outside the iframe, and undo UX are unchanged.

### Agent C — Restore event validation and quarantine

Suggested task name: `frontend_restore_storage`

Objective: make restored server/session events fail closed when their identity or sequence is malformed.

Primary ownership:

- frontend study persistence and restore modules
- shared TypeScript review-event validators
- focused restore/quarantine tests

Tasks:

1. Inventory the exact persisted and server-restored event shapes.
2. Define validation for event UUID, unique identity, contiguous sequence, valid card/session association, supported action/trigger identity, and valid time/offset fields.
3. Apply validation before restored events enter live state or influence commit calculations.
4. Quarantine invalid records with a diagnosable reason; do not silently repair ambiguous history.
5. Preserve normalization of valid legacy v2 records.
6. Add fixtures for duplicate IDs, sequence gaps, sequence reordering, non-UUID identity, negative/overflow offsets, mismatched session/card, unsupported contract identity, and a valid legacy restore.
7. Verify invalid records cannot be recommitted as if trusted.

Out of scope:

- Changing retention policy.
- Server-side schema or migration work.
- Broad event-contract redesign.

Exit gate:

- Every malformed fixture is rejected or quarantined with a stable reason.
- Valid current and legacy sessions still restore.
- Quarantined data cannot alter active session progress or commit payloads.

## 6. Wave 1 integration gate

The integration agent must verify all three Wave 1 branches together before Wave 2 or Wave 3 begins:

- Run backend review, batch, MCP, and concurrency-focused suites.
- Run frontend study action, persistence, restore, undo, and commit suites.
- Confirm frontend restored-event validation agrees with server event identity and sequence semantics.
- Review that no new source of progress truth was introduced.
- Review that no clone/full-copy behavior or database schema changed.
- Record unresolved failures in the canonical architecture plan rather than marking Phases 0-2 complete prematurely.

## 7. Wave 2 — Finish Interaction compatibility boundaries

Wave 2 should be sequential because Agent E depends on the final public interaction contract from Agent D.

### Agent D — Semantic Interaction component contract

Suggested task name: `review_interaction_contract`

Objective: complete extraction of the four-button interaction as a reusable semantic component without leaking raw scheduler ratings through parallel callback APIs.

Primary ownership:

- `StudyBottomBar` and the extracted review controls
- shared TypeScript Action/Trigger contracts
- component and study integration tests

Tasks:

1. Audit all callers of the extracted review control.
2. Choose one semantic callback boundary based on the current Action contract.
3. Remove or confine raw numeric rating callbacks to the compatibility adapter layer.
4. Keep interval preview values as display data, not action identity.
5. Keep current button order, labels, colors, spacing, icons, disabled states, and keyboard hints.
6. Add tests proving semantic action identity maps exactly once to the compatibility rating adapter.
7. Ensure a future alternative Interaction can consume the contract without importing scheduler-specific frontend code.

Exit gate:

- The visual component emits one semantic action contract.
- Numeric scheduler ratings exist only inside the explicit compatibility adapter.
- Zero visual regression and current interaction tests pass.

### Agent E — Trusted keyboard handling across renderer focus

Suggested task name: `iframe_keyboard_security`

Objective: restore expected study shortcuts when focus is inside the sandbox without reintroducing an untrusted generic action side channel.

Primary ownership:

- sandbox renderer host communication
- frontend study keyboard controller
- renderer CSP/message validation tests

Tasks:

1. Trace iframe sandbox flags, message origin/source checks, and current keyboard ownership.
2. Define the smallest trusted message contract required for keyboard intent.
3. Keep action authorization and semantic mapping in the parent study runtime.
4. Reject arbitrary action names, ratings, payloads, or messages from unrelated frames.
5. Handle editable controls, composition/IME input, repeated keydown, and focus transitions.
6. Add security tests for spoofed messages and UX tests for valid shortcuts inside/outside the sandbox.
7. Preserve renderer sanitization, CSP, and media proxy constraints.

Exit gate:

- Valid shortcuts work with parent or renderer focus.
- Renderer content cannot directly invoke progress writes or choose arbitrary semantic actions.
- Origin/source/schema validation and editable-input suppression are covered by tests.

## 8. Wave 3 — Make composition selection real without schema changes

Wave 3 begins only after Wave 1 integration because it touches session creation and restore semantics. Backend and frontend agents may work concurrently after agreeing on an additive contract.

### Agent F — Composition backend authorization and session freeze

Suggested task name: `composition_backend`

Objective: make selected composition an authorized, explicit input to session creation and freeze it for the session lifetime.

Primary ownership:

- `app/services/study_composition_service.py`
- study scope/composition API
- study session creation service and tests
- overlay-only clone resolution tests

Tasks:

1. Re-derive the current composition call graph and distinguish scaffolded data from authoritative session behavior.
2. Require or compatibly default an eligible composition at session creation.
3. Validate that the selected composition belongs to the requested study scope and is accessible to the current user.
4. Freeze composition identity and relevant version/config metadata in the session snapshot.
5. Define rejection behavior for missing, deleted, inaccessible, or changed compositions during an active session.
6. Test direct owned decks and real installed overlay-only clone resolution.
7. Replace any physical-copy clone fixture used as proof of overlay behavior.
8. Preserve old clients through an explicit compatibility default if required.

Out of scope:

- FieldDef binding schema.
- Independent reusable Template architecture.
- Phase 4 progress persistence.

Exit gate:

- A session cannot select an unauthorized or out-of-scope composition.
- The chosen composition is immutable for the active session.
- Direct and overlay-only clone paths have focused proof.
- Old-client fallback is documented and tested if retained.

### Agent G — Pre-session Study Mode selection flow

Suggested task name: `composition_frontend`

Objective: make the user's selected Study Mode determine session creation instead of decorating an already-created session.

Primary ownership:

- `StudyModeSelector`
- study launch route/page and session creation client
- frontend composition and launch tests

Tasks:

1. Trace when the current session is created relative to composition discovery and selection.
2. Move selection before session creation while preserving loading, empty, and single-option flows.
3. Send the selected composition identity through the agreed additive backend contract.
4. Restore/reload an active session using its frozen composition instead of re-prompting.
5. Handle an unavailable selection with an explicit recoverable state.
6. Preserve existing study UI after the session starts.
7. Add tests for one option, multiple options, inaccessible/stale choice, creation failure, and active-session restore.

Exit gate:

- No new session opens before an applicable selection/default is resolved.
- The user's selection reaches the server and is reflected in the frozen session.
- Reloading an active session does not silently change its Study Mode.

## 9. Wave 4 — Evidence and event hardening

### Agent H — Migration-grade read-only study audit

Suggested task name: `study_audit_hardening`

Objective: turn the current aggregate audit into a safe, operationally useful read-only verification tool.

Tasks:

1. Inventory all required anomaly classes across progress, sessions, events, algorithm identity, composition snapshots, and clone provenance.
2. Make output deterministic, bounded, and safe for production-size data.
3. Add explicit startup-safety documentation: the audit must never become an automatic mutating boot task.
4. Add MySQL-compatible query coverage or a documented production verification procedure.
5. Include counts and sampled identifiers without logging answer content or secrets.
6. Define pass/fail thresholds and machine-readable exit behavior.

Exit gate:

- The command is read-only by construction.
- SQLite tests and MySQL verification evidence exist.
- Operators can distinguish clean, warning, and blocking results.

### Agent I — ReviewEvent integrity and provenance hardening

Suggested task name: `review_event_hardening`

Objective: ensure newly persisted review history has sufficient identity and provenance for current compatibility, audit, and future algorithm switching analysis.

Tasks:

1. Reconcile all ReviewEvent producers after Agent A's canonicalization.
2. Verify effective algorithm key/version/config hash, semantic action/trigger identity, source path, session identity, request identity, and ordering data.
3. Define validation for fields that are required for new writes while retaining readable legacy events.
4. Add audit coverage for missing or conflicting provenance.
5. Avoid claiming indefinite replay support; the approved exact replay horizon is only the active session lease.

Exit gate:

- New native writes have one consistent provenance contract.
- Legacy gaps are classified rather than silently invented.
- Audit and persistence tests agree on required fields.

## 10. Wave 5 — Trigger Runtime design checkpoint only

### Agent J — Trigger Runtime boundary investigation

Suggested task name: `trigger_runtime_design`

Objective: produce a bounded design decision for the first genuine Trigger dispatch boundary after the compatibility cleanup is stable.

Deliverable: documentation only; no runtime implementation, schema, or migration.

Questions to answer:

1. Which current module records Trigger metadata but does not execute a true dispatch boundary?
2. What is the minimum typed input/output contract for a primary review trigger?
3. Which responsibilities stay in Interaction, Trigger Runtime, Algorithm adapter, and transaction owner?
4. How are synchronous primary progress effects separated from optional secondary consumers?
5. How are idempotency, failure, ordering, authorization, and observability represented?
6. How does the boundary remain compatible with the approved client-evaluates/server-verifies model?
7. What must wait for Field, Template, and composition binding decisions?

Exit gate:

- The document identifies responsibilities and decisions without prematurely defining detailed SQL.
- It does not authorize Phase 4 or add another progress source.
- It names the smallest reviewable implementation slice for later approval.

## 11. Final integration agent

Suggested task name: `study_architecture_integrator`

The integration agent must not merely merge test results. It owns cross-boundary review and canonical documentation updates.

Tasks:

1. Inspect the complete shared-worktree diff and assign every changed file to an approved task.
2. Reject unrelated cleanup, accidental formatting, schema changes, and duplicate abstractions.
3. Run focused suites first, then the relevant combined backend/frontend suites.
4. Verify REST, MCP, batch, restore, undo, iframe keyboard, composition selection, and overlay clone behavior together.
5. Re-run architecture searches for duplicate event builders, raw rating callbacks, name-only Trigger dispatch, and secondary progress sources.
6. Update `docs/architecture/study-interaction-trigger-algorithm-plan.md` using evidence from code and tests.
7. Mark a cleanup order or phase complete only when every documented exit gate is met.
8. Record remaining debt as concrete follow-up tasks with owner boundaries.

## 12. File ownership and conflict rules

| Area | Primary agent | Coordination rule |
| --- | --- | --- |
| Backend review transaction and events | Agent A | Agent I waits until Agent A is integrated |
| Frontend operation serialization | Agent B | Agent G must preserve the final mutex boundary |
| Frontend restore validation | Agent C | Agent G must reuse, not bypass, restore validation |
| Interaction component contract | Agent D | Agent E consumes the finalized semantic contract |
| Sandbox keyboard bridge | Agent E | Must not change renderer sanitization ownership |
| Composition API/session creation | Agent F | Agree additive request shape with Agent G first |
| Study launch/selector | Agent G | Do not edit backend authorization logic |
| Audit command | Agent H | Read-only; coordinates required provenance with Agent I |
| ReviewEvent provenance | Agent I | Must use Agent A's canonical command, not create another |
| Canonical architecture docs | Integrator | Coding agents report evidence; integrator edits status |

If two agents need the same file, do not let both make independent structural edits. Assign one owner and have the other provide a requested patch description or wait for integration.

## 13. Required agent report format

Every coding agent must return:

1. Outcome achieved.
2. Exact files changed.
3. Behavior preserved.
4. Tests added or changed.
5. Commands run and their results.
6. Known failures or tests not run.
7. Architectural risks or follow-up work.
8. Confirmation that no migrations, production writes, commits, resets, or unrelated cleanup were performed.

## 14. Suggested verification commands

Agents should discover the narrowest existing test modules before running commands. Typical verification sequence:

```powershell
rg -n "ReviewEvent|CardProgress|algorithm_version|trigger|composition_id" app models tests frontend/src
python -m unittest <focused_backend_test_modules>
npm --prefix frontend test -- <focused_frontend_test_files>
npm --prefix frontend run build
git diff --check
git status --short
```

Do not substitute a full suite for focused causal tests. The integrator may run broader suites after focused tests pass.

## 15. Recommended first delegation batch

Start exactly these three agents in parallel:

1. `backend_review_boundary` — canonicalize backend review transaction/event ownership.
2. `frontend_session_safety` — make session mutations mutually exclusive.
3. `frontend_restore_storage` — validate and quarantine malformed restored events.

Do not start composition, iframe keyboard, Trigger Runtime, or database work in the same batch. This first batch closes correctness risks that later work would otherwise build upon.

## 16. Decisions still requiring explicit approval

The following are intentionally not decided by this execution plan:

- The permanent reusable Template/NoteType/Field binding model.
- The physical schema for generic learner progress and Algorithm State.
- The retained executable/state-decoder retirement policy.
- The first real generic Trigger Runtime implementation contract.
- API compatibility retirement timing after v2.
- Whether a future composition is a persisted domain entity or a derived application configuration.

Any task that reaches one of these decisions must stop at evidence and options, then request architectural approval before implementation.
