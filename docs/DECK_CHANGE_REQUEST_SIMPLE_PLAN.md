# Deck Clone Change Request - Simple Implementation Plan

## 1) Goal

Giai phap nay uu tien don gian, khong thay toan bo mo hinh clone hien tai.

Muc tieu v1:

1. User clone deck sua/bo sung du lieu thi nhin thay ro da thay doi gi.
2. User tao request gui chu so huu deck nguon de duyet.
3. Truoc khi submit request bat buoc sync voi upstream de giam conflict.
4. Neu conflict thi user co man hinh resolve conflict roi moi duoc submit.

## 1.1) Mandatory Design Principle

Nguyen tac bat buoc cho feature nay:

1. Neu van de nam o mo hinh du lieu, uu tien sua DB schema truoc.
2. Tuyet doi tranh cach "han che sua DB" roi bo sung logic chong cheo trong route/service de chay tam.
3. Khong giu song song qua lau hai mo hinh cu-va-moi cho cung mot nghiep vu clone/request/merge.
4. Moi logic tam thoi de bridge migration phai co thoi han xoa ro rang trong ke hoach phase.

## 2) Current Baseline (code da co)

He thong hien tai da co:

1. Clone install theo `DeckInstall` + `DeckCloneDeckMap`:
   - [models/deck_install.py](/workspaces/Flama/models/deck_install.py)
   - [models/deck_clone_deck_map.py](/workspaces/Flama/models/deck_clone_deck_map.py)
2. Overlay thay doi clone:
   - [models/deck_clone_field_def_override.py](/workspaces/Flama/models/deck_clone_field_def_override.py)
   - [models/deck_clone_added_field_def.py](/workspaces/Flama/models/deck_clone_added_field_def.py)
   - [models/deck_clone_field_order_override.py](/workspaces/Flama/models/deck_clone_field_order_override.py)
   - [models/deck_clone_note_field_override.py](/workspaces/Flama/models/deck_clone_note_field_override.py)
