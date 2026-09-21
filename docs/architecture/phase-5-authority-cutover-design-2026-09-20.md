# Phase 5 — learner/Note authority cutover design (draft)

> Date: 2026-09-20 | Mode: DESIGN | Status: **PROPOSED, NOT APPROVED**
>
> Baseline commit: `develop` at `263b65e`. On 2026-09-21, an inert LEGACY-only storage slice was added in the worktree; see the [physical-schema ADR](./phase-5-authority-fence-adr-2026-09-21.md). No Phase 5 runtime authority route, NOTE enrollment or production cutover exists.
>
> Entry: [P4-11](../task/decoupling/P4-11_MYSQL_ROLLOUT_REHEARSAL.md) is [closed only for pre-release development](./phase-4-p4-11-pre-release-closeout-2026-09-20.md), and [INT-02 is closed](./phase-4-int02-closeout-2026-09-20.md) with full integration evidence. Deferred production-load/fault/limit risks are mandatory at P5-09 before enablement. A fresh 2026-09-21 [aggregate production read-only snapshot](./phase-5-p5-00-inventory-2026-09-21.md) confirmed head `20260913_000039`; it is not the full SELECT-only Phase 5 preflight.

This draft elaborates [the canonical Phase 5 scope](./study-interaction-trigger-algorithm-plan.md). The two-table LEGACY-only physical foundation is fixed for the current P5-02 slice; exact NOTE routing, lock/wire/rollback contracts still need P5-01 closure. Operational thresholds and the release go/no-go belong to P5-09/G5-P before the owner-directed production canary.

## 1. Current evidence and authority boundary

| Material | Observed owner today | Evidence | Phase 5 implication |
|---|---|---|---|
| Current scheduler state and conflict revision | `CardProgress` keyed by learner/Card; `card_id` is nullable | [`models/card_progress.py`](../../models/card_progress.py), [`study_service.py`](../../app/services/study_service.py), [`study_session_service.py`](../../app/services/study_session_service.py) | No reader/writer may treat the new state as authority before a fenced cutover. |
| Derived learner/Note subject | Unique `(learner_user_id, logical_note_key)` with topology `subject_generation` and **derived** `mirror_revision` | [`models/study_progress_subject.py`](../../models/study_progress_subject.py), [P4-02 ADR](./phase-4-progress-identity-fanin-revision-adr-2026-09-10.md) | Neither current counter is an authoritative Note-level CAS token. |
| Versioned current Algorithm State | One `StudyProgressState` row per subject; exact identity, bounded JSON and hashes | [`models/study_progress_state.py`](../../models/study_progress_state.py), [P4-03 ADR](./phase-4-algorithm-state-availability-adr-2026-09-12.md) | Can be promoted only after an explicit authority revision and full rollback projection contract. |
| Card-shaped availability and raw lineage | Contributor/availability rows are keyed to current CardProgress/Card evidence | [`models/study_progress_contributor.py`](../../models/study_progress_contributor.py), [`models/study_progress_availability.py`](../../models/study_progress_availability.py) | Phase 5 preserves Card compatibility; Note-level presentation/addressing cleanup belongs to Phase 6. |
| Session and wire | Session row pins wire v2/v3, Algorithm/config, 24-hour expiry; `StudySessionCard` freezes Card `base_progress_revision` | [`models/study_session.py`](../../models/study_session.py), [`models/study_session_card.py`](../../models/study_session_card.py), [`study_session_wire.py`](../../app/validators/study_session_wire.py) | Existing leases cannot silently cross an authority epoch. v3 semantic metadata alone is not a Note CAS token. |
| History and external source | `ReviewEvent` remains analytics/history; P4 history facts are derived; Anki snapshots use P1-02 revision/hash rules and revlog is history-only | [`models/review_event.py`](../../models/review_event.py), [`models/study_progress_history_fact.py`](../../models/study_progress_history_fact.py), [P1-02 contract](../task/decoupling/completed/P1-02_EXTERNAL_PROGRESS_REVISION_CONTRACT.md) | State-sync, native Action, immutable history and initializer input remain separate commands/materials. |
| Runtime switches | Shadow write/compare/backfill and wire-v3 issuance default off; none grants read authority | [`app/settings.py`](../../app/settings.py) | A new authority-routing mechanism must be explicit and default LEGACY. |

