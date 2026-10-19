# P5-00 current-state inventory — code and production read-only snapshot

> Date: 2026-09-21 | Mode: INVESTIGATE | Status: **PARTIAL**. A fresh aggregate snapshot was collected from production MySQL at **2026-09-21 00:11:56 UTC**. A later two-run `wsgi_audit.py` bundle at **00:36:01 UTC** used a verified temporary `SELECT, SHOW VIEW` principal. No application-table DDL/DML, deploy, migration or serving-app startup occurred. The audit principal was created and then removed; the root-only checksummed evidence bundle remains on the VPS. P5-00 is not closed because writer disposition, browser offline state and old/new parity are still open.

## Authority and identity

| Entity | Observed identity and role | Evidence |
|---|---|---|
| `CardProgress` | `(user_id, card_id)` unique; mutable scheduler state and `revision` are operational authority | `models/card_progress.py`, `app/services/study_service.py`, `app/services/study_session_service.py` |
| `StudyProgressSubject` | `(learner_user_id, logical_note_key)` unique; `subject_generation` topology fence, `mirror_revision` derived counter | `models/study_progress_subject.py`, `app/services/study_progress_shadow_mirror_service.py` |
| `StudyProgressState` | 1:1 current exact Algorithm State per subject, presently a Phase 4 shadow | `models/study_progress_state.py`, migration `20260913_000039` |
| Session lease | v2/v3 session with Card `base_progress_revision`; server TTL is 24 hours | `models/study_session.py`, `models/study_session_card.py`, `app/services/study_session_service.py`, `app/validators/study_session_wire.py` |
| Pending browser/worker state | IndexedDB persisted session/pending batch; asynchronous worker commits Card progress | `frontend/src/features/study/session/sessionStore.ts`, `sessionRestore.ts`, `app/services/study_worker_service.py` |

## Mutation surfaces requiring one mode-aware boundary

| Surface | Observed authoritative mutation / transaction owner | P5 implication |
|---|---|---|
| Direct review / REST / MCP | `app/services/study_service.py::execute_native_review_command` writes Card progress and ReviewEvent, then commits; route/MCP adapters call it | NOTE action must not leave a direct Card writer. |
| Synchronous session | `app/services/study_session_service.py::commit_study_session` locks Card progress, replays, writes receipt/event and commits | Frozen Card CAS cannot be reinterpreted as Note CAS. |
| Async batch worker | `app/services/study_worker_service.py::process_single_study_batch` locks Card progress, replays, commits, then marks queue processed; retry/DLQ paths exist | Epoch/version pin and receipt/queue ordering need fault rehearsal. |
| Anki/Connect progress snapshot | `app/services/anki_sync_service.py::import_progress` uses per-item nested savepoints and P1-02 source refs. `app/services/flama_connect_package_service.py::receive_sync_package` delegates to it; `app/api/v1/flashcards/anki_imports.py::_upload_sync_package` owns the outer commit. The Connect dispatcher is not this entry point. | Snapshot is state-sync, not native Action; source hash/revision and per-item savepoint outcome must remain atomic. |
| Import card topology | `app/services/connect/import_cards.py` creates/migrates/deletes Card progress and commits import | New sibling Card must receive exact NOTE projection; removed Card cannot erase Note state. |
| Reset/delete and template/card lifecycle | `app/services/deck_management_service.py`, `app/services/flashcard_content_service.py`, `app/services/browse_card_service.py`, `app/services/mcp/note_tools.py`, `app/services/mcp/note_type_tools.py`, `app/services/share/cutover.py`, `app/services/seeding_service.py` mutate or delete Card progress, often through bulk delete. `app/startup_schema.py` also has a compatibility-repair SQL UPDATE. | Generation/epoch must fence sessions and protect clone source content; bulk SQL and startup repair must not bypass the canonical boundary for NOTE learners. |
| Phase 4 shadow/backfill | `app/services/study_progress_shadow_mirror_service.py` locks subject then sorted Card progress; backfill/reconciliation are derived | Must not overwrite NOTE authority state after cutover. |

