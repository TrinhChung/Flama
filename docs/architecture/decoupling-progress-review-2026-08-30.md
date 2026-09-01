# Decoupling progress review and detailed continuation plan — 2026-08-30

> Date: 2026-08-30
>
> Mode: INVESTIGATE + execution planning inside the approved Phase 0–3 contracts
>
> Reviewed revision: `5d578b9`
>
> Safety boundary: no schema/migration change, no progress-authority cutover, and no physical-copy clone behavior is authorized by this review.
>
> Closeout update: P1-02 was completed later on 2026-08-30. Findings 1–5 below describe the pre-closeout state; their resolution evidence is recorded in the [completed P1-02 handoff](../task/decoupling/completed/P1-02_EXTERNAL_PROGRESS_REVISION_CONTRACT.md).

## 1. Executive conclusion at review time

- Phase 0, P1-01 and P2-01 remain complete.
- P1-02 is **partially implemented**, not merely “not started”: modern Anki snapshot conflict handling, legacy `cardsProgress` ordering, revlog/current-state separation, frontend base-hash forwarding and deck-reset session cancellation have landed.
- P1-02 cannot be closed because clone-cutover progress merging still has no deterministic row lock and does not bump `CardProgress.revision`; the new conflict codes also lack focused acceptance tests.
- Phase 2 and Phase 3 contain useful compatibility scaffolds, but their authoritative gates remain open. Green regression suites do not prove same-tick mutex, strict restore quarantine, semantic-only controls, pre-open composition selection or real overlay-only composition behavior.
- There are still 17 open parent tasks from P1-02 through INT-01. P1-02 is the only active parent task and has completed a material portion of P1-02.3.
- Phase 4/schema work remains **NO-GO** until P1–P3 and INT-01 are closed.

### P1-02 closeout addendum

- P1-02.3a–P1-02.3d are complete: response-token/unversioned semantics, deterministic cutover row locking, monotonic `max(revision)+1`, canonical public cutover ownership and reset compatibility delegation are implemented.
- P1-02.4 is complete: focused modern/legacy/revlog/reset/cutover tests pass, and a disposable MySQL 8.0.40 two-connection probe returned typed losers without deadlock or lost update.
- Isolated committed-tree regression passed: Study backend 98/98, Connect/MCP backend 161/161, Decks+Flashcards backend 305/305 and frontend Anki sync helper 11/11.
- The task moved to `docs/task/decoupling/completed/`; the open parent-task count is now 16. P1-03 is queued but was not started by this closeout.

## 2. Verification executed in this review

| Gate | Result | Interpretation |
|---|---:|---|
| `python scripts/run_tests.py --module study --backend-only` | PASS — 98 tests | Existing Study regression surface is green. |
| `python scripts/run_tests.py --module connect_mcp --backend-only` | PASS — 161 tests | Existing Connect/MCP surface is green. |
| `python scripts/run_tests.py --module decks,flashcards --backend-only` | PASS — 301 tests | Existing deck, import, flashcard and share regressions are green. |
| `python scripts/run_tests.py --module study --frontend-only` | PASS — 89 tests | Existing frontend Study regressions are green. |
| `npm run test:changed` from `frontend/` | PASS — 0 tests selected | Not an acceptance gate because the worktree was clean. |

The suites above confirm no observed regression at the reviewed commit. They do not replace the missing task-specific assertions listed below.

## 3. Evidence-backed findings

### Finding 1 — P1-02.3 implementation has landed but the tracker was stale

- **Observed**: commit `2bf990b` added modern snapshot base-hash/local-revision checks, typed result codes, legacy snapshot ordering and first-party base-hash forwarding. Commit `fd81481` cancels affected open Study Sessions before deck progress reset. Commit `70e2d47` makes the active share shim delegate progress merging to the modular helper and adds a per-install savepoint in the active cutover loop.
- **Evidence**: `app/services/anki_sync_service.py`, `app/services/connect/import_cards.py`, `frontend/src/lib/ankiSyncEngine.ts`, `app/services/deck_management_service.py`, `app/services/flashcards_share_service.py`.
- **Potential concern**: task documentation still described P1-02.3 as wholly “next”, so a handoff could repeat landed work or incorrectly close the task based on commit subjects.
- **Impact**: wasted implementation effort or an unsafe closeout that misses the remaining clone/concurrency gap.
- **Unknowns**: no production mutation probe was performed; production concurrency frequency remains unverified.

