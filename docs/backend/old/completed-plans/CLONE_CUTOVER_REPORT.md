# Clone Cutover Report (Logical Overlay Only)

> Follow-up implementation plan cho clone edit -> request -> review/merge:
> `docs/plans/completed/DECK_CHANGE_REQUEST_SIMPLE_PLAN.md`
>
> **Implementation snapshot: 2026-08-21.** Báo cáo này mô tả runtime hiện tại.
> Release atomic hiện cover FieldDef/field order, Note field values và membership
> visibility. Note tags, template/card layout, tên/schema NoteType và deck move của Note
> đã có historical release membership chưa atomic-versioned. Content API, Browse, MCP và
> Flama Connect fail-closed các mutation này để không bypass immutable release gate.
> Note mới chưa publish vẫn editable/movable; field/value changes vẫn versioned bình
> thường. Listing description/taxonomy/pricing không phải clone schema/content và vẫn
> được chỉnh theo marketplace policy riêng.

Tài liệu không giữ các tham chiếu controller cũ hoặc full-copy clone như runtime hợp lệ.

## 1) Current Runtime Inventory

### a) Shared deck install

Entry points:

1. Route: `app/routes/flashcards/share.py::POST /api/shared/decks/<deck_item_id>/install`
2. Service: `app/services/flashcards_share_service.py::install_shared_deck_item_for_user`

Status:

1. Dang chay tren model moi.

Current behavior:

1. Install bắt buộc `source_deck_id`.
2. Mỗi install mới luôn tạo `DeckInstall.clone_mode='logical_overlay'`.
3. Install lưu lineage và release pointers: `source_deck_id`, `source_note_type_id`,
   `source_owner_user_id`, `applied_release_id`, `seen_release_id`, `version_mode`.
   `base_snapshot_at` chỉ còn là compatibility fallback cho install legacy.
4. Install mới bảo đảm listing có initial release và pin thẳng vào current release; không
   bắt đầu ở null pointer rồi đọc source live.
5. Hệ thống clone local deck subtree shell + tạo `DeckCloneDeckMap`, nhưng không copy
   source `Note`/`Card` cho learner.
6. Nếu shared deck bind vào source note type, install flow vẫn tạo `NoteTypeInstall` +
   installed note type copy cho installer.

### b) Read / render / browse / study

Entry points:

1. `app/routes/vocabulary.py`
2. `app/services/flashcards_share_service.py`
3. `app/repositories/flashcards_share_repository.py`

Status:

1. Install đã version hóa dùng source scope tại `applied_release_id` + overlay.
2. Install legacy chưa bootstrap vẫn dùng timestamp snapshot compatibility có kiểm soát.

Current behavior:

1. Browse list/detail resolve clone scope từ `DeckInstall` + `DeckCloneDeckMap`.
2. Study/browse đọc source Note/Card identity, nhưng field values, schema và membership
   được reconstruct tại release install đang apply; owner working edit không lộ sang clone.
3. Render layer apply schema overlay + note field overrides trên published base.
4. Browse `q`, total/count và word sort dùng release-pinned values cộng overlay trước
   pagination; không search/sort source live rồi chỉ sửa payload trả về.
5. Clone chỉ thấy upstream mới sau khi xem diff, prepare/rebase và apply release.

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
4. Note field identity dùng `source_field_def_id`; `field_name` chỉ là compatibility label,
   nên upstream rename không làm mất overlay identity.
5. Clone browse edit vẫn reject:
   - tag edit cho cloned cards
   - move cloned cards sang deck local khac
6. Owner mutation Note tags, template/card layout, NoteType name/schema hoặc deck move
   của Note có historical release membership bị `409` fail-closed cho đến khi các loại
   này có atomic release representation. Guard được áp dụng trên Content API, Browse,
   MCP và Flama Connect.
7. Note mới chưa có release membership vẫn có thể sửa/chuyển deck; field/value mutation
   của released Note vẫn được ghi dirty journal và publish như sparse atoms bình thường.
8. Note/Card hard-delete dùng historical membership guard, không chỉ `Note.deck_id` hiện
   tại, nên một Note từng publish không mất protection sau khi rời source subtree.

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
   - `flask deck-release-bootstrap` de dry-run initial release cho listing public legacy.
   - `flask deck-release-bootstrap --apply` de commit tung listing, tranh transaction dai.
3. Runtime compatibility:
   - listing public moi tao initial release trong cung transaction;
   - listing public legacy duoc bootstrap truoc install moi hoac khi owner update listing.
   - initial baseline không có legacy install null pointer lưu Note values một lần trong
     checkpoints và chỉ emit schema atoms;
   - nếu còn `DeckInstall.applied_release_id IS NULL`, initial baseline vẫn emit Note
     atomic adds cạnh checkpoints để null -> initial diff/rebase giữ đúng semantics.