Reader candidates include `app/repositories/study_repository.py`, `stats_query_repository.py`, `browse_card_repository.py`, `deck_tree_query.py`, `vocabulary_repository.py`, `app/services/dashboard_service.py`, session open/status, MCP and Connect export. This is a **candidate map**, not proof that every indirect path is covered. All currently serve Card-shaped state; no NOTE product-read selector exists.

## Fresh production evidence — aggregate, non-mutating

| Measure | Observed at 2026-09-21 00:11:56 UTC | Consequence |
|---|---:|---|
| MySQL / Alembic | 8.0.46 / `20260913_000039` | The local P5 migration 40 is **not deployed**. The two `study_authority_%` tables do not exist on production. |
| Users / `CardProgress` | 18 / 16,764 rows across 6 learners | Synthetic load must not infer capacity from 6 active learners. |
| Phase 4 subjects / states / contributors / availability | 0 / 0 / 0 / 0 | No current production old/new shadow hash comparison is possible. |
| Study sessions | 489 total: 363 committed, 126 open, all open expired by query time; 0 v3 | There is no unexpired server-side v2/v3 lease in this snapshot. It says nothing about browser IndexedDB or Redis jobs. |
| `study_session_batches` | 0 | Server batch table is empty; external queue state was not inspected. |
| Note / Card / deck install | 40,227 / 40,227 / 17 installs, all `logical_overlay` | Live data has no Card fan-in in the measured progress cohort; test 1:N and overlay synthetically. |
| Clone additions / note-field overrides / field-definition overrides | 0 / 0 / 0 | Empty present-day overlay mutations do not remove the required lifecycle paths. |
| Review events / Connect source Card refs / Connect source Note refs | 127,895 / 15,965 / 15,965 | External-source and history compatibility remain material. |

All 16,764 progress rows had a non-null Card ID, an existing Card and an existing Note. Grouping by `(learner_user_id, Note)` produced 16,764 groups, none with more than one progress row (maximum 1). The observed queue/mode distribution was `review/anki` 12,544; `review/legacy` 1,635; `learning/anki` 950; `learning/legacy` 865; `new/anki` 531; `relearning/anki` 178; `relearning/legacy` 61. Revision ranged from 1 to 13. Both `anki` and `legacy` codec values therefore need P5-03 golden/round-trip coverage.

Recent activity was not zero: 163 progress rows updated in the preceding day and 899 in seven days; 429 ReviewEvents were timestamped within a day and 1,775 within seven days. Latest progress update was 2026-09-20 12:18:07 UTC; latest review timestamp 2026-09-20 12:12:23 UTC. MySQL was in `STRICT_TRANS_TABLES` / `ONLY_FULL_GROUP_BY` mode among other flags; server default collation was `utf8mb4_0900_ai_ci`, application schema default `utf8mb4_unicode_ci`.

At a separate 2026-09-21 process check, the `flama.service` Gunicorn master and both workers had `STUDY_PROGRESS_SHADOW_WRITE_ENABLED`, `STUDY_PROGRESS_SHADOW_COMPARE_ENABLED`, `STUDY_PROGRESS_SHADOW_BACKFILL_ENABLED`, `STUDY_WIRE_V3_ENABLED`, and `STUDY_ASYNC_BATCH_ENABLED` **unset** in `/proc/<pid>/environ`; the deployed code defaults them off. Only those flag names/values were read, not other environment secrets. The configured Redis endpoint was reached without disclosing its URL; read-only `LLEN` returned **0 study queue** and **0 study DLQ** items. These observations do not prove the browser offline stores are empty or that no future request can enqueue a job.

### Verified SELECT-only production audit — 00:36:01 UTC

