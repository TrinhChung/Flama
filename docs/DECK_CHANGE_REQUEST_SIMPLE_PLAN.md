# Deck Clone Change Request - Current Baseline and Next Plan

Tai lieu nay phai duoc doc nhu sau:

1. Phan "baseline" ben duoi mo ta code DA CO trong repo hien tai.
2. Phan "next plan" chi la de xuat cho feature request/review/merge CHUA implement.
3. Khong duoc doc tai lieu nay theo kieu "toan bo ben duoi la backlog tuong lai" nhu phien ban cu.

## 1) Muc tieu

Feature "deck change request" duoc dat tren nen clone overlay hien tai, khong thay the no.

Muc tieu cua phase tiep theo:

1. User clone deck sua local thi thay ro minh da doi gi.
2. User co the submit request gui owner duyet.
3. Truoc khi submit bat buoc sync voi upstream de giam conflict.
4. Neu conflict thi user resolve xong moi duoc submit.
5. Owner approve/reject va merge thay doi vao source.

## 2) Current Baseline (code da co)

### 2.1 Shared deck install

Entry points:

1. Route: `app/routes/flashcards/share.py`
2. Service: `app/services/flashcards_share_service.py::install_shared_deck_item_for_user`
3. Models chinh:
   - `models/deck_marketplace_item.py`
   - `models/deck_install.py`
   - `models/deck_clone_deck_map.py`
   - `models/flashcard.py`

Hanh vi hien tai:

1. Install bat buoc `DeckMarketplaceItem.source_deck_id`.
2. Moi install moi deu tao `DeckInstall.clone_mode='logical_overlay'`.
3. Install luu:
   - `source_deck_id`
   - `source_note_type_id`
   - `source_owner_user_id`
   - `base_snapshot_at`
4. He thong clone local deck tree + tao `DeckCloneDeckMap`.
5. He thong KHONG copy source `Note`/`Card` sang user hoc.
6. Neu deck item bind `source_note_type_id`, install flow van tao `NoteTypeInstall` + installed note type copy cho installer.

### 2.2 Read / browse / study clone

Code chinh:

1. `app/routes/vocabulary.py`
2. `app/services/flashcards_share_service.py`
3. `app/repositories/flashcards_share_repository.py`

Hanh vi hien tai:

1. Clone scope duoc resolve tu `DeckInstall` + `DeckCloneDeckMap`.
2. Browse/study doc source notes/cards trong source scope, sau do apply snapshot + overlay.
3. Source rows tao sau `base_snapshot_at` khong hien trong clone scope hien tai.
4. Cac helper quan trong:
   - `resolve_clone_scope_for_local_deck`
   - `resolve_clone_scope_for_card`
   - `build_clone_schema_view`
   - `apply_clone_note_field_overrides`

### 2.3 Clone edit hien tai

Code chinh:

1. `app/routes/vocabulary.py::PATCH /api/browse/cards/<card_id>`
2. `app/routes/flashcards/share.py::POST /api/shared/decks/<deck_item_id>/clone/overlay`
3. `app/services/flashcards_share_service.py::upsert_clone_overlay`

Hanh vi hien tai:

1. Browse edit cho clone card chi ghi vao `DeckCloneNoteFieldOverride`.
2. API overlay hien co support:
   - `updated_defs`
   - `disabled_def_ids`
   - `added_defs`
   - `removed_added_def_ids`
   - `ordered_def_ids`
   - `note_field_overrides`
3. Browse edit hien tai co rao chan co y:
   - khong cho move cloned card sang deck local khac
   - khong cho edit tags tren cloned card
4. Source note/source card/source deck khong bi mutate truc tiep trong clone edit flow.

### 2.4 Legacy cutover

Code chinh:

1. `app/__init__.py`
2. `app/cli.py::clone-cutover-overlay`
3. `app/services/flashcards_share_service.py::cutover_clone_model_to_overlay_only`

Hanh vi hien tai:

1. Startup goi cutover overlay-only tu dong.
2. CLI co `flask clone-cutover-overlay [--no-fail-on-mismatch]`.
3. Legacy full-copy installs chi con duoc ho tro nhu input cho cutover, khong phai runtime steady state nua.

## 3) Schema hien tai phai xem la baseline bat buoc

1. `DeckInstall`
2. `DeckCloneDeckMap`
3. `DeckCloneFieldDefOverride`
4. `DeckCloneAddedFieldDef`
5. `DeckCloneFieldOrderOverride`
6. `DeckCloneNoteFieldOverride`
7. `NoteTypeInstall` van la mot phan cua install flow khi shared deck bind vao source note type