3. API update overlay:
   - [app/routes/flashcards/share.py](/workspaces/Flama/app/routes/flashcards/share.py#L849)
   - [app/controllers/flashcards_share/clone_install.py](/workspaces/Flama/app/controllers/flashcards_share/clone_install.py#L489)

Ket luan: co nen tang overlay de tao luong request duyet, khong can thay sang full Git model.

## 3) Scope v1 (de lam nhanh va on dinh)

### In-scope

1. Theo doi thay doi local clone:
   - note field da sua
   - field definition da sua/them/tat
   - thay doi thu tu field
   - deck moi tao trong clone scope (chi muc metadata deck)
2. Tao "Change Request" gui owner duyet.
3. Bat buoc "Sync truoc submit".
4. Co co che "Resolve Conflict" truoc submit.
5. Owner co the approve/reject, approve se merge vao source.

### Out-of-scope (v2)

1. Multi-branch phuc tap.
2. Event sourcing day du.
3. Collaborative review threads giong GitHub.

## 4) Minimal DB Changes

### 4.1 New table: `deck_change_requests`

Muc dich: 1 request duyet thay doi tu 1 clone install.

Cot de xuat:

1. `id` (uuid, pk)
2. `deck_install_id` (fk -> `deck_installs.id`, index)
3. `deck_item_id` (fk -> `deck_marketplace_items.id`, index)
4. `requester_user_id` (fk -> `users.id`, index)
5. `owner_user_id` (fk -> `users.id`, index)
6. `title` (varchar 255)
7. `description` (text, nullable)
8. `status` enum/string: `draft`, `needs_sync`, `has_conflict`, `pending_review`, `approved`, `rejected`, `merged`, `closed`
9. `base_snapshot_at` (datetime) - moc clone dang dung khi tao request
10. `synced_snapshot_at` (datetime, nullable) - moc sau lan sync gan nhat
11. `submitted_at`, `reviewed_at`, `merged_at` (datetime, nullable)
12. `review_comment` (text, nullable)
13. `created_at`, `updated_at`

Index:

1. `(owner_user_id, status, updated_at desc)`
2. `(requester_user_id, status, updated_at desc)`

### 4.2 New table: `deck_change_request_items`

Muc dich: luu danh sach thay doi de user/owner xem diff ro rang.

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
   - `deck_add`
   - `deck_rename`
4. `source_ref_id` (nullable) - vd source note id/source field id/source deck id
5. `local_ref_id` (nullable) - local deck id neu can
6. `path_label` (varchar 255, nullable) - hien thi de doc nhanh
7. `before_value` (json, nullable)
8. `after_value` (json, nullable)
9. `is_conflict` (bool, default false, index)
10. `created_at`, `updated_at`

Index:

1. `(change_request_id, change_type)`
2. `(change_request_id, is_conflict)`

### 4.3 New table: `deck_change_request_conflicts`

Muc dich: luu conflict va cach user resolve.

Cot de xuat:

1. `id` (uuid, pk)
2. `change_request_id` (fk -> `deck_change_requests.id`, index)
3. `item_id` (fk -> `deck_change_request_items.id`, index)
4. `conflict_type` enum/string: `note_field`, `field_def`, `deck_meta`
5. `source_ref_id` (varchar 64)
6. `upstream_value` (json)
7. `local_value` (json)
8. `base_value` (json, nullable)
9. `resolution_mode` enum/string nullable: `keep_mine`, `keep_upstream`, `manual`
10. `resolved_value` (json, nullable)
11. `resolved_by` (fk -> `users.id`, nullable)
12. `resolved_at` (datetime, nullable)
13. `created_at`, `updated_at`

Index:

1. `(change_request_id, resolved_at)`
2. `(change_request_id, conflict_type)`

### 4.4 Small extension cho bang cu

`deck_installs` them:

1. `last_synced_at` (datetime, nullable)
2. `last_sync_status` (varchar 32, nullable)

Ly do: giup UI biet clone dang stale hay da sync.

## 5) API/Workflow v1

### Step A - Build draft thay doi

1. API: `POST /api/shared/decks/<deck_item_id>/change-requests/draft`
2. He thong scan overlay rows cua install va build list `deck_change_request_items`.
3. Neu chua co thay doi thi tra `400` voi message ro.

### Step B - Sync truoc submit (bat buoc)

1. API: `POST /api/shared/decks/<deck_item_id>/change-requests/<id>/sync`
2. He thong:
   - doc source data hien tai trong clone scope
   - so sanh voi item draft
   - neu thay doi upstream cham trung field/path da sua -> tao conflict
3. Ket qua:
   - khong conflict: request status `needs_sync` -> `draft` (da sync)
   - co conflict: status `has_conflict`

### Step C - Resolve conflict

1. API: `POST /api/shared/decks/<deck_item_id>/change-requests/<id>/conflicts/<conflict_id>/resolve`
2. Payload:
   - `resolution_mode`: `keep_mine` | `keep_upstream` | `manual`
   - `resolved_value` (chi bat buoc khi `manual`)
3. Khi tat ca conflict da resolve -> request tro ve `draft`.

### Step D - Submit request

1. API: `POST /api/shared/decks/<deck_item_id>/change-requests/<id>/submit`
2. Rule:
   - bat buoc vua sync xong (hoac `last_synced_at` con hop le theo timeout ngan, vd 5 phut)
   - khong con conflict chua resolve
3. Chuyen status sang `pending_review`.

### Step E - Owner review

1. API owner:
   - `POST .../<id>/approve`
   - `POST .../<id>/reject`
2. Approve:
   - apply item da duyet vao source deck/note_type/note
   - cap nhat status `merged`
3. Reject:
   - status `rejected`
   - giu ly do vao `review_comment`

## 6) Conflict Rules (don gian, de van hanh)

Xac dinh conflict neu cung "entity + property" da doi o upstream sau moc clone.

V1 rules:

1. Note field conflict:
   - cung `source_note_id + field_name`
   - local doi va upstream cung doi
2. Field def conflict:
   - cung `source_field_def_id`
   - local doi ten/type/required/position, upstream cung doi
3. Added field name collision:
   - local add field `X`, upstream da co field `X`
4. Deck rename conflict:
   - local doi ten deck, upstream da doi ten cung deck do

Resolve mode:

1. `keep_mine`: dung local value lam ket qua merge.
2. `keep_upstream`: bo local change item.
3. `manual`: user nhap value moi (co validate type).

## 7) UI Requirements

### 7.1 Clone user side

1. Man hinh "My Changes":
   - nhom theo loai thay doi
   - hien before/after
   - badge `Synced` / `Needs Sync` / `Conflict`
2. Nut `Sync now` bat buoc truoc `Submit request`.
3. Neu co conflict:
   - list conflict cards
   - moi card co 3 lua chon resolve

### 7.2 Owner side

1. Man hinh "Incoming Requests":
   - filter `pending_review`
2. Xem diff tung item, highlight conflict da resolve theo cach nao.
3. Nut `Approve and Merge` / `Reject`.

## 8) Implementation Phases (small and safe)

### Phase 1 - Data + Draft Diff

1. Tao 3 bang moi: `deck_change_requests`, `deck_change_request_items`, `deck_change_request_conflicts`.
2. Tao API draft build tu overlay hien co.
3. Hien thi list thay doi cho user clone.

Files chinh:

1. [app/controllers/flashcards_share/clone_install.py](/workspaces/Flama/app/controllers/flashcards_share/clone_install.py)
2. [app/routes/flashcards/share.py](/workspaces/Flama/app/routes/flashcards/share.py)
3. tao model moi trong `models/`

### Phase 2 - Sync + Conflict Resolve

1. Them API sync.
2. Sinh conflict records.
3. Them API resolve conflict.

### Phase 3 - Submit + Review + Merge

1. Submit request API + state machine.
2. Owner approve/reject API.
3. Merge apply vao source + audit log.

## 9) Testing Checklist

1. Clone user co thay doi -> tao draft co item.
2. Upstream doi truoc submit -> sync tao conflict.
3. Resolve het conflict -> submit thanh cong.
4. Owner approve -> source data duoc cap nhat dung item.
5. Owner reject -> source khong doi.
6. Submit khi chua sync -> fail dung message.
7. Submit khi con conflict -> fail dung message.

## 10) Notes

1. V1 chu y de don gian: uu tien note/field/deck metadata, khong lam branch graph phuc tap.
2. Khi v1 on dinh moi mo rong sang v2 (revision graph/rebase nang cao neu can).