The deployed `scripts/run_phase4_preflight_bundle.py` ran `wsgi_audit.py` twice at one frozen UTC observation time. `scripts/run_p5_vps_preflight.py --production-readonly-audit` created a random localhost-only principal with `SELECT, SHOW VIEW` on `flama` only, verified the audit's MySQL privilege gate, then dropped and independently verified removal of that principal. The four evidence files are root-only under `/root/p5_readonly_preflight_tdjq26ph/` on the VPS; `sha256sum -c SHA256SUMS` passed for `run-1.json`, `run-2.json`, and `comparison.json`. There were **zero** remaining `p5audit_%` principals after cleanup. This audit created/dropped only that temporary MySQL account and wrote the root-owned evidence bundle; it did not write application data.

| Check | Verified result |
|---|---|
| Principal / MySQL | SELECT-only gate true; MySQL 8.0.46 |
| Two-run determinism | Equal reports, no differing paths; SHA-256 for each canonical report `08e2071dd5ac16026b67c571eca58076bf593c6f17ab17026d4960e89e78b57a` |
| Phase 4 preflight | PASS/PASS, no blockers, all accounting partitions true; schema drift 0; database and deployed repository both head `20260913_000039` |
| Progress topology | 16,764 progress rows, 16,764 single-progress learner/Note groups, 0 fan-in, 0 unresolvable subjects |
| Server-side work | 0 active unexpired open sessions, 0 active enqueued DB batches, 0 active Connect import sessions; Redis study queue/DLQ both 0; 126 expired-open session rows remain |
| Full architecture audit | WARN/WARN, no blockers; warning records need disposition before NOTE eligibility |

The WARN items are 1,780 stale-revision `StudySessionCard` records attached to open sessions, 595 ReviewEvents pointing to detached/deleted Cards, 4 events with null Algorithm, 4 with unknown provenance, 5 versioned events missing a required provenance field, 126 expired-open sessions, and 4 sessions with invalid config snapshots. These are **not** evidence of a currently active lease; nor may they be silently accepted as suitable NOTE initialization/history. The Phase 4 preflight PASS with empty shadow tables proves schema/accounting safety, **not** old/new state parity or authority readiness. Browser IndexedDB/offline records cannot be inspected server-side; Redis was separately checked as described above.

### Finding — remaining indirect-path and runtime evidence

- **Observed:** local code has multiple independent commit owners and v2/v3 Card-CAS leases; no Phase 5 authority route exists. A source search found Card progress references across study, Connect, content lifecycle, share and analytics modules.
- **Evidence:** files in the mutation table; `app/settings.py` has only default-off Phase 4 shadow flags; `20260913_000039` is the last pre-P5 migration in this code baseline.
- **Potential concern:** switching a learner by a global flag or by one API path would leave other writers/readers on Card authority and create split brain.
- **Impact:** accepted stale reviews, state/event mismatch, lost rollback projection or incorrect due counts.
- **Unknowns:** old/new reconciliation while shadow tables are empty, browser offline clients, in-flight work outside the observed DB/Redis snapshot, full indirect writer/reader coverage, warning-to-cohort disposition, real traffic shape and representative multi-user/overlay load. The checksummed audit is point-in-time, not rollout evidence.

## Required before closing P5-00

1. **Done for current deployed head:** the dedicated SELECT-only two-run audit and checksum verification above. Before rollout, repeat it after any deploy/data change and establish a safe Phase 4 shadow rollout/reconciliation policy; empty shadow tables cannot yield an old/new diff. Triage the seven WARN categories per candidate learner rather than blanket-waiving them.
2. Turn this inventory into a tested disposition for every writer/reader and transaction owner, including bulk deletes, Connect package upload, startup compatibility repair, all reset/delete/rekey paths, import/export and queued jobs. No NOTE enrollment until every path is mode-aware or explicitly blocked.
3. Recheck live v2/v3 lease, DB batches and Redis queue/DLQ at rollout; treat browser offline storage as unbounded until explicit protocol/version fencing is in place. The observed zero server-side work at this snapshot is not a license to reinterpret old v2/v3 tokens.
4. Feed observed topology into P5-09 disposable MySQL synthetic workload. No minimum real-user count is required for the eventual production canary.
