# Phase 4 — entry investigation

> Date: 2026-09-09 | Mode: INVESTIGATE | Repository baseline: `880ff1b` (`phase3`)
>
> Evidence: repository code and existing reports; no current production database inspection
>
> Related plan: [Phase 4 execution plan](../task/decoupling/P4_EXECUTION_PLAN_2026-09-10.md)

## 1. Runtime and authority

Production entry is `wsgi.py -> create_app()`, served by Gunicorn. Current config is loaded through `app/settings.py`; maintenance is implemented in `app/startup.py` and defaults off outside tests. `create_audit_app()` explicitly disables startup mutations. Descriptions of unconditional boot-time maintenance in older guidance must not be used to construct a Phase 4 migration command.

| Data | Authority now | Main write boundary | Phase 4 relevance |
|---|---|---|---|
| Current learning state | `CardProgress`, unique `(user_id, card_id)` | native transaction, session commit/worker, external snapshot/import, reset/cutover | sole operational authority during shadowing |
| Presentation identity | `Card(note_id, template_id)` | content/import and compatibility lifecycle | maps existing progress to a Note; retain Card IDs |
| Review facts | `ReviewEvent` and Connect provenance | canonical native recorder / external revlog importer | history is incomplete for reconstructing current state |
| Active lease | `StudySession`, SessionCards/Commits and browser snapshot | session service plus frontend durable store | preserve pinned handler, config, selection and receipt semantics |
| Overlay identity | source/local Note/Card plus `DeckInstall` maps | shared-deck install and overlay services | progress learner is the installer; source Note owner is a different role |

## 2. Findings

### F1 — Card-to-Note fan-in needs a fresh accounting boundary

- **Observed:** `CardProgress.card_id` is nullable; current uniqueness is learner/Card. Multiple Templates can create multiple Cards for one Note. The audit detects learner/Note fan-in, but its equivalence predicate does not cover every provenance field, including `last_review_event_id`.
- **Evidence:** `models/card_progress.py:13`, `models/card_progress.py:53`, `models/card.py:14`; `app/services/study_architecture_audit_service.py:1161` and `:1179`.
- **Potential concern:** collapsing rows using only matching scheduler fields can lose contributor identities/history; choosing the newest or maximum revision silently chooses a winner.
- **Impact:** a Note mirror can become misleading even though its selected Card state looks valid. A later ordinary review of just one sibling can make a previously equivalent group divergent.
- **Unknowns:** current production counts, full contributor equality, and frequency of newly divergent groups require refreshed evidence. The 2026-08-29 audit is historical.
- **Planning owner:** P4-01/P4-02/P4-07; preserve all contributors and quarantine ambiguity.

### F2 — Runtime CardState is a normalized view, not a lossless archive

- **Observed:** `card_state_from_progress` supplies defaults, normalizes queues, derives dates from policy/timezone, and does not include all burial, leech, timestamp, and latest-event fields.
- **Evidence:** `app/repositories/study_repository.py:26`, `:41`, `:116`; full column set in `models/card_progress.py`.
- **Potential concern:** using this serializer alone for backfill loses raw values and can manufacture historical state from current time/config.
- **Impact:** an apparently successful shadow comparison could hide irreversible data loss.
- **Unknowns:** which production rows require default/date normalization; actual timestamp precision and label/provenance distribution.
- **Planning owner:** P4-03/P4-07; raw preservation and executable projection need separate verification.

### F3 — Availability depends on query context and the clock

- **Observed:** due resolution uses timezone, local day boundary, current time, learn-ahead, and effective deck options. Overlay Cards can be scheduled through a local deck while retaining source identity.
- **Evidence:** `app/repositories/study_repository.py:247`, `:280`, `:319`; `app/services/study_service.py:182`; `app/services/scheduler_config_service.py`.
- **Potential concern:** one stored `eligible` boolean or an unqualified per-Note policy hash becomes stale after a boundary or policy change.
- **Impact:** incorrect due counts/order without any progress-row mutation.
- **Unknowns:** live policy variation across installed contexts and query load.
- **Planning owner:** P4-03/P4-10; distinguish state-derived availability anchors from context/time evaluation.

### F4 — Phase 3 frozen-artifact validation has remaining gaps