The [2026-09-20 rehearsal](./phase-4-reconciliation-rollout-rehearsal-2026-09-20.md) proves a local 16,424-row shadow comparison and small isolated VPS tests, not a production authority rollout. P4-11's load/fault gaps were explicitly deferred for development progress; [INT-02](./phase-4-int02-closeout-2026-09-20.md) later passed full tests and a fresh local MySQL re-probe. Production enablement still requires synthetic multi-user/overlay/fault proof independent of live user count.

### Finding A — one progress identity, several current Card rows

- **Observed:** learner/Note is the agreed target subject, but native/session/Connect paths still address learner/Card progress. Equivalent fan-in keeps every contributor; divergence has no arbitrary winner.
- **Evidence:** [P4-02 ADR](./phase-4-progress-identity-fanin-revision-adr-2026-09-10.md), [`study_progress_shadow_mirror_service.py`](../../app/services/study_progress_shadow_mirror_service.py), [`study_repository.py`](../../app/repositories/study_repository.py).
- **Potential concern:** promoting one Note state while leaving a sibling Card writer on old authority creates split brain; selecting one Card as the projection winner loses state.
- **Impact:** stale review acceptance, incorrect due/order or rollback to a different scheduler state.
- **Unknowns:** the 2026-09-21 [aggregate snapshot](./phase-5-p5-00-inventory-2026-09-21.md) has one CardProgress per learner/Note and 17 logical-overlay installs, but the distribution and mutation traffic must be refreshed at cutover; synthetic 1:N/overlay load remains mandatory.
- **Alternatives Considered:** (A) keep per-Card authority indefinitely; (B) use one Note authority with complete per-Card compatibility projection.
- **Trade-offs:** A avoids a cutover but cannot deliver the agreed identity; B adds write amplification and requires full lifecycle coverage.
- **Recommendation:** B, with no cohort enrollment until every affected Card projection is lossless and reconciled.
- **Migration Implications:** additive authority routing/revision and transition evidence; no Card or progress deletion.

### Finding B — derived counters cannot be reused as authority revision

