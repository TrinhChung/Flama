# P5-04 — canonical mode-aware command, fenced CAS foundation

> Date: 2026-09-21 | Mode: IMPLEMENTED / INERT | Status: **PARTIAL**. The learner-prefix fence is active for native study entrypoints and one existing-state NOTE command plus durable receipt wrapper is implemented for locked test/rehearsal composition, but the physical schema and runtime still accept only LEGACY authority. No NOTE read route, enrollment or production switch exists.

## Outcome of this slice

`app/repositories/study_authority_repository.py::lock_study_authority_route` now provides the single learner authority prefix used by native study flows. It performs a MySQL locking/current read of the stable `users.id` row with `FOR SHARE`, then reads `study_authority_enrollments` under the same transaction. A missing enrollment resolves to immutable `(LEGACY, epoch=0)`; a persisted LEGACY epoch is returned exactly. NOTE, unknown mode, invalid epoch and missing learner fail closed with typed errors.

The same repository now provides the inert subject suffix `lock_study_authority_subject`: after the caller has locked the learner prefix and subject, it locks or first-creates the independent authority token, then locks current `StudyProgressState`. A first token starts at revision zero and copies the exact current semantic hash, or remains null when state is absent. Existing tokens are never reset. Subject generation, Phase 4 mirror revision, state presence and token/state hash divergence all fail closed. `verify_study_authority_cas` then checks the complete expected tuple `(enrollment epoch, subject generation, authority revision, semantic state hash)` with distinct conflict codes and validates the registered exact state decoder. These helpers do not commit, advance authority revision, or make NOTE reachable from a product route.

`app/services/study_authority_write_service.py::apply_study_authority_material_write` now provides the next inert layer for an **existing usable state**. It re-verifies the CAS, exact next-state decoder/hash and P5-03 projection, then re-hashes every locked `CardProgress` baseline immediately before any mutation. Only after the entire sibling vector passes does it stage the new `StudyProgressState`, advance the independent token exactly once and apply every encoded compatibility row. It never commits or rolls back, leaves `subject_generation` and the Phase 4 `mirror_revision` unchanged, rejects unchanged semantic state as a no-op, and rejects missing/stale/partial sibling inputs before mutation. The encoder result now retains each independently verified baseline revision/size/hash specifically for this anti-TOCTOU check.

`lock_study_authority_siblings` now supplies the independent complete-set proof consumed by that applicator. After subject/token/state locks, it takes a shared locking read of the live Note and its complete Card range, verifies the optional requested Card belongs to that Note, then locks exactly one learner-owned `CardProgress` per Card in Card-ID order. A source Note may belong to a marketplace publisher while the progress rows belong to the learner; this preserves the overlay-only model and never copies or mutates source content. Detached/noncanonical subject identity, an empty Card set, missing compatibility progress, the wrong learner or a Card outside the subject fail closed. The result is immutable and the write service no longer accepts a caller-provided progress map as completeness evidence.

This resolver starts only after an upstream entrypoint has authorized the effective local/source overlay context. It proves the physical Note/Card sibling vector, not release membership or install authorization. Missing compatibility-row creation, detached/rekey identity and external/lifecycle lock alignment remain P5-06 work.

`lock_study_authority_compatibility` extends that suffix through the current Phase 4 evidence rows. It locks exactly one active `StudyProgressContributor` and one `StudyProgressAvailability` for every independently resolved sibling, and rejects a stale generation, detached identity, missing row or cross-subject attachment. This is intentionally an existing-state gate: it does not fabricate missing evidence or treat a partial contributor vector as usable NOTE authority.

`app/services/study_progress_history_service.py::append_native_history_fact` is now the shared no-commit append primitive for scheduler-grade native history. It validates the canonical `ReviewEvent` envelope and exact learner/subject/generation/contributor/Card context, stores before/after hashes and runtime identity, and treats only a byte- and context-identical fact as replay. Reusing the event identity with different state hashes or metadata fails closed. The Phase 4 mirror now delegates to this primitive, so legacy shadow traffic and the future NOTE command cannot drift into two history encodings.

`app/services/study_authority_evidence_service.py::finalize_study_authority_evidence` now closes the existing-state compatibility-evidence suffix after the material write. It requires the exact lock snapshot, the complete projected sibling vector and a flushed canonical event whose reviewed Card has the matching Card-specific pointer. It remaps every projected row, refreshes contributor raw evidence, availability, pointer lineage and subject aggregate hashes, and rejects any semantic divergence. The independent `authority_revision` is never derived from or written by this step. `mirror_revision` advances once only after all derived evidence is valid because it retains its Phase 4 meaning—successful derived projection finalization—and is never accepted as a NOTE request CAS token. The compatibility snapshot captures the prior mirror revision plus contributor revision/raw hashes, so a repeated finalization or in-transaction evidence mutation fails with `STALE_AUTHORITY_EVIDENCE`.

`app/services/study_authority_command_service.py::apply_existing_state_note_review` now composes those primitives into one caller-owned transaction for an already materialized NOTE subject. It verifies that the scheduler transition started from the exact locked state, derives the next canonical Algorithm State directly from that transition, stages the canonical native `ReviewEvent`, flushes only to obtain its ID, encodes every sibling projection with the reviewed Card pointer, advances state/token, refreshes evidence, and appends the reviewed contributor's history fact. It never commits or rolls back. `study_service.stage_native_review_event` is event-only; the established direct/session/worker mutation path still invokes its existing leech and marketplace/install side effects separately. The P5-05 receipt wrapper now composes durable idempotency around this command; P5-06 side effects remain intentionally absent.

