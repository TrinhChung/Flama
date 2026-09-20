# Phase 4 external/lifecycle mirror verification — 2026-09-14

> Task: [P4-08](../task/decoupling/P4-08_EXTERNAL_LIFECYCLE_MIRROR.md)
>
> Baseline: `develop` at `bd96abc` (`p07`)
>
> Result: implemented and locally verified; intentionally uncommitted
>
> Authority: `CardProgress` remains the only operational current-state read/write authority

## Outcome

P4-08 extends the P4-07 same-transaction learner/Note coordinator to every discovered non-native `CardProgress` writer and destructive lifecycle owner. The mirror has no internal commit or rollback. Unexpected mirror failures propagate to the existing transaction/savepoint owner; expected external conflict/no-op outcomes retain their P1-02 behavior and do not advance mirror revision.

`STUDY_PROGRESS_SHADOW_WRITE_ENABLED` remains default-off. No runtime path reads scheduler state, due status, ordering or conflict data from the Phase 4 shadow tables.

## Writer and lifecycle coverage

| Authority owner | Adapter point | Mirror/disposition behavior | Atomic owner |
|---|---|---|---|
| modern Anki progress package | `anki_sync_service.import_progress` | applied/forced snapshots only; `CONNECT_PROGRESS_SNAPSHOT`; source Card/Note lineage; conflict/no-op/unresolved does not finalize | existing per-record savepoint |
| legacy `cardsProgress` import | `connect.import_cards._migrate_cards_progress` | applied records only; `CONNECT_LEGACY_PROGRESS`; one finalization per Note; source Note lineage | existing per-note savepoint and media compensation unit |
| Anki revlog | `anki_sync_service.import_reviews` | append normalized `CONNECT_REVLOG` facts; never executes scheduler or changes current progress/revision/pointer/subject mirror revision | existing per-source-Card savepoint |
| deck progress reset | `deck_management_service.reset_deck_progress` | resolves owned and effective clone-scope Cards, cancels open sessions, deletes learner progress and writes `TOMBSTONED_RESET` with generation advance | existing reset transaction |
| Browse single/batch Card delete | `browse_card_service` | explicit progress delete; contributor detach or Note tombstone; no ORM callback dependency | existing service transaction |
| Note/Template/NoteType purge | `flashcard_content_service` | explicit progress delete before content cascade; detach/tombstone lifecycle facts | existing content transaction |
| MCP Note/batch delete and NoteType template removal | `mcp.note_tools`, `mcp.note_type_tools` | same lifecycle adapter and explicit bulk progress delete | existing MCP service transaction |
| deck purge/delete | `deck_management_service.delete_deck_subtree` | all affected learner subjects tombstoned before Card/Note deletion | existing deck-delete transaction |
| seed replacement | `seeding_service`, `seed_flama_template.py` | old subjects tombstoned before replacement content deletion | existing seed transaction |
| import template reconciliation | `connect.import_cards._upsert_import_card` | removed template Cards detach contributors inside the Note savepoint | existing per-note savepoint |
| legacy clone cutover | `share.cutover.migrate_legacy_clone_install_to_overlay` | old/new subjects locked globally before P1-02 local/source progress locks; old subject rekeyed, destination mirrors only final authority | existing per-install cutover savepoint |

Repository-wide `CardProgress` create/delete inventory was rechecked after the adapters were added. Native direct/MCP/session/worker creation and updates remain owned by P4-07. The non-native creation paths are the two Connect writers above; every runtime bulk progress delete and the cutover rekey path now has an explicit P4-08 adapter.

## Generation, lineage and completeness corrections

- A topology/lifecycle generation advance releases current live identities and retains the prior contributor rows in their original generation. Surviving authoritative rows are projected into new contributor rows. Existing history facts therefore continue to reference evidence from the generation in which they occurred.
- Source Card/Note lineage is copied forward for surviving contributors during topology rollover and refreshed when an applied external snapshot supplies newer source hashes.
- External snapshot state begins as `HISTORY_SNAPSHOT_ONLY`. Imported revlog facts are `HISTORY_IMPORTED_PARTIAL` or `HISTORY_REPAIRED_PARTIAL`; a contributor combining snapshot/native/revlog evidence becomes `HISTORY_MIXED_PARTIAL` conservatively.
- Revlog-only work can update contributor history completeness and append history facts, but does not change subject generation, subject mirror revision, `CardProgress`, or latest-event pointer.
- Reset/delete/rekey writes bounded `study-progress-lifecycle-evidence.v1` material with old/new topology, authority and lineage hashes.

## Lock and transaction contract

The preserved lock order is:

1. existing transaction-owner prefix lock, such as Connect source identity, StudySession/Batch or install;
2. all affected learner/Note subject rows in binary `(learner_user_id, logical_note_key)` order;
3. all affected `CardProgress` rows in `(card_id, progress_id)` order;
4. authoritative mutation/source/event work;
5. one final mirror/lifecycle recomputation per subject;
6. commit or rollback by the existing owner.

Lifecycle discovery uses non-locking reads, then `prepare_mirror_scopes` acquires every subject before any progress row. After the explicit authority delete, a locking range check proves that no targeted learner/Card progress survived and holds the delete fence until the content transaction finishes; a missing delete fails closed. Clone cutover performs preparation once across all old/new Note pairs before invoking the retained P1-02 merge routine. No adapter independently commits or rolls back.

## Verification evidence

Commands run from `D:\Project\nihongo`:

```text
python scripts/run_tests.py --module connect_mcp,decks,flashcards,seed,study --backend-only
```

Result: `755` tests across `68` backend files passed in `249.06s`.

Focused flag-on suites also passed:

```text
python -m unittest tests.test_study_progress_shadow_mirror tests.test_anki_import_api
python -m unittest tests.test_flashcard_api_integration.FlashcardApiIntegrationTests.test_cutover_migrates_legacy_full_copy_install_to_overlay
```

These cover applied/forced/no-op/conflict/unresolved snapshot outcomes, source lineage, legacy import, revlog import/repair/idempotency, native-after-external completeness, immutable generation contributors, partial Card deletion, Note deletion, reset followed by review, logical-overlay cutover and mirror failure rollback.

Disposable local MySQL probes loaded connection settings from the existing local `.env`, created uniquely named databases, upgraded `20260913_000038 -> 20260913_000039`, ran checks, and dropped the databases in `finally`:

```text
python scripts/probe_phase4_shadow_mirror_mysql.py
python scripts/probe_phase4_external_lifecycle_mysql.py
```

The P4-07 probe passed concurrent native session/direct/MCP fan-in, worker execution and mirror-fault rollback. The P4-08 probe passed external savepoint rollback, revlog history-only behavior, multi-subject reset, Note deletion with retained history, post-reset generation fencing, unchanged source content and a bounded two-connection native-vs-external race without deadlock.

`python -m compileall` for changed Python modules and `git diff --check` also passed. Logged `datetime.utcnow`, SQLAlchemy legacy-query and intentional fault-path messages are pre-existing test warnings, not failures.

## Rollback and remaining scope

Immediate rollback is to keep `STUDY_PROGRESS_SHADOW_WRITE_ENABLED=false`. Existing `CardProgress`, P1-02 conflict/savepoint behavior, reset, delete and cutover authority continue unchanged; additive evidence remains for diagnosis.

P4-09 still owns resumable backfill. P4-10 owns full shadow reconciliation, and P4-11 owns broader MySQL load/restart/rollback rehearsal. P4-08 does not authorize production enablement, shadow reads, Algorithm switching or Phase 5 authority cutover.