- **Observed:** `subject_generation` fences topology/reset/rekey; `mirror_revision` counts successful derived projection writes. Session CAS currently uses `CardProgress.revision`.
- **Evidence:** [`models/study_progress_subject.py`](../../models/study_progress_subject.py), [P4-02 sections 8–9](./phase-4-progress-identity-fanin-revision-adr-2026-09-10.md#8-generation-revision-and-backfill-fencing), [`models/study_session_card.py`](../../models/study_session_card.py).
- **Potential concern:** repurposing either Phase 4 counter would make old snapshots and new commands interpret the same number differently.
- **Impact:** ABA conflicts after reset/rekey or accepted stale offline commits.
- **Unknowns:** whether MySQL workload measurements favor an authority revision on the subject row or a separate keyed authority row.
- **Alternatives Considered:** (A) overload `mirror_revision`; (B) add an independent monotonic `authority_revision` and a fenced enrollment epoch.
- **Trade-offs:** A saves DDL but breaks issued semantics; B costs one additive migration and explicit token plumbing.
- **Recommendation:** B; review exact physical placement in P5-01.
- **Migration Implications:** old counters and codecs remain readable throughout Phase 5.

### Finding C — v3 is not the Phase 5 wire by default

- **Observed:** backend recognizes v2/v3 and v3 issuance is default-off, but session cards/events still use Card identity and `base_progress_revision`.
- **Evidence:** [`study_session_wire.py`](../../app/validators/study_session_wire.py), [`models/study_session_card.py`](../../models/study_session_card.py), [`frontend/src/features/study/types.ts`](../../frontend/src/features/study/types.ts), [`app/settings.py`](../../app/settings.py).
- **Potential concern:** issuing an unchanged v3 session after Note cutover would pin the wrong conflict token.
- **Impact:** invalid replay/idempotency or client/server state disagreement.
- **Unknowns:** observed v2/v3 leases, offline/pending batches and client-version distribution at rollout.
- **Alternatives Considered:** (A) reinterpret v3 `base_revision`; (B) issue a new explicitly versioned Note-subject envelope while keeping frozen v2/v3 decoders.
- **Trade-offs:** A is superficially smaller but changes issued semantics; B adds frontend/worker dual-reader work and a lease drain.
- **Recommendation:** B (provisional `study-session.v4`); P5-01 must freeze the contract and P5-05 must implement the exact schema and rollout negotiation.
- **Migration Implications:** retain v2/v3 executable handlers through their actual active lease/job horizon, not merely a timer.

## 2. Required invariants

1. Exactly one operational authority is selected for a learner at a time. Routing is persisted and fenced in MySQL, not inferred from a process-local flag or Deck/Template context.
2. For an enrolled learner, one valid `(learner_user_id, logical_note_key)` state and independent monotonic authority revision govern all Cards, Templates, StudyModes and overlay contexts for that Note. Quarantined, missing or unsupported subjects are not enrollable.
3. An accepted material native Action atomically commits the new Note state/revision, complete lossless legacy projection for every active Card contributor, canonical `ReviewEvent`, scheduler-grade history fact and idempotency receipt. Failure of a required projection rolls back the whole unit; no independent commit in helpers.
4. A no-op, duplicate delivery or typed conflict changes no authority revision and appends no duplicate fact. Reset/delete/rekey advances the subject generation/fence and invalidates affected sessions before a later write.
5. Existing Card IDs, P1-02 external IDs/hash/revision rules, logical-overlay source/local Note identity and immutable source content survive cutover. No copied source Notes/Cards or per-Template progress is introduced.
6. Only exact registered Algorithm/Trigger/state/config versions execute. `scheduler_mode="fsrs"` or a Template choice never silently switches Algorithms. The current proven executable remains `legacy-anki/1.0.0` until a separately accepted target exists.
7. Rollback to `CardProgress` is allowed only while **every** accepted new state has a complete, checked legacy projection. Once a new-only state/Action is accepted, rollback is forward repair or verified backup restore, not a flag flip.
8. History occurrence and ingestion times, imported snapshot versus revlog semantics, and lifecycle tombstones remain distinct. Review history is not replayed to guess present state.
9. Generic due/order/analytics reads evaluate frozen timezone/day-boundary/learn-ahead context. Phase 5 must not make time-dependent `eligible_now` a stored fact or deduplicate Card presentation before Phase 6.
10. New DDL is additive. No `CardProgress`, Card, Template, session, event or decoder purge is in Phase 5.

## 3. Target architecture and alternatives

The proposed target promotes the existing subject/state storage rather than introducing a second progress representation. **These are proposed contracts, not approved DDL:**

| Component | Proposed responsibility | Physical decision to finalize at P5-01 |
|---|---|---|
| `study_authority_enrollments` | Persist learner mode/epoch; absent row means LEGACY/0. The current additive migration accepts LEGACY only. | PK/FK and current DDL fixed in [physical-schema ADR](./phase-5-authority-fence-adr-2026-09-21.md); NOTE-capable CHECK widening, audit and lock protocol remain later gates. |
| `study_progress_subjects` | Keep identity, topology generation and derived mirror revision unchanged. | Do not repurpose or alter Phase 4 counters in the current slice. |
| `study_authority_subject_tokens` | Independent subject generation/revision/hash CAS companion row; no Phase 4 table rewrite. | Current DDL fixed; first-create and state↔token atomic invariant still need P5-04. |
| `study_progress_states` | Store exact current authoritative Algorithm identity/payload/hash for NOTE learners after cutover. | Existing row remains derived until NOTE routing is complete; future command must atomically align state and token. |
| Contributors/availability | Preserve per-Card raw lineage and query anchors as a compatibility projection of the one Note state. | Update-all-siblings transaction cost, new-Card materialization and detached mapping. |
| `CardProgress` | During the reversible window, complete write-through legacy authority projection with current Card IDs and revisions; never independently decide NOTE-user state. | Exact round-trip encoder for every accepted state/Algorithm and all fields, including nullness/pointers. |
| `ReviewEvent` and history facts | Event remains analytics/history; current transition also writes exact Trigger/composition/Algorithm/state-schema and before/after hashes to a versioned scheduler-grade fact. | Whether additive columns are needed or bounded versioned payload/fact fields already cover all required queries. |

### Physical storage choice

| Alternative | MySQL/locking and normalization | Compatibility/operability | Decision |
|---|---|---|---|
| A. Promote existing subject + separate 1:1 state; add independent companion token and enrollment | Reuses unique learner/Note identity and bounded JSON; one extra small token row/lock per NOTE transition | Avoids altering Phase 4 tables or historical migration 39; requires atomic state↔token proof | **Chosen for inert schema slice**, pending P5-01 MySQL lock/write-amplification proof |
| B. Add a parallel authority table while leaving shadow inert | Clear physical isolation but duplicates identity/state, locks, indexes and reconciliation | Easier hard boundary at first; two Note representations can diverge and require another consolidation | Fallback only if A cannot preserve issued shadow semantics |

### Routing and rollback choice

| Alternative | Benefit | Risk | Decision |
|---|---|---|---|
| Persist learner enrollment/epoch and fence each mutation against it | One mode across all Notes/Decks/devices/workers; controlled cohort and auditable switch | Extra keyed read/lock and migration; lock order must be proved | **Recommended** |
| Global/app-instance flag or hash-percentage without persisted epoch | Easy rollout config | Split-brain across workers/deploys and in-flight sessions; rollback cannot be proven per learner | Reject for authority selection |
| NOTE write with lossless synchronous legacy projection | Immediate operational rollback while contract is representable | Extra writes per sibling Card; failure must roll back accepted Action | **Required for initial Phase 5 cohort** |
| NOTE-only write with forward-repair rollback | Supports new-only states sooner | No safe instant fallback; higher blast radius | Defer until separately approved post-compatibility gate |

MySQL work must measure narrow subject-row contention, sibling-Card write amplification, transaction length, deadlocks, JSON size and the new enrollment fence under direct/session/worker/Connect concurrency. Application-level canonical hashes remain binary/collation-independent. Exact indexes and thresholds come from measured plans, not estimates in this draft.

## 4. Proposed transaction, read and enrollment contracts

**LEGACY mode:** preserve the P1/P4 command and `CardProgress` authority; Phase 4 mirror/compare remain diagnostics. A new flag must not turn Phase 4 shadow writes into implicit authority.

**NOTE mode native Action:** resolve authorized effective Note/overlay context; pin the persisted learner enrollment epoch; lock subject before sorted Card contributors (preserving the existing session/Connect prefix locks); verify `(subject_generation, authority_revision, state hash, exact Algorithm/config)` from the request; execute the fixed built-in Trigger against exact decoded state; write state and increment authority revision once; project the result to every current sibling `CardProgress`; flush canonical event/receipt and versioned history fact; finalize contributor/availability lineage; commit once at the existing service boundary. An enrollment change, stale token, unknown decoder, divergence or non-projectable value fails closed before commit. P5-01 must prove the precise shared/exclusive enrollment lock and global order on MySQL with two connections; no lock order is silently invented here.

**External state-sync:** resolve the same learner/Note identity and enrollment epoch, but never pretend an Anki snapshot is a user Action. Preserve P1-02 source-ref/hash, `force` authorization, typed conflict/no-op and revlog history-only behavior. An applied snapshot increments Note authority revision and projects Card compatibility in its existing per-item savepoint; source ref and state stay atomic. Reset, deletion, clone rekey and new sibling-Card materialization use named lifecycle commands and generations, not a generic last-write-wins update.

**Reads:** a request selects one persisted mode/epoch. NOTE users read state/availability through a dedicated repository/evaluator; LEGACY users retain current `study_repository.py`/stats paths. During canary, execute a non-serving comparison in the same fixed context. No page may quietly combine NOTE due counts with LEGACY state, and no fallback to legacy on a NOTE read error is allowed unless the learner is explicitly and safely transitioned back.

**Enrollment:** all eligible subjects must be reconciled; no active v2/v3 lease, accepted job or pending offline batch may cross the epoch. A fenced transaction rechecks eligibility, projection completeness and current hashes before changing the learner mode. New sessions after enrollment use a Note-authority wire; old clients unable to negotiate it remain LEGACY or receive an explicit upgrade-required response. Rollback reverses enrollment only after every NOTE transition's legacy projection has been checked under the same fence. Stale client submissions after an epoch change return typed conflict/expiry, never write the other authority.

## 5. Wire, history and Algorithm scope

P5-01 should specify, and P5-05 should implement, a new immutable wire family (provisional `study-session.v4`, matching commit/batch variants) with `logical_note_key`, subject generation, authority revision, enrollment epoch, exact Algorithm/state/config/Trigger identity, frozen composition and compatibility `card_id`. It must define replay/idempotency, mixed-version denial and receipt semantics in Python, TypeScript, REST and worker code. The existing v2/v3 decoders remain pinned to their issued leases. The maximum server lease is currently 24 hours; actual open sessions, pending jobs and browser persistence must be measured, and an operational safety margin approved before retiring issuance/execution.

History facts for new NOTE transitions must carry exact before/after state hashes, Trigger/action/composition/Algorithm identity, occurrence/ingestion, provenance and lifecycle linkage. Current-state initialization must not reconstruct from partial `ReviewEvent` streams. An Algorithm switch command is allowed only with an accepted target executable/decoder/initializer, frozen history cut and completeness policy, subject CAS and idempotency. This phase defines/tests the fail-closed switch seam; it does **not** infer an FSRS executable from labels or automatically enable a new Algorithm (new capabilities are Phase 8). Any switch yielding state not losslessly expressible in `CardProgress` requires a separately approved forward-only rollback policy and cannot be part of the initial reversible cohort.

## 6. Zero-data-loss sequence and stop rules

1. **Entry:** carry P4-11's documented pre-release waiver and the closed INT-02 handoff, then collect a fresh read-only production schema/data/lease/traffic bundle. Reconcile every eligible learner/Note and record quarantine/unresolvable disposition.
2. **Expand:** approve exact authority ADR; add enrollment/revision/schema and dual decoders with LEGACY defaults. Verify real `wsgi.py`/Gunicorn flags-off boot and migration/backup on disposable MySQL matching production.
3. **Write-through proof:** implement a single transaction command and lossless Note→all-Card projection; compare old/new states, hashes, due/order and idempotency under fixed contexts. No NOTE product reads yet.
4. **Read/canary:** issue new wire only to eligible users, fence/enroll a tiny approved cohort, serve Note authority reads/writes and keep legacy projection. Increase cohort only after measured error, latency, locks and reconciliation remain within approved limits.
5. **Cutover/closeout:** route all canonical readers/writers through the mode-aware boundary, drain/expire old leases under policy, run two independent full audits and prove rollback. Keep old storage and decoders; contraction is Phase 9.

Hard stop on any split-brain write, unprojectable accepted state, unknown exact version, stale lease accepted across epoch, source-note mutation in overlay flow, lost event/receipt, unexplained state/due/order difference or failed backup/restore. Quantitative latency, lock, retry, replication/storage and cohort limits are **not yet known**; P5-09 must set them from rehearsal and baseline, not from the SSH-tunnel probe timings.

## 7. Open decisions / needs verification

- P4-11 and INT-02 are closed for development handoff. This does not approve Phase 5's exact design or production cutover. P5-09 must discharge the deferred production risks using controlled synthetic concurrency, not a minimum live-user count.
- Refresh production head, schema drift, row/fan-in/quarantine counts, real installed-source/local contexts, active v2/v3 leases, accepted jobs and client-version distribution immediately before design approval.
- Prove exact lossless encoding of **every** accepted Note state to all legacy CardProgress fields and pointer semantics. If this cannot be done, narrow the initial cohort/Algorithm contract; do not label a query-only projection reversible.
- Decide physical authority revision/enrollment DDL, lock order, transaction ownership and all read consumers with MySQL plans and two-connection tests.
- Decide whether existing history fact payload suffices for Trigger/composition identity or an additive version/column is required; never rewrite issued history silently.
- Decide measured operating limits and approved rollback horizon. No production data copy, live authority switch or destructive reverse migration is authorized by this document.