The storage review found no need for another history table: `ReviewEvent` plus `StudyProgressHistoryFact` cover immutable event and scheduler evidence. They do **not** constitute a universal command receipt. `ReviewEvent(user_id, client_event_id)` is nullable for current direct REST traffic, while `StudySessionCommit` is scoped to one session and its response. P5-05 therefore adds a separate generic receipt with a required operation key, exact request fingerprint and stored response; it does not reinterpret either existing mechanism.

The material applicator still deliberately rejects a subject with no current state. First-state creation cannot be safe until the same command creates or reconciles contributor/availability rows and subject status. The existing-state command now has a durable P5-05 receipt but is not a product command until it also has the P5-06 authorization/side-effect contract and wire/route integration. Therefore this foundation is not wired to REST, MCP, sessions or workers.

The fence is called before existing database row locks in:

- direct native reviews, shared by REST and MCP;
- study-session issuance;
- async batch admission;
- synchronous session commit;
- accepted worker batch execution.

Parsing and pure request validation may happen first, but no database mutation or workflow/subject/progress row lock may precede this learner prefix. The repository uses `no_autoflush`, so unrelated pending ORM objects cannot flush before the fence. It never commits or changes enrollment.

## Lock-order contract

The reviewed target order is:

1. learner `User` rows in ascending ID order: `FOR SHARE` for ordinary read/write/session admission; `FOR UPDATE` for mode/epoch transition, never lock upgrade;
2. locking/current enrollment read while the User fence is held;
3. existing workflow admission rows required by the entrypoint, in stable identity order: session/batch/import/source/install scope;
4. learner/Note subjects in `(learner_user_id, logical_note_key)` order;
5. subject authority token, current state and exact state hash;
6. shared locking read of the live Note and its Card range, then every sibling `CardProgress` row in Card-ID order, followed by contributor/availability compatibility rows;
7. append or finalize event, history fact, receipt/idempotency and audit evidence; commit once at the existing transaction owner.

Direct review currently follows `User → enrollment → subject (when Phase 4 mirror is enabled) → CardProgress → event/evidence`. Session/worker flows now follow `User → enrollment → session/workflow → subject → sorted CardProgress → event/receipt`. External import, Connect and clone lifecycle paths are not yet migrated; P5-06 must align their source-ref/install locks to this prefix and prove no reverse edge.

## Why this remains LEGACY-only

Migration 40 still enforces `mode_code = 'LEGACY'`. Even if a database is tampered or a newer schema is paired with this older runtime, observing NOTE returns `NOTE_AUTHORITY_UNAVAILABLE`; it never silently serves or mutates `CardProgress` as the fallback authority. This is a deployment-safety seam, not a NOTE implementation.

P5-04 can admit NOTE only after all of the following exist together:

- first-state contributor/availability materialization plus reset/rekey/ABA behavior;
- missing compatibility-row creation plus authorized release/overlay and detached/rekey identity handling;
- integrate the durable P5-05 receipt wrapper and P5-06 authorized side effects into every product transaction owner;
- two-connection conflict/duplicate/deadlock/fault rollback proof;
- a later CHECK-widening migration gated on every deployed writer/reader failing closed.

## Evidence and remaining gates

Six focused route-repository tests cover absent/persisted LEGACY, pending-object no-autoflush, invalid/missing learner, NOTE/unknown/invalid epoch and tampered NOTE data. Seven subject-CAS tests cover state/null first-create, existing-token preservation, learner/generation/state/mirror divergence, every CAS conflict component, LEGACY diagnostic mode and missing decoder. Five sibling-resolver tests cover publisher-owned source identity, complete learner progress, missing rows, requested-Card scope, detached/noncanonical identity, LEGACY mode and empty Card sets. Five material-write tests cover caller-owned rollback, exact commit, stale and incomplete projection, semantic no-op and the first-state safety gate. Seventeen authority-command/history/evidence tests additionally cover canonical event-only composition, rejection before event when legacy progress mutation is supplied, injected history or receipt failure with caller rollback, exact receipt replay, divergent request/provenance rejection and corrupt response detection, the complete compatibility lock, stale raw baseline, exact fact replay, divergent-hash rejection, missing availability, two-sibling evidence refresh with zero reconciliation diff, event-pointer mismatch, double-finalize rejection and caller-owned full rollback. Five receipt-schema tests cover migration and storage constraints. The focused P5 contract set passes 65 tests; the registered study backend matrix passes 281 tests across 31 files.

The disposable MySQL 8.0.40 probe proves all current locking layers: the absent-row shared/exclusive User barrier and repository route read, then revision-zero token initialization from exact current state. A second connection attempting `FOR UPDATE` on the same subject token times out with MySQL error 1205 while the holder retains the row lock. With the sibling resolver active, a second connection attempting to insert another Card for the same Note also times out, proving that the encoded Card set cannot gain a phantom sibling before transaction end. The probe executes the low-level applicator with a forced outer rollback, then executes the composed existing-state command plus receipt for the commit path: canonical event, authority revision `0→1`, exact two-sibling projection, refreshed contributor/availability/lineage, one exact scheduler history fact and one receipt all persist together. An exact retry replays the stored response without adding evidence. State/token hashes remain aligned. It reports `subject_canonical_command_commit=PASS`, `subject_command_receipt_commit=PASS` and `subject_command_receipt_replay=PASS`, uses and drops a random database, and reports `configured_database_modified=false`.

Current gate: **P5-04 is partial**. The safe LEGACY routing prefix, read/verify CAS, live-Note sibling and compatibility resolvers, canonical existing-state event/material/projection/evidence/history command, durable P5-05 receipt and caller-owned rollback proof are implemented. The product command still needs missing-row and first-state materialization, wire/route integration, overlay authorization and side effects, lifecycle handling, end-to-end duplicate/deadlock semantics and the remaining conflict/fault matrix before NOTE mode opens.