### Finding 2 — Modern and legacy Anki paths implement most, but not all, approved semantics

- **Observed**: modern snapshots lock `ConnectSourceCardRef` and existing `CardProgress`, compare `baseSnapshotHash` and `applied_local_revision`, avoid creating progress for same-hash/due-unresolved outcomes, bump material writes once, and return typed codes. Legacy `cardsProgress` now distinguishes newer, stale, identical and ambiguous snapshots. Revlog import no longer writes current-progress pointers.
- **Evidence**: `app/services/anki_sync_service.py:95`, `app/services/anki_sync_service.py:132`, `app/services/anki_sync_service.py:330`, `app/services/connect/import_cards.py:311`.
- **Potential concern**: `legacy_unversioned` is currently true only when a previous snapshot exists; a first material snapshot without `baseSnapshotHash` is not marked unversioned even though the approved compatibility contract says missing base hash must be visible. `import_progress` also does not return the applied `serverSnapshotHash` in each result, leaving the response contract asymmetric with note-status.
- **Impact**: rollout telemetry can undercount unversioned clients, and a client may need an extra status read to obtain the new optimistic token.
- **Unknowns**: confirm whether response-level `serverSnapshotHash` is required or note-status is intentionally the sole token source before changing the wire response.

### Finding 3 — Clone cutover still violates the approved revision contract

- **Observed**: `_merge_card_progress_rows_for_cutover` reads local and source progress without `FOR UPDATE`; rekeying preserves the old revision, and merging/deleting the local row never sets `target.revision = max(local, target) + 1`.
- **Evidence**: `app/services/share/cutover.py:174`, `app/repositories/flashcards_share_repository.py:520`. The compatibility shim in `app/services/flashcards_share_service.py:1417` delegates to this helper, so this is the active behavior too.
- **Potential concern**: a concurrent native/session review can race cutover, and an already-open Study Session may not become stale after a material progress identity merge.
- **Impact**: silent loss of newer progress or acceptance of a stale batch commit after cutover.
- **Unknowns**: MySQL lock/deadlock behavior needs a disposable write-enabled MySQL test; SQLite cannot prove row-lock ordering.

### Finding 4 — The cutover boundary is only partially consolidated

- **Observed**: the active monolith delegates the row merge to `app.services.share.cutover`, but both the monolith and modular package still expose separate full cutover implementations. The active CLI imports the monolith through `app.services.flashcards_share`.
- **Evidence**: `app/services/flashcards_share.py`, `app/services/flashcards_share_service.py:3605`, `app/services/share/cutover.py:662`, `app/cli.py:362`.
- **Potential concern**: future fixes may update only one full cutover loop. The active loop has a per-install savepoint; the modular full loop still has different rollback behavior.
- **Impact**: behavior drift based on import path and incomplete P1-02/P3 cleanup.
- **Unknowns**: no direct production caller for the modular full cutover was found, but it remains public through `app.services.share`.

### Finding 5 — P1-02 acceptance coverage is missing

- **Observed**: the implementation commits did not modify tests. Repository tests contain no assertions for `baseSnapshotHash`, `SOURCE_SNAPSHOT_CHANGED`, `LOCAL_PROGRESS_CHANGED`, `FORCED_PROGRESS_APPLIED`, `AMBIGUOUS_PROGRESS_ORDER` or `ANKI_DUE_UNRESOLVED`.
- **Evidence**: commit stats for `2bf990b`, `fd81481`, `70e2d47`; repository search in `tests/`.
- **Potential concern**: broad modules pass while every newly approved conflict branch can regress unnoticed.
- **Impact**: P1-02.4 cannot provide the required “no silent last-write-wins” proof.
- **Unknowns**: none; this is a confirmed coverage gap.

### Finding 6 — Phase 2 scaffolds exist, but the correctness gates remain open

