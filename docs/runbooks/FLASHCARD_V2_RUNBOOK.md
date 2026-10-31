# Flashcard V2 Runbook [CANONICAL BASELINE]

## Architecture Baseline
- Production schema uses MySQL + integer user/deck IDs; flashcard entities (`NoteType`, `FieldDef`, `Template`, `Note`, `Card`, `MediaAsset`) use string UUID IDs.
- Canonical architecture is `Deck -> NoteType -> FieldDef -> Template -> Note -> Card`. Legacy tables have been fully retired and dropped.
- Multi-template support is standard for all note types.
- Field rename jobs execute synchronously within request handling.
- Shared deck installs use logical overlay only. With Published Base enabled, learners read the latest published content plus their personal `DeckClone*` edits; source notes/cards are not copied. The older snapshot branches remain pending P6 cleanup.
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
- Published Base installs read current published Notes; legacy `base_snapshot_at` metadata is retained for compatibility.
- Install clones the local deck subtree and creates `NoteTypeInstall` when the deck item is bound to a source note type.
- Clone edits are stored in overlay tables such as `DeckCloneNoteFieldOverride`, not by mutating source notes/cards.
- Development/test maintenance can run clone cutover through `cutover_clone_model_to_overlay_only(...)` when `STARTUP_RUN_MAINTENANCE=True`; production startup is passive.

## Contributing saved Note changes

1. Edit a Note in an installed deck and save it. These personal changes remain private.
2. Open the deck's **Đóng góp chỉnh sửa**, review the changes, and enter a title/description.
3. Choose **Gửi đóng góp**. Draft preparation and comparison with the original content run automatically.
4. If conflicts are found, the detail screen asks for field-level decisions. Save the decisions, then choose **Gửi đóng góp** there. No manual draft/sync step is required.
5. The owner reviews the contribution; acceptance and publication remain separate owner actions.

The send button requires saved content changes; title/description alone do not create
a contribution. Pending contributions cannot be submitted again from the form.
If personal changes differ from the reviewed preview, refresh/review is required.

`POST /api/shared/decks/<deck_item_id>/change-requests/send` accepts `title`,
`description`, and the preview's `expected_overlay_fingerprint`. It owns one
transaction, preserves matching drafts and conflict resolutions, and returns
`pending_review` or `has_conflict`. A retry with the same saved edits returns the
existing pending contribution. The original draft/sync/submit endpoints remain
available for older clients; the SPA uses the combined action.

Verify with `npm run test:collab` in `frontend/`, and from the repository root:

```powershell
$env:FLAMA_MYSQL_TESTS = '1'
.\.venv\Scripts\python.exe scripts/run_tests.py --file tests/test_contribution_send_mysql.py --backend-only
```

The MySQL tests create and remove a generated loopback schema, preserving the
configured application database.

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
