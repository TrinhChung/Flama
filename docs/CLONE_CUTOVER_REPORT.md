# Clone Cutover Report (Logical Overlay Only)

> Follow-up implementation plan for clone edit -> request -> review/merge flow:
> `docs/DECK_CHANGE_REQUEST_SIMPLE_PLAN.md`
>
> Mandatory principle: if the root issue is data model/schema, prefer DB change over
> workaround logic in routes/services.

## 1) Inventory & Audit

### a) Clone deck / install deck / get deck
- `app/controllers/flashcards_share_controller.py::install_shared_deck_item_for_user`
  - Status: migrated to new model only.
  - Change: install now requires `source_deck_id`, always writes `clone_mode='logical_overlay'`, always creates pointer deck subtree map.
- `app/routes/flashcards.py::POST /api/shared/decks/<deck_item_id>/install`
  - Status: migrated to new model only.
  - Change: install pipeline now calls overlay-only install flow; legacy branch removed.
- `app/routes/vocabulary.py::browse/study APIs`
  - Status: migrated to new model only.
  - Change: read/render paths resolve clone scope from source decks + snapshot + overlay deltas.

### b) Copy note_type / copy defs / copy notes/cards
- Deck install auto-copy note type in `install_shared_deck_item_for_user`
  - Status: removed.
  - Change: removed auto `NoteTypeInstall` + cloned note type creation in deck install pipeline.
- Full-copy clone notes/cards (legacy data)
  - Status: migrated via cutover migration.
  - Change: legacy local notes/cards -> source snapshot + note field overrides + progress remap.
- Def-level differences
  - Status: migrated to overlay payload where needed.
  - Change: cutover builds `updated_defs` / `disabled_def_ids` / `added_defs` from local-vs-source field defs.

### c) Read/render deck (render/study/browse/export)
- `app/routes/vocabulary.py` browse list/detail/update
  - Status: migrated.
  - Change: clone rows/details use overlay-computed values and local deck mapping.
- `app/routes/flashcards.py` study next/answer
  - Status: already overlay-based; retained.

### d) Edit deck / edit note / edit note_type
- Browse edit for clone cards (`PATCH /vocabulary/api/browse/cards/<id>`)
  - Status: migrated.
  - Change: writes note deltas into `DeckCloneNoteFieldOverride`; no source-note mutation.
- Deck/note-type marketplace edit
  - Status: source binding hardened (`source_deck_id` required for shared deck items).

## 2) Old-model Artifacts Removed

- Removed legacy install branch:
  - `legacy_copy` path in deck install flow.
- Removed deck-install side-effect auto note type copy:
  - removed `auto_note_type_installed` behavior in deck install response/audit.
- Removed obsolete runtime feature toggle:
  - `USE_NEW_CARD_MODEL` config removed from app bootstrap.
- Removed model enum branch for legacy mode:
  - `DeckInstall.clone_mode` moved from enum-with-legacy to plain string (overlay-only semantics).

## 3) Migration / Backfill Results

### Migration entrypoints
- Startup cutover hook:
  - `app/__init__.py` calls `share_ctrl.cutover_clone_model_to_overlay_only(fail_on_mismatch=True)`.
- Manual one-shot command:
  - `flask clone-cutover-overlay [--no-fail-on-mismatch]`.

### Cutover algorithm summary
- Target set: `deck_installs` with `clone_mode != 'logical_overlay'` (or null).
- For each install:
  1. Resolve source/local roots, ensure/construct deck map.
  2. Pair local legacy notes with source snapshot notes by mapped deck + deterministic ordering.
  3. Build schema overlay deltas (defs) from local-vs-source note type defs.
  4. Build note field overrides so rendered overlay equals legacy local note content.
  5. Remap learner `card_progress` from local copied cards to source cards.
  6. Validate migrated rendered values equal pre-cutover local values; fail on mismatch.
  7. Delete legacy local copied notes/cards.

### Verification sample (integration test)
- Test: `test_cutover_migrates_legacy_full_copy_install_to_overlay`
  - Migrated installs: `1`
  - Failed installs: `0`
  - Post-cutover:
    - legacy local note deleted
    - overlay row created (`DeckCloneNoteFieldOverride`)
    - learner progress moved from local card to source card
    - install mode normalized to logical overlay

## 4) Proof of No Legacy Path Remaining

### Keyword grep checks
- `legacy_copy` in app/models/tests/docs: `0` results.

### Single model behavior proof points
- Deck install now requires source deck and creates pointer+snapshot install only.
- Browse/study/edit clone all read/write via snapshot+overlay pipeline.
- Legacy full-copy installs are transformed or fail loudly (no silent skip).

## 5) Residual Risks

- Legacy installs with ambiguous historical structure (e.g., deck tree mismatch, note count mismatch, template mismatch) intentionally fail cutover with explicit error to avoid silent data corruption.
- Def-level mapping for deeply customized legacy note types is heuristic (position-based); mismatch still fails at equivalence validation stage.