4. Strictness control:
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
6. `test_shared_deck_install_creates_pointer_clone_without_note_copy`
   - install mới pin current release và không tạo Note/Card copy
7. `test_clone_browse_search_uses_pinned_release_values` và
   `test_clone_browse_word_sort_uses_pinned_release_values_before_pagination`
   - `q`, count và sort dùng release projection + overlay, không leak owner live edit
8. `test_initial_release_preserves_atomic_baseline_for_legacy_install`
   - legacy null-pointer install giữ null -> initial atomic diff; install thường dùng
     checkpoint-only Note baseline
9. Scale proofs trong `test_deck_install_rebase_flow.py`
   - hơn 1.000 overlays không tạo giant `IN`; 1.005 conflicts chỉ trả page đầu 100

Focused release/schema/rebase/change-request regression snapshot: **36 tests pass** trên
SQLite. Alembic SQLite downgrade/upgrade qua merge head pass với một script head
`20260820_000019`. MySQL 8 live chưa chạy.

## 5) Follow-up Sau Cutover (Hoàn thành trong atomic scope hiện tại)

Các follow-up chính đã được giải quyết qua Change Request + immutable Release subsystem:

1. [x] Draft diff request: Tạo và xem trước diff thay đổi local so với snapshot
2. [x] Sync/conflict state machine: Tự động phát hiện xung đột và hỗ trợ resolve (`keep_mine`, `keep_upstream`, `manual`)
3. [x] Owner review inbox: Hộp thư tiếp nhận change request cho deck owner
4. [x] Approve/reject/merge: Quy trình duyệt/hợp nhất vào owner working tree an toàn
5. [x] Immutable release gate: merge khong phat tan cho clone cho den khi owner publish
6. [x] Installed update: unread notification, Git-style diff, rebase conflict va apply tuy chon
7. [x] Study-history invariant: update giu nguyen source `Note.id`/`Card.id`/`CardProgress`

Chi tiết xem tại: [`DECK_CHANGE_REQUEST_SIMPLE_PLAN.md`](DECK_CHANGE_REQUEST_SIMPLE_PLAN.md)

## 6) Release/update API và scale contract

1. Owner releases: `/api/marketplace/decks/<item_id>/releases...`; release preview,
   history và changes mặc định 100, tối đa 200 items/page.
2. Install updates: `/api/marketplace/installations/<install_id>/updates...`; diff mặc
   định 100, tối đa 200 và `q` tối đa 200 ký tự.
3. Rebase conflicts:
   `GET /api/marketplace/rebases/<rebase_id>/conflicts?after_id=&limit=`; mặc định 100,
   tối đa 200. Prepare/error envelope chỉ nhúng page đầu; resolve/apply success không gửi
   lại conflict array.
4. Change-request local/detail item pages mặc định 100, tối đa 250; owner inbox mặc định
   30, tối đa 100; `q` tối đa 200. Cursor bind snapshot fingerprint/revision + filters.
5. Subsequent release ưu tiên dirty-row sparse diff + batch source/base reads; marker gap
   fallback full. Jump nhiều release collapse effective diff bằng SQL window và loại net
   no-op. Overlay overlap dùng correlated `EXISTS`, không giant `IN`.
6. Initial publish luôn O(deck) để tạo checkpoints. Không có legacy null install thì Note
   baseline chỉ nằm ở checkpoints; có null install thì giữ thêm Note atomic adds để bảo
   toàn compatibility semantics.

## 7) Residual Risks

1. Legacy installs có lịch sử mờ hồ hoặc deck tree/note pairing không khớp sẽ fail loudly để tránh silent corruption.
2. Listing/install legacy chua co release van can chay `deck-release-bootstrap --apply` truoc
   rollout production de loai bo cua so doc source live.
3. Note tags, template/card layout, NoteType name/schema và release-aware deck move chưa
   atomic-versioned; released lineage fail-closed. Đây là product limitation có chủ đích,
   không phải compatibility fallback.
4. Local-change preview vẫn materialize tập local overlays để tạo fingerprint; không scan
   full source deck nhưng cần benchmark nếu một install có hàng chục nghìn overrides.
5. Publish lớn vẫn synchronous và chưa có production worker/outbox.
6. MySQL 8 migration round-trip, `EXPLAIN` và benchmark/deadlock/concurrency 10k-50k records
   chưa được chứng nhận trên môi trường live; đây là deployment gate cho catalog lớn.