Ket luan:

1. Repo da chot huong overlay-only cho clone deck.
2. Feature deck change request phai build tren cac bang overlay hien co.
3. Khong co co so de quay lai mo hinh full-copy clone.

## 4) Nhung gi CHUA co trong code

Tinh den hien tai repo CHUA co:

1. Bang `deck_change_requests`
2. Bang `deck_change_request_items`
3. Bang `deck_change_request_conflicts`
4. API:
   - build draft diff
   - sync truoc submit
   - resolve conflict
   - submit request
   - approve/reject/merge
5. Owner inbox/man hinh review request
6. Merge-back flow tu overlay vao source
7. `last_synced_at` / `last_sync_status` tren `deck_installs`

Noi cach khac:

1. Repo da co local overlay edit.
2. Repo chua co request/review/merge state machine.

## 5) Mandatory Design Principles

Nguyen tac bat buoc cho phase tiep theo:

1. Giu overlay-only model, khong mo lai `legacy_copy`.
2. Khong cho clone write truc tiep vao source rows.
3. Neu van de nam o data model/schema, uu tien sua DB schema truoc.
4. Tranh cach "khong sua DB, chi chat them logic route/service" cho nghiep vu request/review/merge.
5. Diff/request/merge phai build tu overlay rows + snapshot scope hien co.
6. Khong lam vo semantics browse/study/install da ship.

## 6) Scope hop ly cho v1 request/review/merge

### In-scope

1. Build draft diff tu overlay rows hien co:
   - field def update
   - field def disable
   - added field
   - field order override
   - note field override
2. Sync truoc submit.
3. Detect conflict.
4. User resolve conflict.
5. Owner approve/reject.
6. Merge vao source + ghi audit.

### Out-of-scope o v1

1. Local deck tree changes trong installed root (`create/move/rename/delete`) vi hien tai do la local-only behavior.
2. Tag edit cho cloned cards.
3. Move cloned cards sang deck local khac.
4. Multi-branch/review threads/event sourcing.
5. Auto-merge upstream notes/cards tao sau snapshot.

## 7) Minimal DB Changes de xuat cho feature chua implement

### 7.1 New table: `deck_change_requests`

Muc dich: 1 request review/merge tu 1 clone install.

Cot de xuat:

1. `id` (uuid, pk)
2. `deck_install_id` (fk -> `deck_installs.id`, index)
3. `deck_item_id` (fk -> `deck_marketplace_items.id`, index)
4. `requester_user_id` (fk -> `users.id`, index)
5. `owner_user_id` (fk -> `users.id`, index)
6. `title` (varchar 255)
7. `description` (text, nullable)
8. `status` enum/string:
   - `draft`
   - `needs_sync`
   - `has_conflict`
   - `pending_review`
   - `approved`
   - `rejected`
   - `merged`
   - `closed`
9. `install_snapshot_at` (datetime) - snapshot cua install luc request duoc tao
10. `last_synced_at` (datetime, nullable)
11. `submitted_at`, `reviewed_at`, `merged_at` (datetime, nullable)
12. `review_comment` (text, nullable)
13. `created_at`, `updated_at`

Index:

1. `(owner_user_id, status, updated_at desc)`
2. `(requester_user_id, status, updated_at desc)`

### 7.2 New table: `deck_change_request_items`

Muc dich: materialize diff de user/owner xem va duyet.

Cot de xuat:

1. `id` (uuid, pk)
2. `change_request_id` (fk -> `deck_change_requests.id`, index)
3. `change_type` enum/string:
   - `note_field_set`
   - `note_field_remove`
   - `field_def_update`
   - `field_def_disable`
   - `field_def_add`
   - `field_order_update`
4. `source_ref_id` (nullable) - source note / source field def
5. `local_ref_id` (nullable) - local overlay row id neu can
6. `path_label` (varchar 255, nullable)
7. `before_value` (json, nullable)
8. `after_value` (json, nullable)
9. `is_conflict` (bool, default false, index)
10. `created_at`, `updated_at`

Index:

1. `(change_request_id, change_type)`
2. `(change_request_id, is_conflict)`

### 7.3 New table: `deck_change_request_conflicts`

Muc dich: luu conflict va cach resolve.

Cot de xuat:

1. `id` (uuid, pk)
2. `change_request_id` (fk -> `deck_change_requests.id`, index)
3. `item_id` (fk -> `deck_change_request_items.id`, index)
4. `conflict_type` enum/string:
   - `note_field`
   - `field_def`
   - `field_order`
5. `source_ref_id` (varchar 64)
6. `upstream_value` (json)
7. `local_value` (json)
8. `base_value` (json, nullable)
9. `resolution_mode` enum/string nullable:
   - `keep_mine`
   - `keep_upstream`
   - `manual`
10. `resolved_value` (json, nullable)
11. `resolved_by` (fk -> `users.id`, nullable)
12. `resolved_at` (datetime, nullable)
13. `created_at`, `updated_at`

Index:

1. `(change_request_id, resolved_at)`
2. `(change_request_id, conflict_type)`

### 7.4 Small extension cho bang cu

`deck_installs` co the them:

1. `last_synced_at` (datetime, nullable)
2. `last_sync_status` (varchar 32, nullable)

Ly do:

1. Giup UI biet clone dang stale hay da sync.
2. Khong thay the `base_snapshot_at`; day chi la metadata cho request flow.

## 8) API / Workflow de xuat

### Step A - Build draft

1. API: `POST /api/shared/decks/<deck_item_id>/change-requests/draft`
2. He thong scan overlay rows cua install va build `deck_change_request_items`.
3. Neu chua co thay doi thi tra `400`.

### Step B - Sync truoc submit

1. API: `POST /api/shared/decks/<deck_item_id>/change-requests/<id>/sync`
2. He thong:
   - doc source data hien tai trong clone scope
   - so sanh voi overlay diff item
   - neu upstream doi cung entity/property thi tao conflict
3. Ket qua:
   - khong conflict -> request quay ve `draft`
   - co conflict -> request sang `has_conflict`

### Step C - Resolve conflict

1. API: `POST /api/shared/decks/<deck_item_id>/change-requests/<id>/conflicts/<conflict_id>/resolve`
2. Payload:
   - `resolution_mode`: `keep_mine` | `keep_upstream` | `manual`
   - `resolved_value` (bat buoc khi `manual`)
3. Khi tat ca conflict duoc resolve -> request tro lai `draft`.

### Step D - Submit request

1. API: `POST /api/shared/decks/<deck_item_id>/change-requests/<id>/submit`
2. Rule:
   - bat buoc request vua sync xong
   - khong con conflict chua resolve
3. Chuyen status sang `pending_review`.

### Step E - Owner review / merge

1. API owner:
   - `POST .../<id>/approve`
   - `POST .../<id>/reject`
2. Approve:
   - apply diff item vao source deck/source note/source field defs
   - ghi audit
   - cap nhat status `merged`
3. Reject:
   - status `rejected`
   - luu ly do vao `review_comment`

## 9) Non-obvious constraints tu code hien tai

1. `base_snapshot_at` khong chi an notes/cards moi. `build_clone_schema_view()` con loc `FieldDef.created_at <= snapshot_at`, nen field moi duoc merge vao source sau snapshot se khong tu dong hien trong install cu neu khong co chien luoc resync ro rang.
2. `NoteTypeInstall` copy ton tai song song voi source note type. Feature request/review/merge khong duoc nham installed note type copy la source of truth.
3. Stress test hien tai verify scale bang pointer rows (`DeckCloneDeckMap`), khong bang local note copies.
4. Browse edit clone hien tai chi cover note field overrides; schema-level diff/edit dang di qua API overlay rieng.

## 10) Files can xem truoc khi implement

1. `app/routes/flashcards/share.py`
2. `app/routes/vocabulary.py`
3. `app/services/flashcards_share_service.py`
4. `app/repositories/flashcards_share_repository.py`
5. `models/deck_install.py`
6. `models/deck_clone_deck_map.py`
7. `models/deck_clone_field_def_override.py`
8. `models/deck_clone_added_field_def.py`
9. `models/deck_clone_field_order_override.py`
10. `models/deck_clone_note_field_override.py`
11. `docs/CLONE_CUTOVER_REPORT.md`

## 11) Testing checklist toi thieu cho phase moi

1. Clone user co overlay rows -> tao draft co item dung loai.
2. Upstream doi cung entity/property truoc submit -> sync tao conflict.
3. Resolve het conflict -> submit thanh cong.
4. Owner approve -> source data doi dung item.
5. Owner reject -> source khong doi.
6. Submit khi chua sync -> fail dung message.
7. Submit khi con conflict -> fail dung message.
8. Merge xong khong lam vo browse/study/install da ship.
