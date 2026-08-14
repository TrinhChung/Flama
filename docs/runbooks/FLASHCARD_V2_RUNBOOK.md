# Flashcard V2 Runbook [CANONICAL BASELINE]

## Architecture Baseline
- Production schema uses MySQL + integer user/deck IDs; flashcard entities (`NoteType`, `FieldDef`, `Template`, `Note`, `Card`, `MediaAsset`) use string UUID IDs.
- Canonical architecture is `Deck -> NoteType -> FieldDef -> Template -> Note -> Card`. Legacy tables have been fully retired and dropped.
- Multi-template support is standard for all note types.
- Field rename jobs execute synchronously within request handling.
- Shared deck installs use logical overlay only: install pins a snapshot, clones the deck tree shell, and stores local clone edits in `DeckClone*` tables instead of copying source notes/cards.
- Deck Change Requests enable cloner contributions back to the source deck owner with conflict resolution.

## Environment & Commands
1. Install dependencies:
```powershell
pip install -r requirements.txt
```
2. Apply schema migration:
```powershell
flask --app wsgi.py db upgrade
```
3. Reseed or bootstrap data:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\reseed_db.ps1
```
4. Optional manual clone cutover for old deck installs:
```powershell
flask --app wsgi.py clone-cutover-overlay
```

## Verification Checklist
- Run full test suite: `python -m unittest discover -s tests -p "test_*.py"`.
- Open React SPA at `/study` and review cards.
- Install a shared deck from marketplace and verify logical overlay rows (`DeckCloneDeckMap`, `DeckInstall.clone_mode='logical_overlay'`).
- Verify media rendering with sandboxed iframe (`static/js/card_renderer_host.js`).

## Shared Deck Clone Notes
- Shared deck install creates `DeckInstall` with pinned `base_snapshot_at`.
- Install clones the local deck subtree and creates `NoteTypeInstall` when the deck item is bound to a source note type.
- Clone edits are stored in overlay tables such as `DeckCloneNoteFieldOverride`, not by mutating source notes/cards.
- Startup automatically runs clone cutover for old installs through `cutover_clone_model_to_overlay_only(...)`.

## Rollback Strategy
- For schema migration rollbacks, use Alembic: `flask --app wsgi.py db downgrade <revision>`.
- For production recovery, use DB backup/restore.
- Temporary recovery control: set `FLASHCARDS_SHARE_CUTOVER_FAIL_ON_MISMATCH=0` if you need the app to boot while auditing failed legacy installs.

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