- **Observed**:
  - `useStudySession` sets `operationRef.current = true` after entry without atomic test-and-acquire; answer, undo and commit can enter in the same tick.
  - restore validation accepts any non-empty event ID, requires only increasing rather than contiguous sequence, does not reject duplicate event IDs, and does not enforce monotonic/bounded scheduler offsets.
  - `ReviewInteractionControls` publicly exposes and emits both `onAnswer` and `onReviewAction`; `StudyBottomBar` still owns a raw rating callback.
  - P2-01 containment remains present: forged host commands are ignored and the iframe source no longer emits progress-affecting host commands.
- **Evidence**: `frontend/src/features/study/hooks/useStudySession.ts:280`, `frontend/src/features/study/session/sessionRestore.ts:73`, `frontend/src/features/study/interactions/ReviewInteractionControls.tsx:16`, `frontend/src/features/study/components/StudyBottomBar.tsx:20`, `frontend/src/features/study/components/CardRendererHost.test.ts:90`.
- **Potential concern**: IndexedDB/live-state divergence, ambiguous restored history and duplicate semantic emission.
- **Impact**: incorrect offline/session commit behavior even while visual tests remain green.
- **Unknowns**: browser-level trusted shortcut behavior inside editable/IME contexts remains unverified; P2-05 must decide whether no-bridge remains the final policy.

### Finding 7 — Phase 3 is still a compatibility scaffold, not an authoritative composition contract

- **Observed**: open-session accepts an optional list `composition_ids`; the service fetches up to `MAX_SESSION_CARDS + 1` before filtering in Python. React opens the session before a learner selection and filters the frozen view locally. The existing “clone” exit test creates a second physical Card rather than installing a real `DeckInstall` logical overlay.
- **Evidence**: `app/routes/flashcards/study.py:681`, `app/services/study_session_service.py:372`, `app/services/study_session_service.py:379`, `frontend/src/features/study/hooks/useStudySession.ts`, `tests/test_study_composition_exit_gate.py:148`.
- **Potential concern**: unauthorized/ambiguous multi-selection, query-limit unfairness and source/local Template identity mismatch for installed decks.
- **Impact**: selection does not authoritatively control which progress subjects enter the session; Phase 3 cannot be declared complete.
- **Unknowns**: P3-05 mixed-NoteType policy and P3-07 application/binding identity are still awaiting formal ADR approval.

## 4. Current task matrix

| Task | Current status | Concrete remainder | Required output before close |
|---|---|---|---|
| P1-02 | **COMPLETED 2026-08-30** | none; preserve the completed external writer contract | [completed handoff](../task/decoupling/completed/P1-02_EXTERNAL_PROGRESS_REVISION_CONTRACT.md) |
| P1-03 | TODO | versioned bounded ReviewEvent provenance; shared validation; legacy classification | producer inventory, validator/builder, malformed/oversized tests |
| P1-04 | TODO | executable/decoder lifecycle and support states | support matrix, retirement runbook, cross-deploy tests |
| P2-02 | TODO | real owner-token mutex for all frontend mutations | same-tick conflict matrix and cleanup proof |
| P2-03 | TODO | UUID/duplicate/contiguous/offset/membership validation | strict restore validator and bounded quarantine fixtures |
| P2-04 | TODO | semantic-only reusable control API | one callback, compatibility adapter and single-emission tests |
| P2-05 | TODO | trusted keyboard threat model and browser evidence | safe bridge or explicit permanent no-bridge ADR |
| P2-06 | TODO | built-in Trigger responsibility decision | ADR, transaction/idempotency/version error matrix |
| P2-07 | TODO | wire v3 plus measured v2 lease compatibility | versioned validators, rollout/retirement policy and tests |
| P3-05 | TODO / inventory complete | approve mixed-NoteType scope/cardinality behavior | ADR and API/frontend default/error contract |
| P3-07 | TODO / inventory complete | approve logical application/binding/lifecycle identities | ADR with compatibility ID and frozen-material contract |
| P3-01 | TODO | exactly-one authorized composition input | API/error/fallback contract and backend tests |
| P3-02 | TODO | clone-aware discovery and query-first selection | one effective-scope resolver and fairness tests |
| P3-03 | TODO | select before opening session | pre-session UI flow with zero visual regression |
| P3-04 | TODO | freeze selected effective composition | restore/stale behavior and immutable snapshot proof |
| P3-06 | TODO | replace physical-copy simulation with real overlay gate | `DeckInstall` source/local-added end-to-end tests |
| INT-01 | TODO | combined Phase 0–3 integration and documentation closeout | exit checklist and Phase 4 GO/NO-GO recommendation |

