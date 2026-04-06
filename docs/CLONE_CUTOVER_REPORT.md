# Clone Cutover Report (Logical Overlay Only)

> Follow-up implementation plan cho clone edit -> request -> review/merge:
> `docs/DECK_CHANGE_REQUEST_SIMPLE_PLAN.md`

Tai lieu nay mo ta TRANG THAI HIEN TAI cua code, khong giu cac tham chieu controller cu nua.

## 1) Current Runtime Inventory

### a) Shared deck install

Entry points:

1. Route: `app/routes/flashcards/share.py::POST /api/shared/decks/<deck_item_id>/install`
2. Service: `app/services/flashcards_share_service.py::install_shared_deck_item_for_user`

Status:

1. Dang chay tren model moi.

Current behavior:

1. Install bat buoc `source_deck_id`.
2. Moi install moi luon tao `DeckInstall.clone_mode='logical_overlay'`.
3. Install luu `source_deck_id`, `source_note_type_id`, `source_owner_user_id`, `base_snapshot_at`.
4. He thong clone local deck subtree + tao `DeckCloneDeckMap`.
5. He thong KHONG copy source `Note`/`Card` cho learner.
6. Neu shared deck bind vao source note type, install flow van tao `NoteTypeInstall` + installed note type copy cho installer.

### b) Read / render / browse / study

Entry points:

1. `app/routes/vocabulary.py`
2. `app/services/flashcards_share_service.py`
3. `app/repositories/flashcards_share_repository.py`

Status:

1. Dang dung source scope + snapshot + overlay.

Current behavior:

1. Browse list/detail resolve clone scope tu `DeckInstall` + `DeckCloneDeckMap`.
2. Study/browse doc source notes/cards trong source scope cua install.
3. Render layer apply schema overlay + note field overrides.
4. Source rows tao sau `base_snapshot_at` khong hien trong install cu.

### c) Clone edit path

Entry points:

1. `app/routes/vocabulary.py::PATCH /api/browse/cards/<card_id>`
2. `app/routes/flashcards/share.py::POST /api/shared/decks/<deck_item_id>/clone/overlay`
3. `app/services/flashcards_share_service.py::upsert_clone_overlay`

Status:

1. Dang ship.

Current behavior:

1. Browse edit cho clone cards chi ghi vao `DeckCloneNoteFieldOverride`.
2. API overlay rieng ghi schema + note deltas vao cac bang `DeckClone*`.
3. Source note khong bi mutate truc tiep.
4. Clone browse edit van reject:
   - tag edit cho cloned cards
   - move cloned cards sang deck local khac

### d) Legacy cutover

Entry points:

1. Startup hook trong `app/__init__.py`
2. CLI `flask clone-cutover-overlay [--no-fail-on-mismatch]`
3. Service `app/services/flashcards_share_service.py::cutover_clone_model_to_overlay_only`

Status:

1. Dang duoc giu de xu ly install cu.

Current behavior:

1. Target set la install co `clone_mode != 'logical_overlay'` hoac null.
2. Cutover build lai `DeckCloneDeckMap` neu can.
3. Cutover sinh schema overlay rows + note field overrides tu local full-copy data cu.
4. Cutover remap `CardProgress` tu local copied cards sang source cards.
5. Sau khi validate tuong duong, local copied notes/cards cu bi xoa.

## 2) Old-model Behavior Removed Khoi Runtime Paths

1. New installs khong con tao copied notes/cards cho learner.
2. `USE_NEW_CARD_MODEL` da bi bo khoi app bootstrap.
3. `DeckInstall.clone_mode` tren luong install moi la overlay-only.
4. `legacy_copy` hien chi con xuat hien trong test fixture va compatibility cutover path, khong phai luong install runtime.

## 3) Migration / Backfill Entry Points

1. Startup:
   - `app/__init__.py` goi `cutover_clone_model_to_overlay_only(...)`
2. CLI:
   - `flask clone-cutover-overlay [--no-fail-on-mismatch]`
3. Strictness control:
   - startup co the dung `FLASHCARDS_SHARE_CUTOVER_FAIL_ON_MISMATCH`

## 4) Verification Proof Points

Integration tests da cover cac proof point quan trong:

1. `test_shared_deck_install_clone_cards_visible_in_browse_api`
   - clone deck browse/study duoc source cards qua local deck map
2. `test_shared_deck_install_clones_source_note_type_for_installer`
   - install van tao `NoteTypeInstall` khi co `source_note_type_id`
3. `test_shared_deck_clone_overlay_saves_delta_only_and_updates_render`
   - schema + note overlay rows duoc persist, render thay doi dung, learner khong co local copied notes
4. `test_shared_deck_install_stress_grows_pointer_rows_not_note_rows`
   - scale tang bang `DeckCloneDeckMap`, khong bang note copy
5. `test_cutover_migrates_legacy_full_copy_install_to_overlay`
   - install cu duoc cutover sang overlay va remap progress

## 5) Follow-up Gap Sau Cutover

Cutover da xong phan "clone local overlay edit". Repo hien tai VAN CHUA co:

1. draft diff request
2. sync/conflict state machine
3. owner review inbox
4. approve/reject/merge vao source

Follow-up plan hien tai nam o:

1. `docs/DECK_CHANGE_REQUEST_SIMPLE_PLAN.md`

## 6) Residual Risks

1. Legacy installs co lich su mo ho hoac deck tree/note pairing khong khop se fail loudly de tranh silent corruption.
2. Source notes/cards/field defs tao sau snapshot van invisible voi install cu cho toi khi co chien luoc sync/request phu hop.
3. Merge-back flow request/review/merge chua ton tai, nen current model dung o local overlay edit.
