# Phase 0–3 next execution plan — after independent review round 5

> Status: PHASE 0 AND P1-01–P1-02 CLOSED; P1-03 is queued and has not started
>
> Current gate: `P0-01..P0-04 COMPLETED`, Phase 0 `GO`, `P1-01 COMPLETED`, `P1-02 COMPLETED`
>
> Scope: close P0-03, then sequence the remaining runtime-correctness and composition-contract tasks through INT-01
>
> Hard boundary: no model, migration, physical progress store, source-of-truth cutover or full-copy clone behavior in this plan

## 1. Outcome and ordering rule

The replacement P0-03 evidence bundle and P1-01 canonical native review transaction passed their gates. P1-02 then completed its inventory, conflict matrix, runtime closeout and MySQL 8.0.40 acceptance proof on 2026-08-30. P1-03 is next in the dependency chain but was not started during this closeout. Phase 4 remains outside this plan. See the [2026-08-30 evidence review](../../architecture/decoupling-progress-review-2026-08-30.md) and the [completed P1-02 handoff](./completed/P1-02_EXTERNAL_PROGRESS_REVISION_CONTRACT.md).

After Phase 0 closes, use this order:

```text
P0-03 SELECT-only evidence + Phase 0 closeout
  -> P1-01 canonical native review transaction
  -> P1-02 external revision/conflict contract
  -> P1-03 ReviewEvent provenance
  -> P1-04 Algorithm retirement lifecycle

P0-03 closeout
  -> P2-02 frontend mutex
  -> P2-03 restore validation/quarantine
  -> P2-04 semantic interaction
  -> P2-05 trusted keyboard decision

P1-03 + P2-04 -> P2-06 Trigger design
P1-04 + P2-03 + P2-06 -> P2-07 wire v3/v2 lease policy

P0-03 closeout -> P3-05 + P3-07 decision contracts
P1/P2 correctness + P3-05 + P3-07
  -> P3-01 -> P3-02 -> P3-03 -> P3-04 -> P3-06
  -> INT-01
```

## 2. Step 0 — unblock and complete P0-03

### 2.1 Required input

Operator exposes the authorized audit URI as `SQLALCHEMY_DATABASE_URI` only to the audit process through the workspace secret/environment mechanism. This is the variable current app settings actually read. Do not put the URI in chat, Markdown, committed files or command history.

### 2.2 Work breakdown

| Subtask | Detailed work | Required output |
|---|---|---|
| P0-03.1 Credential preflight | Connect without printing URI; read `CURRENT_USER()`, `DATABASE()` and `SHOW GRANTS`; fail closed when identity/schema is unexpected or any INSERT/UPDATE/DELETE/CREATE/ALTER/DROP/GRANT OPTION is present | Redacted principal/schema/grant proof; no secret and no DB mutation |
| P0-03.2 Freeze exact code | Verify every file hash and canonical manifest digest in `study_architecture_audit_code_manifest_2026-08-29.json`; regenerate the manifest first if any audit-runtime file changed | Verified manifest with zero file-digest mismatch |
| P0-03.3 Candidate run 1/2 | Run `wsgi_audit.py` twice through the maintenance-disabled factory; write candidate files first rather than overwriting the historical bundle | Two redacted raw JSON candidates plus process exit codes and timestamps |
| P0-03.4 Determinism check | Normalize only `observed_at`; compare full payload recursively; reject any other difference | Machine-readable comparison with `deterministic_excluding_timestamp=true` and empty semantic diff |
| P0-03.5 Evidence promotion | Promote verified candidates to authoritative run 1/run 2/baseline artifacts; compute SHA-256 after files are closed | Current baseline, two raw runs, comparison and checksum manifest from one execution bundle |
| P0-03.6 Report reconciliation | Update all counts, warning owners, environment metadata and exit-code semantics in the production verification report | Report and JSON agree 1:1; stored Round 4 claims remain explicitly historical |
| P0-03.7 Regression and closeout | Run focused audit, Study backend and Connect MCP backend suites; update P0-03 and central handoff only after evidence review | P0-03 `COMPLETED`; Phase 0 closeout verdict with commands/results |

### 2.3 Acceptance gate

- Principal has `SELECT` and no write/DDL/grant privilege.
- Audit app registers no normal mutator command and runs no startup maintenance.
- Run 1 and Run 2 differ only in declared timestamp fields.
- Inventory, reconciliation, verdict counts, warning table, raw artifacts and Markdown report agree exactly.
- Every warning has a stable disposition and downstream task owner.
- Manifest digest and all file digests verify after the final run.
- Focused audit tests, Study backend and Connect MCP backend suites pass.
- Any process `BLOCK`, unexpected privilege, semantic drift or checksum mismatch keeps P0-03 `BLOCKED`.

### 2.4 Commands after the secret is available