## 5. Detailed execution plan

### Wave A — P1-02 execution plan (completed)

| Slice | Detailed work | Output / acceptance gate |
|---|---|---|
| P1-02.3a — Modern snapshot contract finish | Decide and document whether `serverSnapshotHash` is returned by `import_progress` or only note-status; mark every missing-base material request as `legacy_unversioned`; preserve same-hash and due-unresolved zero-progress side effects. | Additive response contract is unambiguous; no hidden unversioned client. |
| P1-02.3b — Cutover row locking | Add one repository/helper path that loads local/source `CardProgress` in deterministic card-ID order with `FOR UPDATE`; handle local-only, source-only and dual-row cases. | One lock order is used by active and modular imports; no unlocked active path. |
| P1-02.3c — Cutover revision | For every material rekey/merge set the surviving row revision to `max(local_revision, source_revision) + 1`; preserve the current newer-state and max-counter merge rules; delete the local row atomically. | An open session frozen on either affected row becomes stale; source Note/Card content remains unchanged. |
| P1-02.3d — Canonical cutover ownership | Make the compatibility shim and modular public API delegate the same full cutover implementation, including per-install savepoint behavior. Keep CLI/startup outer commit ownership unchanged. | Search shows one authoritative migrate/cutover implementation, or the remaining compatibility wrapper is documented as pure delegation. |
| P1-02.4a — Modern snapshot tests | Cover new-row revision 1, same-hash replay, local conflict, source conflict, forced apply, due-unresolved no-op, first-insert conflict and base-hash forwarding. | Every approved typed code is asserted together with row/event/revision side effects. |
| P1-02.4b — Legacy/revlog/reset tests | Cover newer/stale/identical/equal-different/missing-time legacy states; prove revlog never mutates current progress; prove reset cancels affected owned and overlay sessions before deletion. | No snapshot is mislabeled as native and no reset session can resurrect progress. |
| P1-02.4c — Cutover/overlay tests | Cover local-only rekey, source-newer, local-newer, exact max+1 revision, strict/non-strict savepoint, source Card overlay and local-added Card identity. | No source mutation and no last-write-wins proof on SQLite behavior. |
| P1-02.4d — MySQL concurrency probe | On a disposable write-enabled MySQL database, run native/snapshot and native/cutover two-transaction cases; record lock order, final revision and typed loser result. | MySQL proof is stored without credentials; deadlock or lost update keeps task open. |
| P1-02.4e — Closeout | Run the four focused modules, update P1-02 handoff, move task to `completed/`, repair tracker links and commit only P1-02 files. | P1-02 marked complete only when code, direct tests and MySQL evidence agree. |

### Wave B — Finish Phase 1 contracts

| Task slices | Detailed work | Required output |
|---|---|---|
| P1-03.1–P1-03.2 | Inventory native, revlog, repair and analytics producers; define versioned native/external payload shapes and bounded fields. | Before/after producer matrix and canonical provenance contract. |
| P1-03.3–P1-03.5 | Add typed allowlist/range/depth/size validation; construct final event once; classify legacy gaps; test malformed, oversized and native/external parity. | Shared validation seam, zero partial event write, audit categories and handoff. |
| P1-04.1–P1-04.2 | Inventory server executable, client evaluator, wire decoder, IndexedDB/session decoder; define active/deprecated/lease-only/retired states and safety window. | Support matrix and retirement ADR/runbook. |
| P1-04.3–P1-04.4 | Add status introspection and stable unavailable behavior; test new, active old, retired restore and historical read scenarios. | Exact-version cross-deploy compatibility proof; no latest-version fallback. |