- **Observed:** `updateTemplateContent` rewrites templates/card keys in active snapshots; the durable store also contains Template update propagation. Restore validates a binding fingerprint prefix but does not recompute the digest or enforce the full artifact/binding relation. An unknown session-config schema is classified as legacy by the backend decoder.
- **Evidence:** `frontend/src/features/study/hooks/useStudySession.ts:980`, `frontend/src/features/study/session/sessionStore.ts:574`, `frontend/src/features/study/session/sessionRestore.ts:442`; `app/services/study_session_config.py:63`.
- **Potential concern:** these paths do not satisfy the full frozen-artifact claims in the accepted Phase 3 binding ADR.
- **Impact:** state mirroring should not build compatibility proofs on a snapshot whose binding and executable can disagree.
- **Unknowns:** complete reachable combinations of live edit, cross-tab sync, pending batch, and restore need regression fixtures.
- **Planning owner:** P4-00, a prerequisite correction task. Historical Phase 3 closeout remains historical evidence, not a waiver of this new finding.

**Resolution — 2026-09-10:** P4-00 disabled Template/Note propagation into active and persisted sessions, added canonical immutable relationship checks during frontend restore, enforced durable-batch `composition_id`, and made backend wrapper/binding decoding fail closed. Complete Study backend/frontend module tests passed; the frozen-session gate is reclosed.

Read-only reproduction of the unknown-schema branch on this baseline returned `legacy=True` and `selected_composition_id=None` for `study-session-config.v999`. The probe loaded only the pure config module with `runpy`; no app/database was started. This proves decoder classification, not acceptance of an entire forged commit.

### F5 — Mirror finalization belongs to existing transaction owners

- **Observed:** native REST/MCP share `execute_native_review_command` and `apply_native_review_mutation`; session/worker replay use the same mutation helper. Latest ReviewEvent pointers are finalized by transaction owners after flush. Direct review advances revision per command; a session batch advances once per touched Card. External imports use per-item savepoints and preserve partial-success behavior.
- **Evidence:** `app/services/study_service.py:352`, `:417`; `app/services/study_session_service.py:1021`; `app/services/study_worker_service.py`; `app/services/anki_sync_service.py:253`, `:459`.
- **Potential concern:** a mirror hook inside each Action sees intermediate state or misses final event pointers; a global after-commit hook breaks atomicity.
- **Impact:** mirror state can disagree with the committed authority or alter established retry/partial-success behavior.
- **Unknowns:** every reset, deletion, rekey, and first-row race must be included in the current writer inventory.
- **Planning owner:** P4-02/P4-08/P4-09; finalize once per affected learner/Note within the existing transaction/savepoint.

### F6 — Migration-only schema and startup-created metadata are different evidence

- **Observed:** `StudySessionBatch` is registered by the app factory, but a repository search found no `study_session_batches` entry in Alembic revisions. Startup can optionally call `db.create_all()`. No learner/Note progress mirror model exists at this baseline.
- **Evidence:** `app/__init__.py:97`, `models/study_session_batch.py:12`, `app/startup.py:50`, `migrations/versions/`.
- **Potential concern:** a `create_all` test database can pass while a migration-only installation has a different schema.
- **Impact:** Phase 4 cannot certify migration parity solely from SQLite fixtures. Async readiness remains an independent rollout concern.
- **Unknowns:** actual deployed batch table/constraints and Alembic head require environment evidence.
- **Planning owner:** P4-01/P4-06/P4-11; disposition existing drift separately and keep async issuance disabled unless its own gates pass.

## 3. Decisions already settled versus work still needed

Reuse the accepted P1-02 external conflict contract, P1-04 exact Algorithm lifecycle, P2 built-in Trigger/security boundary, P2-07 wire compatibility, and P3 exactly-one composition rule. Earlier open-question lists in the canonical plan predate these decisions.

Phase 4 still needs Note-level fan-in/revision rules, lossless current-state codecs, context-aware availability, state/history provenance and completeness, deletion/reset accounting, an additive physical design, resumable backfill, atomic mirrors, and MySQL reconciliation. Authoritative state cutover, repeated physical application storage, new Algorithms, history-based switch execution, and data purging belong to later phases.

## 4. Evidence limits

- Clean worktree at `880ff1b` before this documentation task; the previous implementation has been committed since the earlier chat handoff.
- Full-suite results cited by Phase 3 are prior-run evidence. This planning task did not rerun the full suite or inspect production.
- Existing MySQL reports do not certify current data distributions, performance, schema drift, or readiness for Phase 4 DDL.
- All proposed filenames, commands, flags, and schemas in the execution plan are deliverables to create, not claims that they already exist.