```text
.venv\Scripts\python.exe -m unittest tests.test_study_architecture_audit_cli tests.test_study_architecture_audit_service tests.test_study_behavior_acceptance_baseline
.venv\Scripts\python.exe scripts/run_tests.py --module study --backend-only
.venv\Scripts\python.exe scripts/run_tests.py --module connect_mcp --backend-only
```

The audit command itself must receive the URI through process environment. Do not inline the URI in the documented command.

### 2.5 Allowed preparation while the credential is blocked

To avoid idle time, P1-01.1 may be performed as a read-only draft: map every producer, lock/revision check, event builder, side effect and commit/rollback owner. The draft must be labeled non-authoritative and must not extract code, change runtime behavior or mark Phase 1 started. P3-05/P3-07 may collect open questions, but cannot approve a decision without the authoritative P0-03 evidence.

Historical preparation update: P1-01.1 mapped direct, MCP and session transaction ownership before implementation. The completed P1-01 handoff now supersedes the former two-writer observation.

Update 2026-08-29: P3-05 and P3-07 repository evidence/open-question inventories are also complete. Both remain `TODO`: production distribution, mixed-scope cardinality and applied-composition lifecycle decisions require the accepted P0-03 bundle before ADR approval.

Closeout update 2026-08-30: the SELECT-only replacement bundle passed with 67 categories, 11/11 formulas, 61 PASS, 6 WARN, 0 BLOCK and deterministic two-run output. Step 0 and P1-01–P1-02 are complete. P1-02 closed deterministic clone-cutover locks, monotonic revision, response tokens, canonical reset/cutover delegation and the full focused/MySQL proof; P1-03 remains queued.

## 3. Step 1 — P1-01 canonical native review transaction

P1-01 is completed and has unlocked P1-02, P1-03 and P1-04. The table below is retained as the executed slice plan; the completed task handoff contains the post-change call graph and evidence.

### 3.1 Delivery slices

| Slice | Detailed work | Required output |
|---|---|---|
| P1-01.1 Producer/call graph | Trace REST route, MCP `submit_review`, session commit, progress writes, `record_review_event`, dirty tracking and transaction owner | Before-call graph and producer inventory with exact commit/rollback owner |
| P1-01.2 Typed core contract | Define transport-neutral command input/result/error types for user/card/action/policy/revision/provenance and side-effect intents | Approved function contract; no HTTP/MCP/session DTO leakage |
| P1-01.3 Core extraction | Extract transition, progress application, canonical ReviewEvent construction and required local side effects into a non-committing core | One core owns native mutation semantics; `CardProgress` remains authority |
| P1-01.4 Direct/MCP adapters | Route REST and MCP through the core while preserving response/error shapes | Direct/MCP parity tests and no route helper imported by services |
| P1-01.5 Session adapter | Keep lease validation, sequence/idempotency and outer transaction in session service, but delegate each native transition/event to the same core | Batch/session no longer owns a second canonical event or policy builder |
| P1-01.6 Concurrency/rollback | Normalize first-progress insert race, stale revision and suspension errors; prove rollback after flush/side-effect failure | Typed errors, zero partial progress/event/dirty-tracking writes |
| P1-01.7 Cleanup and handoff | Remove obsolete duplicate builders only after all callers migrate; document post-call graph | Search proof of one authoritative native builder plus task handoff |

### 3.2 File ownership

Exclusive backend ownership for this task:

- `app/services/study_service.py`
- `app/services/study_session_service.py`
- `app/services/study_policy_service.py`
- `app/routes/flashcards/study.py`
- `app/services/mcp/study_tools.py`
- related Study/Connect tests

Do not combine unrelated OAuth, UI or schema changes in the P1-01 handoff.

### 3.3 P1-01 output gate

- Same initial state, semantic action and policy produce equivalent progress and canonical event metadata through direct, MCP and session paths.
- Only session transport adds lease/client-event/sequence metadata.
- Session commit remains all-or-nothing and idempotent.
- No internal event builder commits independently of its outer transaction.
- No model/migration change.
- Verification: Study backend, Connect MCP backend and changed-file tests.

## 4. Step 2 — frontend correctness lane

Run these tasks sequentially because they share Study hook/session-store ownership. Preserve zero visual regression.

| Order | Task | Detailed focus | Required output |
|---:|---|---|---|
| 1 | P2-02 | Replace marker-style operation tracking with synchronous owner-token acquisition across submit/undo/restore/commit/retry | One mutex boundary; same-tick conflict matrix; correct release after error/abort/unmount |
| 2 | P2-03 | Validate restored current/legacy events before hydration; quarantine invalid rows atomically and idempotently | Strict validator, stable bounded reason set, valid-v2 compatibility and invalid-history containment tests |
| 3 | P2-04 | Collapse controls to one semantic `ReviewAction` callback; keep raw rating mapping in a named compatibility adapter | Single-emission semantic API and unchanged layout/colors/spacing/icons |
| 4 | P2-05 | Decide and document trusted keyboard boundary after semantic action ownership is stable | Threat model plus safe implementation or explicit no-bridge decision |

Verification after each frontend task:

```text
(from frontend/) npm run test:changed
python scripts/run_tests.py --module study --frontend-only
```

## 5. Step 3 — backend follow-ups unlocked by P1-01

Execute sequentially to avoid competing edits in Study/Connect event writers.

| Order | Task | Detailed focus | Required output |
|---:|---|---|---|
| 1 | P1-02 | Inventory external progress mutators; define native/session/snapshot/revlog/repair conflict matrix; apply revision and idempotency rules without source mutation | Mutation inventory, approved conflict matrix, typed conflict codes, overlay-aware concurrency tests |
| 2 | P1-03 | Define versioned bounded provenance payload; build event once with final native/external identity; classify legacy gaps without invention | Canonical event contract, payload validator, producer inventory and audit disposition updates |
| 3 | P1-04 | Define active/deprecated/lease-only/retired states and exact decoder/executable retention across server/client | Support matrix, retention runbook and exact-version failure tests |

P1-02 must preserve logical overlay identity and never mutate source Notes/Cards. P1-03 must keep ReviewEvent as immutable history, not current progress authority. P1-04 must not silently fall back to a newer algorithm version.

## 6. Step 4 — decision-only composition lane

Start only after authoritative P0-03 evidence exists. These are ADR/contract tasks; they must not create models or migrations.

### P3-05 mixed-NoteType scope policy

- Validate observed single/mixed/empty scope distribution from the new audit bundle.
- Compare grouped compositions, NoteType-first selection and single-NoteType session restriction.
- Decide stable grouping/order, selected progress-subject set, overlay/local-added behavior and old-client fallback.
- Output: ADR, API cardinality contract, frontend state flow and owned/overlay acceptance examples.

### P3-07 applied composition and binding contract

- Keep `Note`, `Template`, `Card` and `CardProgress` current responsibilities explicit.
- Define logical definition/version/input/application/binding/effective-composition identities without prescribing SQL.
- Anchor future binding identity to stable `FieldDef.id`; names remain labels/legacy syntax.
- Define repeated application, pin/fork/unpublish/detach lifecycle and active-session frozen material.
- Output: ADR/contract tables, compatibility composition ID rules, binding error matrix, overlay/import/Connect compatibility and deferred Phase 4 questions.

These decisions are inputs to P3-01 and P3-04, not authorization for physical schema design.

## 7. Step 5 — Trigger/wire convergence

| Task | Dependency gate | Required output |
|---|---|---|
| P2-06 | P1-03 + P2-04 | Approved Trigger responsibility, transaction, idempotency and provenance contract |
| P2-07 | P1-04 + P2-03 + P2-06 | Wire v3 implementation/policy with bounded v2 lease compatibility and fail-closed restore/dispatch |

Do not implement Trigger dispatch before P2-06 is approved. Do not remove v2 decoding while a supported lease/persisted-session window remains.

## 8. Step 6 — Phase 3 implementation and closeout

| Order | Task | Required output |
|---:|---|---|
| 1 | P3-01 | Exactly-one authorized composition selection in session API with compatibility fallback |
| 2 | P3-02 | One query-first clone-aware resolver for owned/source-overlay/local-added contexts |
| 3 | P3-03 | Pre-session StudyMode selection that sends the approved composition identity; zero visual regression |
| 4 | P3-04 | Frozen effective composition snapshot with stale/restore behavior |
| 5 | P3-06 | Real overlay-only exit proof using `DeckInstall`; no physical clone fixture and no source mutation |
| 6 | INT-01 | Combined P0–P3 verification, duplicate-boundary audit and tracker closeout |

## 9. Checkpoints and stop conditions

| Checkpoint | GO condition | STOP condition |
|---|---|---|
| Phase 0 closeout | Current SELECT-only bundle, report, checksums and tests agree | Credential absent, unsafe grant, audit block, semantic drift or checksum mismatch |
| P1-01 merge | One canonical native builder and full parity/rollback evidence | Two authoritative builders, hidden commit, partial write or API regression |
| P1/P2 correctness | Revision/provenance/retirement + mutex/restore/semantic gates pass | Silent last-write-wins, invented provenance, version fallback or invalid restore hydration |
| Phase 3 entry | P3-05/P3-07 approved and P1/P2 dependencies complete | Mixed scope/binding identity remains ambiguous |
| INT-01 | All task outputs and module tests pass; no source mutation/schema change | Any incomplete dependency or compatibility invariant failure |

## 10. Immediate handoff

1. P0-03 is complete; retain its six warning classes as explicit downstream inputs.
2. Treat the completed P1-01 typed core and session outer transaction as the fixed native-write boundary.
3. P1-02.1–P1-02.4 completed. Preserve the external revision/conflict contract as the fixed boundary; P1-03 may start only as a separate task/handoff.
4. Keep frontend correctness work ordered P2-02 → P2-03 → P2-04 → P2-05.
5. Review P3-05/P3-07 decisions against the accepted production distribution before P3 implementation.