### Wave C — Finish Phase 2 frontend correctness in ownership order

| Order | Task | Detailed work | Required output |
|---:|---|---|---|
| 1 | P2-02 | Replace boolean marker with synchronous owner token; guard answer, undo, restore, retry, regular/keepalive commit; release only by current owner after success/error/abort/unmount. | Same-tick `answer+answer`, `answer+undo`, `restore+answer`, `commit+answer` tests. |
| 2 | P2-03 | Require UUID event IDs, uniqueness, sequence `1..N`, monotonic lease-bounded offsets, exact card/session membership and all-or-none semantic metadata; atomically quarantine one bounded row per scope. | Strict fixture matrix and proof invalid rows never hydrate or recommit. |
| 3 | P2-04 | Remove `onAnswer` from reusable controls; emit one `ReviewAction`; map action to legacy rating only in a named adapter at the session boundary. | Single-emission tests and zero CSS/layout diff. |
| 4 | P2-05 | Compare no-bridge and browser-enforced trusted-input options; test editable elements, IME, repeat, focus transitions and forged messages using an isolated browser profile. | Approved safe implementation or explicit no-bridge ADR. |
| 5 | P2-06 | After P1-03/P2-04, define built-in Trigger ownership, primary/follow-up transaction, idempotency and fail-closed version behavior. | Design-only ADR and smallest approved implementation slice. |
| 6 | P2-07 | After P1-04/P2-03/P2-06, implement/approve wire v3 and measured v2 lease compatibility. | Server/client validators, telemetry without answer content and deploy matrix. |

### Wave D — Approve Phase 3 decisions before implementation

| Task | Detailed decision work | Required output |
|---|---|---|
| P3-05 | Reconcile P0 distribution with owned recursive decks, empty scopes, installed overlays and local-added content; choose exactly-one compatibility composition vs NoteType group; define deterministic order/default/error behavior. | Approved mixed-scope ADR linked by P3-01/P3-03. |
| P3-07 | Define definition/version/input/application/binding/effective-composition identities, repeated application, pin/fork/unpublish/detach lifecycle, stable `FieldDef.id` binding and exact material P3-04 freezes. | Approved logical contract with at least two alternatives; no DDL. |

### Wave E — Implement and prove Phase 3

| Order | Task | Detailed work | Required output |
|---:|---|---|---|
| 1 | P3-01 | Replace optional `composition_ids` list with one authorized canonical `composition_id`; define explicit old-client fallback and stable errors. | Exactly-one API tests for owned, unauthorized, stale, empty and ambiguous scopes. |
| 2 | P3-02 | Use one clone-aware effective-scope resolver for discovery and session query; apply selection in SQL before `MAX_SESSION_CARDS`. | Query-limit fairness plus source/local-added identity tests. |
| 3 | P3-03 | Fetch options and resolve learner/default selection before opening a session; opening request carries the approved ID. | One/zero/multiple-option UI states and zero visual regression. |
| 4 | P3-04 | Freeze selected identity, effective version/config/bindings and compatibility hashes for the lease; restore uses frozen material and fails stale/unsupported states explicitly. | Reload/deploy/stale tests with no live re-resolution drift. |
| 5 | P3-06 | Build a real publish/install `DeckInstall` fixture; prove source Cards, local-added Cards, discovery, open, query, snapshot and restore share one contract; remove physical-copy proof wording. | Overlay-only Phase 3 exit report and no-source-mutation assertions. |

### Wave F — INT-01 closeout

1. Re-run duplicate-writer, host-command, progress-authority and physical-clone searches.
2. Run Study backend/frontend, Connect/MCP and Decks/Flashcards modules plus the MySQL-safe evidence bundle.
3. Verify all task handoffs, relative links and completed-folder moves.
4. Record each Phase 0–3 exit gate as PASS/FAIL with an evidence link.
5. Issue a separate Phase 4 GO/NO-GO recommendation. Do not start migrations automatically.

## 6. Immediate next handoff after P1-02 closeout

P1-02 is complete and no new task was started during its closeout. The next separately authorized Phase 1 handoff is **P1-03 — ReviewEvent provenance hardening**.
