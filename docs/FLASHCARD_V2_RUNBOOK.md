# Flashcard V2 Runbook

## Assumptions (Explicit)
- Current production schema uses MySQL + integer user/deck ids. To stay backward-compatible, flashcard-v2 keeps `user_id` and `deck_id` as integer FKs; new entities use string UUID ids.
- Legacy `VocabularyEntry` rows do not store owner user. Migration command assigns migrated notes to one target user (`--user-id`, default: first user).
- Legacy rows map to a single `Legacy` template card. Multi-template support is enabled for new note types.
- Field rename job is implemented as synchronous background-job emulation (job record is created and completed in the same request).
- Shared deck installs now use logical overlay only: install pins a snapshot, clones the deck tree, and stores local clone edits in `DeckClone*` tables instead of copying source notes/cards.
- Legacy full-copy clone mode is only supported as cutover input, not as an active runtime mode.

## New Schema & Migration
1. Install dependencies:
```powershell
pip install -r requirements.txt
```
2. Apply schema migration:
```powershell
flask db upgrade
```
3. Run legacy backfill:
```powershell
flask flashcard-migrate-legacy --user-id <USER_ID>
```
4. Dry-run verification (no commit):
```powershell
flask flashcard-migrate-legacy --user-id <USER_ID> --dry-run
```
5. Optional manual clone cutover for old deck installs:
```powershell
flask clone-cutover-overlay
```

## Verification Checklist
- `COUNT(vocabulary_entries)` equals `COUNT(legacy notes for target user)`.
- `COUNT(vocabulary_progress where entry_id is not null)` equals `COUNT(vocabulary_progress where new_card_id is not null)`.
- `LegacyMigrationMap` row count equals `VocabularyEntry` row count.
- Open `/flashcards/study` and review at least 10 migrated cards.
- Open `/vocabulary/study/...` to confirm legacy study still works unchanged.
- Install one shared deck and confirm the learner gets pointer rows (`DeckCloneDeckMap`) and `DeckInstall.clone_mode='logical_overlay'`, not copied learner notes.

## Shared Deck Clone Notes
- Shared deck install creates `DeckInstall` with pinned `base_snapshot_at`.
- Install clones the local deck subtree and may also create `NoteTypeInstall` when the deck item is bound to a source note type.
- Clone edits are stored in overlay tables such as `DeckCloneNoteFieldOverride`, not by mutating source notes/cards.
- Startup automatically runs clone cutover for old installs through `cutover_clone_model_to_overlay_only(...)`.

## Rollback Strategy
- There is no runtime `USE_NEW_CARD_MODEL` rollback switch anymore.
- For clone-cutover rollout issues, use DB backup/restore as the real rollback path.
- Temporary recovery control only: set `FLASHCARDS_SHARE_CUTOVER_FAIL_ON_MISMATCH=0` if you need the app to boot while auditing failed legacy installs.
- Data rollback for migration run: execute backfill in `--dry-run` first, then real run.
- Schema rollback:
```powershell
flask db downgrade a2f8b3c9d4e0
```
- Legacy tables are untouched (`vocabulary_entries`, `vocabulary_progress`, etc.) and remain usable during transition.

## NoteType / Template Usage
- UI:
  - NoteType manager: `/flashcards/note-types`
  - NoteType detail + template editor + realtime preview: `/flashcards/note-types/<note_type_id>`
  - Dynamic note editor + media upload: `/flashcards/notes/new`
  - Study renderer (iframe sandbox): `/flashcards/study`
- API:
  - NoteType CRUD: `/api/note-types`
  - Field CRUD/reorder: `/api/note-types/<id>/fields...`
  - Template CRUD + preview: `/api/note-types/<id>/templates...`
  - Note CRUD: `/api/notes...`
  - Media upload: `/api/notes/<note_id>/media`
  - Study next/answer: `/api/study/next`, `/api/study/<card_id>/answer`

## Template Syntax
- `{{Field}}`: escaped output.
- `{{{Field}}}`: raw HTML (safe only for server-sanitized richtext/media HTML).
- `{{#Field}}...{{/Field}}`: render if field is non-empty.
- `{{^Field}}...{{/Field}}`: render if field is empty.

## Security Notes
- Render path: Mustache bind -> sanitize output (`bleach`) -> iframe sandbox render.
- Allowlist sanitizer blocks script/event-handler/javascript URLs/iframe/meta/object/embed.
- Media rendering only allows `/media/proxy/<asset_id>` output.
- CSP is set on preview/study endpoints:
  - `default-src 'none'; style-src 'unsafe-inline'; img-src /media/proxy/; media-src /media/proxy/; frame-ancestors 'self'`

## Test Plan Mapping
- Unit:
  - `tests/test_flashcard_renderer.py` (template parse/conditional/escaping/media + XSS cases 1-10)
- Integration:
  - `tests/test_flashcard_api_integration.py` (CRUD + preview + study fetch/submit + add-field-without-schema-change)
- Migration:
  - `tests/test_flashcard_migration.py` (legacy backfill + progress mapping + dry-run rollback)
- Existing scheduler/study regression:
  - `tests/test_anki_scheduler.py`
  - `tests/test_counter_logic.py`
  - `tests/test_study_integration.py`
