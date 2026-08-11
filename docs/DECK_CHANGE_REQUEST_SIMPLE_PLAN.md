# Shared Deck Collaboration, Release, and Update Plan

## 1. Mục đích tài liệu

Tài liệu này là kế hoạch triển khai chính thức cho ba luồng liên quan nhưng bất đối xứng:

1. Người cài shared deck sửa nội dung trong clone local bằng logical overlay.
2. Người cài gửi một phần hoặc toàn bộ thay đổi local về owner dưới dạng contribution/change request.
3. Owner chỉ phân phối thay đổi cho các install khi chủ động publish một release bất biến; từng người cài tự xem diff và quyết định cập nhật.

Tài liệu phân biệt rõ:

- **Current baseline**: code đã tồn tại trong repo.
- **Target behavior**: hành vi cần đạt.
- **Implementation plan**: phần chưa implement và thứ tự triển khai.

Không được đọc tài liệu này như một kế hoạch xây lại clone từ đầu. Logical overlay và change-request MVP hiện tại là baseline phải được giữ và harden.

## 2. Current baseline trong repo

### 2.1 Runtime và kiến trúc

Runtime thật:

1. `wsgi.py` gọi `create_app()`.
2. Local dev thường chạy `flask --app wsgi.py run --host=0.0.0.0 --port=4789`.
3. Docker/production chạy Gunicorn với `wsgi:app`.
4. Startup có mutation: `db.create_all()`, compatibility schema, seed mặc định và clone cutover.

Implementation mới phải theo boundary hiện tại:

1. HTTP parsing/response: `app/routes/flashcards/`.
2. Transaction và business orchestration: `app/services/`.
3. Query/bulk persistence: `app/repositories/`.
4. Schema: model phẳng trong `models/` và Alembic migration trong `migrations/versions/`.
5. UI mới mặc định nằm trong React `frontend/src/`, không mở rộng Jinja change-request UI trừ compatibility redirect/fallback.

### 2.2 Logical overlay install đã ship

Files chính:

1. `app/routes/flashcards/share.py`
2. `app/services/flashcards_share_service.py`
3. `app/repositories/flashcards_share_repository.py`
4. `models/deck_install.py`
5. `models/deck_clone_deck_map.py`
6. Các model `models/deck_clone_*.py`

Hành vi hiện tại:

1. Install mới dùng `DeckInstall.clone_mode='logical_overlay'`.
2. Install lưu source deck, source note type, source owner và `base_snapshot_at`.
3. Hệ thống copy deck tree shell và tạo `DeckCloneDeckMap`.
4. Hệ thống không copy source `Note`/`Card` theo từng learner.
5. Browse/study dùng source Note/Card rồi apply clone schema/note overlay.
6. Local edit được lưu thưa trong:
   - `DeckCloneFieldDefOverride`
   - `DeckCloneAddedFieldDef`
   - `DeckCloneFieldOrderOverride`
   - `DeckCloneNoteFieldOverride`
   - `DeckCloneAddedNote`

Invariant: không quay lại `legacy_copy` và không tạo full Note/Card copy cho từng install.

### 2.3 Change request MVP đã ship

Files chính:

1. `app/routes/flashcards/change_requests.py`
2. `app/services/deck_change_request_service.py`
3. `app/repositories/deck_change_request_repository.py`
4. `models/deck_change_request.py`
5. `models/deck_change_request_item.py`
6. `models/deck_change_request_conflict.py`
7. `migrations/versions/20260330_000006_add_deck_change_request_tables.py`
8. `tests/test_deck_change_request_flow.py`

Flow hiện có:

```text
needs_sync -> draft -> has_conflict -> draft -> pending_review -> merged/rejected
```

API hiện có:

1. Preview local changes.
2. Build/refresh draft.
3. Sync với upstream.
4. Resolve conflict bằng `keep_mine`, `keep_upstream`, `manual`.
5. Submit request.
6. Owner inbox/detail.
7. Approve/merge và reject.

Reject hiện đã đúng một phần yêu cầu mới:

1. Không sửa source.
2. Không xóa overlay của contributor.
3. Lưu reason vào request.

Merge hiện chưa đúng semantics release mới:

1. Merge sửa source rows trực tiếp.
2. Merge cleanup overlay tương ứng.
3. Merge nâng `base_snapshot_at` của install.
4. Vì clone đọc source live, merge có thể làm thay đổi hiển thị của clone khác mà chưa publish.

### 2.4 Seam giữ lịch sử học

Clone học trực tiếp source `Card.id`. `CardProgress` unique theo `(user_id, card_id)`.

Do đó invariant bắt buộc là:

1. Update field không recreate `Note` hoặc `Card`.
2. Note/Card bị loại khỏi release phải retire/tombstone, không hard-delete.
3. New Note/Card có ID mới và progress mới.
4. Local-added note được merge cần map local/source identity có kiểm soát và remap progress tương tự legacy cutover helper nếu cần.

## 3. Gaps và rủi ro cần xử lý

### P0: `base_snapshot_at` không phải content version

`base_snapshot_at` chỉ lọc row theo `created_at`:

1. Owner sửa field hiện hữu: clone có thể thấy ngay.
2. Owner thêm Note/Card/FieldDef sau snapshot: clone cũ không thấy.
3. Owner hard-delete source row: clone mất row ngay và có nguy cơ mất progress do cascade.

Target phải thay timestamp snapshot bằng một published release thật.

### P0: chưa có immutable release/publish gate

`DeckMarketplaceItem.version` hiện chỉ là metadata mutable. Repo chưa có:

1. Release history bất biến.
2. Sparse release delta.
3. Current published release pointer.
4. Applied release pointer trên từng install.
5. Available-update/seen state.
6. Preview/rebase/apply upstream update.

### P0: conflict base của contribution có thể sai

Overlay hiện chủ yếu lưu after-value. Draft lấy `before_value` từ source tại thời điểm build draft, không phải published base lúc learner bắt đầu sửa.

Nếu owner đổi cùng field sau khi learner sửa nhưng trước khi learner build draft, conflict có thể bị bỏ sót. Cần `base_release_id` và stable field identity.

### P0: hard delete có thể xóa lịch sử học

Source Note có thể bị hard-delete, kéo theo Card và `CardProgress` qua FK cascade. Trước khi release hỗ trợ remove:

1. Shared Note/Card/FieldDef/Template cần tombstone/retired semantics.
2. Release membership quyết định visibility.
3. Cleanup vật lý chỉ được thực hiện theo retention policy sau khi chứng minh không còn install/progress phụ thuộc.

### P1: scale diff chưa phù hợp deck lớn

Hiện tại:

1. Draft có N+1 lookup theo FieldDef/Note.
2. Sync lookup source theo từng request item.
3. Request detail eager-load và serialize toàn bộ items/conflicts.
4. Owner inbox dùng `.all()` không pagination.
5. Jinja/vanilla JS render toàn bộ diff array vào DOM.
6. Fingerprint build bằng cách load toàn bộ overlay vào Python/JSON.

### P1: identity note field đang dựa vào tên

`DeckCloneNoteFieldOverride` dùng `field_name`. Upstream rename có thể làm mất mapping hoặc tạo conflict sai.

Target dùng `source_field_def_id` làm identity; tên field chỉ là label/compatibility.

### P1: NoteType có thể nằm ngoài scope deck

Field rename/remove hiện có thể rewrite mọi Note dùng cùng NoteType, kể cả Note ngoài source deck.

V1 phải chọn một trong hai policy:

1. Chỉ cho schema contribution/release khi NoteType độc quyền cho shared deck; hoặc
2. Version NoteType như dependency riêng và pin `note_type_release_id` trong deck release.

Khuyến nghị v1: enforce exclusive provenance cho schema-changing operation; NoteType release độc lập là phase sau.

## 4. Target architecture

```text
Clone overlay
    | submit
    v
ChangeRequest --merge--> Owner working tree --publish--> Immutable DeckRelease
    | reject                                      |
    |                                             | available update
    v                                             v
Overlay remains                        DeckInstall.applied_release
                                                   |
                                                   v
                                      Rebase local overlay + advance pointer
```

### 4.1 Tác động của từng action

| Action | Owner working tree | Published release | Clone overlay | Applied release | CardProgress |
|---|---|---|---|---|---|
| Clone sửa field | Không đổi | Không đổi | Ghi delta | Không đổi | Giữ nguyên |
| Owner reject contribution | Không đổi | Không đổi | Vẫn giữ | Không đổi | Giữ nguyên |
| Owner merge contribution | Có đổi | Chưa đổi | Vẫn giữ | Không đổi | Giữ nguyên |
| Owner publish | Không đổi thêm | Tạo release mới | Không đổi | Chưa đổi | Giữ nguyên |
| Clone apply update | Không đổi | Không đổi | Rebase/prune | Nâng pointer | Giữ nguyên |

### 4.2 Ba lớp state phải đặt tên rõ

UI/API không được trộn ba snapshot sau:

1. `editor_draft`: form chưa save.
2. `local_overlay`: thay đổi clone đã persist.
3. `published_base`: release install đang áp dụng.

Owner có thêm lớp thứ tư:

4. `owner_working`: source đang sửa nhưng chưa publish.

## 5. Data model đề xuất

### 5.1 `deck_releases`

Mục đích: immutable release metadata.

Columns chính:

1. `id` UUID PK.
2. `deck_item_id` FK/index.
3. `sequence_no BIGINT` làm thứ tự authoritative.
4. `version_label VARCHAR(50)` cho SemVer hiển thị.
5. `parent_release_id` nullable FK.
6. `status`: `building`, `published`, `failed`.
7. `manifest_hash`.
8. `change_count` và aggregate counts theo loại.
9. `changelog`.
10. `created_by_user_id`, `created_at`, `published_at`.
11. `idempotency_key`.

Constraints/indexes:

1. Unique `(deck_item_id, sequence_no)`.
2. Unique `(deck_item_id, version_label)`.
3. Unique `(deck_item_id, idempotency_key)` khi idempotency key có giá trị.
4. Index `(deck_item_id, status, published_at, id)`.

### 5.2 `deck_release_changes`

Mục đích: append sparse change theo property thực sự thay đổi.

Columns chính:

1. `id BIGINT` PK để giảm index footprint trên MySQL.
2. `release_id`, `release_sequence_no`.
3. `entity_kind`: `note`, `note_field`, `field_def`, `field_order`, `template`, `deck_node`, `card`.
4. `entity_id`: stable source ID.
5. `field_def_id` nullable.
6. `property_key`.
7. `operation`: `add`, `set`, `remove`, `move`, `retire`.
8. `before_value`, `after_value` JSON: chỉ một property, không phải toàn card.
9. `before_hash`, `after_hash`.
10. `source_deck_id`, `sort_key`.
11. `source_change_request_item_id` nullable để trace contribution.

Indexes:

1. Unique `(release_id, change_key)`.
2. `(release_id, entity_kind, source_deck_id, sort_key, id)` cho diff cursor.
3. `(entity_kind, entity_id, property_key, release_sequence_no, id)` cho point-in-time reconstruction.

Không index JSON trực tiếp. Các filter/sort keys phải có column riêng.

### 5.3 Checkpoint và membership

`deck_release_note_checkpoints`:

1. Một JSON snapshot/Note tại checkpoint release.
2. Tận dụng `Note.field_values` hiện tại.
3. Tạo initial checkpoint và checkpoint định kỳ, không snapshot mỗi release.
4. Ngưỡng ban đầu để benchmark: sau khoảng 20 release hoặc cumulative delta vượt 20-25% deck.

`deck_release_entity_memberships`:

1. `deck_item_id`, `entity_kind`, `entity_id`.
2. `introduced_sequence`, `removed_sequence`.
3. `source_deck_id` và stable mapping metadata.
4. Visibility không còn phụ thuộc `created_at <= base_snapshot_at`.

Read/query layer phải release-aware cho cả browse list/search/sort/count và study, không chỉ render card detail.

### 5.4 Mở rộng bảng hiện tại

`DeckMarketplaceItem`:

1. `current_release_id`.
2. `working_revision BIGINT`.
3. Giữ `version/changelog` làm cache compatibility cho current release.

`DeckInstall`:

1. `applied_release_id`.
2. `seen_release_id`.
3. `overlay_revision BIGINT`.
4. `version_mode` trong rollout.
5. Không dùng `last_sync_status` làm notification/update state.

`DeckCloneNoteFieldOverride`:

1. Thêm `source_field_def_id`.
2. Thêm `base_release_id` hoặc `base_value_hash`.
3. Giữ `field_name` tạm thời cho compatibility/display.
4. Nếu local value bằng published base thì xóa override thay vì giữ no-op row.

`DeckChangeRequest`:

1. Thêm `base_release_id`.
2. Thêm `revision BIGINT`.
3. Thêm `active_slot` nullable để enforce tối đa một active request/install.
4. Cache item/conflict counts để summary không load toàn bộ relationship.

### 5.5 Working dirty set

`deck_working_dirty_entities`:

1. Upsert theo `(deck_item_id, entity_kind, entity_id, property_key)`.
2. Lưu base/current hash, operation và `updated_at`.
3. Owner edit O(1) và publish chỉ xử lý dirty set.
4. Nếu working value quay lại published value thì xóa dirty row.
5. Cần fallback reconciliation/hash vì hiện có nhiều đường ghi Note/schema: Browse, import, Flama Connect, API note type.

### 5.6 Update attempt và conflict

`deck_install_rebases`:

1. `install_id`, `from_release_id`, `to_release_id`.
2. `status`: `prepared`, `has_conflict`, `ready`, `applied`, `cancelled`, `stale`, `failed`.
3. `expected_overlay_revision`, `idempotency_key`.
4. Summary counts và timestamps.

`deck_install_rebase_conflicts`:

1. Chỉ materialize field/property bị conflict.
2. Lưu base/upstream/local và resolution.
3. Không copy toàn bộ upstream diff vào từng install.

### 5.7 Data growth invariant

```text
O(initial published notes/fields)
+ O(properties thật sự thay đổi qua releases)
+ O(local clone overrides)
+ O(active conflicts/update decisions)
```

Không có thành phần `deck size × số releases × số installs`.

## 6. Contribution workflow: clone -> owner

### 6.1 Save local field

Clone field API nên dùng operation rõ nghĩa:

```json
{
  "field_ops": [
    {"field_def_id": "...", "op": "set", "value": "..."},
    {"field_def_id": "...", "op": "clear_override"}
  ],
  "expected_overlay_revision": 12
}
```

Rules:

1. `clear_override` khác empty string.
2. Mỗi mutation atomic increment `DeckInstall.overlay_revision`.
3. Chỉ lưu changed field, không lưu toàn card.
4. Pending request không còn khóa toàn bộ clone edit sau khi request snapshot đã độc lập.

### 6.2 Preview và staging

1. “My Changes” chỉ đọc persisted overlay.
2. Unsaved editor draft phải được cảnh báo và không tự đưa vào contribution.
3. Default stage toàn bộ eligible changes.
4. Với tập lớn dùng `{mode: allMatching, excludedIds}` hoặc stage state server-side.
5. Preview summary và item feed dùng cursor pagination.

### 6.3 Three-way sync

Với mỗi changed property:

1. Base = published value tại `base_release_id`.
2. Upstream = owner working value hiện tại.
3. Mine = clone overlay/request value.

Conflict khi upstream và mine đều đổi so với base và không bằng nhau.

Resolution modes giữ tương thích:

1. `keep_mine`
2. `keep_upstream`
3. `manual`

### 6.4 Submit

1. Request phải vừa sync với expected revision.
2. Không còn unresolved conflict.
3. Request items được freeze thành immutable snapshot.
4. Overlay có thể tiếp tục thay đổi sau submit nhưng không thay đổi submitted request.

### 6.5 Owner merge/reject

Owner review v1 là whole-request:

1. `merge`:
   - validate current owner/source scope;
   - recheck expected request/source revision;
   - apply request snapshot vào owner working tree;
   - mark working dirty;
   - không publish;
   - không cleanup contributor overlay;
   - không advance bất kỳ install release pointer nào.
2. `reject`:
   - chỉ đổi status và lưu reason;
   - source không đổi;
   - release không đổi;
   - contributor overlay giữ nguyên.

Partial item merge là phase sau.

## 7. Owner publish workflow

### 7.1 Owner edit

1. Sửa working source bình thường.
2. Ghi/update dirty keys.
3. UI chỉ hiển thị “N thay đổi chưa phát hành”.
4. Không tạo notification và không đổi `current_release_id`.

### 7.2 Release preview

1. So sánh working dirty set với current release.
2. Trả summary trước; item diff dùng cursor.
3. Owner nhập `version_label` và changelog.
4. Client gửi `expected_current_release_id` và `expected_working_revision`.

### 7.3 Publish

1. Lock marketplace/release head bằng `SELECT ... FOR UPDATE`.
2. Enforce expected head và working revision.
3. Tạo release `building`.
4. Bulk insert sparse changes/checkpoint/membership theo batch.
5. Validate manifest hash/counts.
6. Atomic chuyển release sang `published` và swap `DeckMarketplaceItem.current_release_id`.
7. Không update/fan-out mọi `DeckInstall` trong publish transaction.

Update available được derive bằng:

```text
DeckInstall.applied_release_id != DeckMarketplaceItem.current_release_id
```

`seen_release_id` chỉ quản lý unread badge. Mark seen không đồng nghĩa apply hoặc skip update.

## 8. Clone update/rebase workflow

### 8.1 Compare

1. Base = install applied release.
2. Target = selected/latest published release.
3. Diff feed đọc shared release changes, không materialize lại theo install.
4. Khi jump qua nhiều release, collapse các changes cùng natural key thành base -> target.

### 8.2 Conflict rules

Với mỗi upstream atomic change:

1. Không có local override: nhận upstream bằng cách advance base.
2. Local bằng upstream: xóa override dư thừa.
3. Upstream bằng base: giữ local override.
4. Local và upstream cùng đổi khác nhau: tạo conflict.

Resolution:

1. `keep_mine`: giữ overlay; base metadata được rebase lên target.
2. `keep_upstream`: xóa override tương ứng.
3. `manual`: ghi resolved value thành overlay mới.

### 8.3 Apply

1. Lock install.
2. Compare expected `applied_release_id` và `overlay_revision`.
3. Recompute/validate unresolved conflicts.
4. Apply resolution theo stable change key.
5. Advance `applied_release_id`.
6. Prune no-op overlays.
7. Không recreate Note/Card.
8. Không update/delete `CardProgress` hoặc `ReviewEvent`.

Removed Note/Card chỉ bị ẩn theo membership. Nếu được đưa lại vào release sau, identity/progress cũ vẫn có thể được phục hồi.

## 9. API plan

### 9.1 Owner release APIs

1. `GET /api/shared/decks/<item_id>/releases/preview`
2. `POST /api/shared/decks/<item_id>/releases`
3. `GET /api/shared/decks/<item_id>/releases`
4. `GET /api/shared/decks/<item_id>/releases/<release_id>`
5. `GET /api/shared/decks/<item_id>/releases/<release_id>/changes?cursor=&limit=&type=&deck_id=&q=`

### 9.2 Installed update APIs

1. `GET /api/installed-decks/<install_id>/updates`
2. `GET /api/installed-decks/<install_id>/updates/<release_id>/diff?cursor=&limit=&type=&q=`
3. `POST /api/installed-decks/<install_id>/updates/<release_id>/prepare`
4. `POST /api/install-rebases/<rebase_id>/conflicts/<conflict_id>/resolve`
5. `POST /api/install-rebases/<rebase_id>/apply`
6. `POST /api/installed-decks/<install_id>/updates/<release_id>/mark-seen`

### 9.3 Contribution API hardening

Giữ endpoint/state machine hiện có, nhưng thay contract detail:

1. `GET /api/change-requests/<id>` chỉ trả summary/permissions/counts.
2. `GET /api/change-requests/<id>/items?cursor=&limit=&change_type=&conflict_only=&deck_id=&q=`.
3. Local preview cũng dùng cursor.
4. Draft/submit/sync/approve/reject nhận `expected_revision`.
5. Mutation quan trọng nhận `Idempotency-Key`.

Diff response shape:

```json
{
  "snapshot_revision": "...",
  "summary": {},
  "items": [],
  "next_cursor": null
}
```

Summary item chỉ chứa preview/truncated size. Full base/before/after hoặc structured hunks được fetch khi expand.

## 10. React UX plan

### 10.1 Feature boundary

Tạo feature riêng:

```text
frontend/src/features/deck-collaboration/
  api.ts
  queryKeys.ts
  types.ts
  pages/
    DeckActivityPage.tsx
    MyDeckChangesPage.tsx
    ContributionReviewPage.tsx
    ReleaseBuilderPage.tsx
    InstalledDeckUpdatePage.tsx
  components/
    DiffWorkspace.tsx
    DiffSummaryBar.tsx
    DiffNavigator.tsx
    VirtualDiffList.tsx
    DiffRow.tsx
    DiffHunk.tsx
    ConflictResolver.tsx
    VersionBadge.tsx
    CollaborationStatusBadge.tsx
```

Không nhồi workflow mới vào `BrowsePage.tsx` hoặc `MarketplacePublishPages.tsx`; hai page này đã lớn. Chỉ tích hợp metadata, badge và CTA.

### 10.2 Routes

1. `/deck-activity`: tabs “Cập nhật”, “Đã gửi”, “Cần duyệt”.
2. `/installed-decks/:installId/changes`.
3. `/installed-decks/:installId/updates/:releaseId`.
4. `/creator/contributions/:requestId`.
5. `/creator/decks/:deckItemId/releases/new`.
6. `/creator/decks/:deckItemId/releases`.

### 10.3 Integration seams

1. `BrowsePage.tsx`:
   - `clone_context`;
   - stable `field_def_id`;
   - upstream/effective value;
   - override badge;
   - CTA “Xem thay đổi”.
2. `LibraryPages.tsx`:
   - `deck_install_id`;
   - applied/available version;
   - update/conflict counts;
   - CTA “Xem cập nhật”.
3. Dashboard `DeckTree.tsx`:
   - owned/installed origin;
   - unpublished/local/pending status chips;
   - context action theo ownership.
4. `SharedDeckDetailPage.tsx`:
   - owner CTA release/contribution;
   - learner CTA local changes/update.
5. Sidebar/navigation:
   - collaboration activity entry;
   - unread badge.

### 10.4 Git-like diff workspace

1. Header sticky: deck/request, status, base -> target, changelog, primary action.
2. Summary: Note, field, add, modify, remove, conflict counts.
3. Sidebar group theo deck path -> Note -> Field.
4. Diff unit là `Note + FieldDef`, không phải Card; một Note có thể sinh nhiều Card/template.
5. Unified diff mặc định; desktop có split toggle.
6. Unchanged fields collapsed.
7. Richtext/Markdown diff trên canonical raw text; sanitized render preview là mode riêng.
8. Image/audio chỉ diff asset reference, filename/hash/metadata; không tải binary vào list.
9. Empty string, whitespace và newline phải hiển thị rõ.
10. Mobile dùng hai tab “Danh sách / So sánh”.
11. Add/remove/modify/conflict phải phân biệt bằng icon/label và màu, không chỉ màu.

### 10.5 Large diff constraints

1. Cursor/keyset pagination bắt buộc.
2. Initial page 100 items hoặc nhỏ hơn.
3. Virtualized/windowed list; DOM row mục tiêu dưới 150.
4. Chỉ một row expanded tại một thời điểm.
5. Full field value và Card preview lazy-load.
6. Search/filter server-side và reset cursor.
7. Immutable diff detail có thể cache với `staleTime: Infinity`.
8. API client phải hỗ trợ `AbortSignal` để hủy/ignore stale request.
9. Không dùng Monaco/CodeMirror cho read-only field diff.
10. Notification v1 dùng polling nhẹ; chưa cần WebSocket.

## 11. Implementation boundaries

Files/modules mới dự kiến:

1. `app/routes/flashcards/releases.py`
2. `app/routes/flashcards/install_updates.py`
3. `app/services/deck_release_service.py`
4. `app/services/deck_install_rebase_service.py`
5. `app/services/deck_diff_service.py`
6. `app/repositories/deck_release_repository.py`
7. `app/repositories/deck_install_rebase_repository.py`
8. Models release/rebase/dirty set trong `models/`.
9. React feature `frontend/src/features/deck-collaboration/`.

Không tiếp tục mở rộng `app/services/deck_change_request_service.py` bằng toàn bộ release/update logic. Service hiện tại chỉ nên giữ contribution orchestration và được chuyển dần sang bulk repository/query helpers.

Các read seams bắt buộc phải đổi sang release-aware data:

1. `app/services/flashcards_share_service.py`
2. `app/repositories/flashcards_share_repository.py`
3. `app/services/browse_card_service.py`
4. `app/repositories/vocabulary_repository.py`
5. `app/routes/flashcards/study.py`
6. `app/services/study_artifact_service.py`
7. `app/services/study_session_service.py`

## 12. Phased implementation plan

### Phase 0: ADR, scope và performance spike

Deliverables:

1. Chốt terminology/invariants trong ADR.
2. Chốt stable change key và release/rebase state machines.
3. Chốt v1 scope.
4. React read-only `DiffWorkspace` chạy fixture 50.000 items.
5. Baseline MySQL query plan và storage estimate.

### Phase 1: Additive schema và tombstone foundation

Deliverables:

1. Release/change/checkpoint/membership/dirty/rebase tables.
2. Release pointers/revisions trên marketplace/install/request/overlay.
3. `source_field_def_id` backfill có audit.
4. Tombstone/retired fields cho shared Note/Card/FieldDef/Template.
5. Model registration và Alembic migrations.
6. Không phụ thuộc `db.create_all()` để hoàn tất migration/backfill.

### Phase 2: Initial release và publish gate

Deliverables:

1. Idempotent CLI baseline backfill.
2. Working dirty tracking trên mọi write path.
3. Release preview/publish/list/diff APIs.
4. Atomic publish head swap.
5. Current-release metadata trong marketplace payload.

### Phase 3: Release-aware clone reads

Deliverables:

1. Clone membership theo release.
2. Effective schema/note values từ checkpoint + delta + clone overlay.
3. Browse list/search/sort/detail và study cùng một effective content layer.
4. Shadow-read/hash comparison với legacy path.
5. Content/template version invalidation đúng trong study artifact.

### Phase 4: Installed update/rebase

Deliverables:

1. Available update và seen badge.
2. Base -> target diff.
3. Prepare/conflict resolution/apply.
4. Overlay no-op pruning.
5. Stable CardProgress proof tests.

### Phase 5: Contribution hardening

Deliverables:

1. Base release thật cho draft/sync.
2. Immutable submitted request snapshot.
3. Continue local edit sau submit.
4. Merge vào owner working tree, không publish/cleanup overlay.
5. Cursor-paginated request items/inbox.
6. Bulk query/write thay N+1.
7. Optimistic revision/idempotency.

### Phase 6: React collaboration UI

Deliverables:

1. Deck Activity.
2. My Changes và staging.
3. Contribution review.
4. Release Builder.
5. Installed Deck Update/rebase.
6. Browse/Library/Dashboard/Shared Detail/sidebar integration.
7. Mobile, keyboard, light/dark và a11y.

### Phase 7: Rollout và cleanup

Deliverables:

1. Existing install migration/cutover.
2. MySQL load/deadlock tests.
3. Feature flags theo new install/existing install.
4. Metrics/alerting.
5. Compatibility route redirect khỏi legacy Jinja UI.
6. Update `CLONE_CUTOVER_REPORT.md`, `FLASHCARD_V2_RUNBOOK.md` và architecture docs.
7. Chỉ deprecate `base_snapshot_at` sau khi mọi install đã vào release mode.

## 13. Migration và rollout strategy

### 13.1 Expand first

1. Chỉ add tables, nullable columns và indexes trước.
2. Old app vẫn chạy trên expanded schema.
3. New code phải xử lý null pointers khi backfill chưa xong.
4. Migration phải reconcile table/column/constraint/index riêng; không chỉ `if table exists: return`.

### 13.2 Baseline backfill

1. Tạo initial release cho mỗi published/unlisted deck item.
2. Dùng version string hiện tại làm initial label nếu hợp lệ.
3. Keyset chunk theo Note ID, 500-2.000 Note/transaction.
4. Backfill resumable bằng unique keys, cursor và manifest counts/hash.
5. Validate source subtree, Note/Card identity và progress counts.

### 13.3 Existing installs

Không thể tái dựng historical field value trước khi feature tồn tại.

Cutover policy:

1. Tạo baseline từ effective source state tại thời điểm cutover.
2. Pin existing install vào baseline để chặn owner edit sau cutover bị leak.
3. Giữ legacy membership cutoff để không tự lộ Note/Card mới ngoài snapshot cũ.
4. Pre-existing overlay được đánh dấu `base_unknown`/`needs_rebuild`; không khẳng định conflict base giả.
5. Draft editable cũ chuyển `needs_rebuild`, overlay giữ nguyên.
6. Pending review cũ phải được inventory và complete/rebase có kiểm soát trước cutover.

### 13.4 Dual read/shadow validation

1. Build release-aware output song song với legacy output.
2. Compare scope IDs, schema, effective values và render hash trên sample/install cohort.
3. Bật new installs trước.
4. Bật existing installs theo cohort.
5. Rollback flag không được fallback mù sang live source nếu việc đó làm lộ unpublished change.

## 14. Indexing, concurrency và jobs

### 14.1 Existing change-request indexes

Đề xuất bổ sung sau khi kiểm tra `EXPLAIN ANALYZE`:

1. `(deck_install_id, status, updated_at, id)`.
2. `(owner_user_id, status, deck_item_id, updated_at, id)`.
3. `(change_request_id, sort_order, id)`.
4. Unique `(deck_install_id, active_slot)` với terminal rows dùng `NULL`.
5. Unique `(change_request_id, change_key)` cho draft retry.

Không giữ index low-selectivity/thừa nếu composite query index đã cover; phải kiểm tra MySQL `SHOW INDEX` trước khi drop.

### 14.2 Concurrency/idempotency

1. Publish lock release head và kiểm tra expected release/working revision.
2. Overlay mutation atomic increment `overlay_revision`.
3. Apply update lock install và kiểm tra expected applied release/overlay revision.
4. Request mutation dùng `revision BIGINT` và conditional state transition.
5. Unique constraints là hàng rào cuối cho retry/race.
6. Lock source rows theo sorted IDs để giảm deadlock.
7. Hai approve/reject/publish/apply đồng thời chỉ một action được commit.

### 14.3 Large jobs

1. Small sparse release có thể chạy synchronous.
2. 10.000-50.000 changes phải chạy DB-backed job với `building` state.
3. Job batch/resume idempotent; head swap cuối phải ngắn.
4. Repo hiện chưa có background worker thật, nên phase này phải bổ sung worker/CLI process thay vì giữ request Gunicorn mở lâu.
5. Notification không fan-out trong publish transaction; push/email sau này dùng transactional outbox.

## 15. V1 scope

### In-scope

1. Clone note-field set/remove/clear override.
2. FieldDef non-destructive property update.
3. Field add/order sau khi stable identity/backfill hoàn tất.
4. Contribution staging, sync/conflict, whole-request merge/reject.
5. Owner release preview/publish/history.
6. Clone update preview/rebase/apply.
7. Git-like paginated React diff.
8. Tombstone/membership cho Note/Card cần retire.
9. Audit, concurrency, idempotency và progress preservation.

### Deferred sau v1

1. Partial item merge.
2. Review comment threads.
3. Multi-branch/cherry-pick.
4. Shared NoteType release dependency đầy đủ.
5. Local deck tree contribution add/move/delete.
6. Tag contribution.
7. Template/card-layout contribution nếu chưa có tombstone/version dependency.
8. Push/WebSocket/email notification.
9. Physical cleanup/garbage collection của retired entities.

## 16. Test matrix

### 16.1 Functional version/update

1. Owner edit field cũ nhưng chưa publish: clone browse/study không đổi.
2. Publish một field: đúng một sparse delta, không tạo rows theo card/install.
3. Merge contribution: chưa có notification/update cho clone khác.
4. Chỉ publish mới tạo available update.
5. Clone mark seen/dismiss: applied release không đổi.
6. Apply update: pointer advance và effective value đúng.
7. Jump N -> N+3 collapse đúng changes cùng key.
8. Local override khác key được giữ.
9. Cùng key tạo conflict và ba resolution modes đúng.
10. Local bằng upstream thì override được prune.
11. Note/Card retire không xóa progress/history.
12. Update trong lúc study session đang mở không corrupt session.

### 16.2 Contribution

1. Draft chỉ lấy persisted overlay.
2. Base release đúng ngay cả khi owner đổi source trước lúc build draft.
3. Submit yêu cầu sync/revision mới nhất.
4. Submitted snapshot không đổi khi learner sửa local tiếp.
5. Reject giữ nguyên overlay và source/release không đổi.
6. Merge sửa owner working tree nhưng không publish/cleanup overlay.
7. Merge -> owner publish -> contributor apply tự prune redundant overlay.
8. Shared NoteType ngoài deck scope không bị rewrite âm thầm.

### 16.3 Progress identity

1. Note field update giữ nguyên Note/Card IDs.
2. Toàn bộ `CardProgress` fields giữ nguyên: due, queue, revision, reps, lapses, stability/difficulty.
3. `ReviewEvent` và stats history giữ nguyên.
4. Retire/reintroduce card phục hồi đúng previous progress visibility.

### 16.4 Concurrency/idempotency

1. Hai publish cùng base: một thắng.
2. Retry cùng idempotency key không duplicate release.
3. Apply update đua với local edit.
4. Submit đua với overlay edit.
5. Hai active draft cùng install.
6. Approve vs reject đồng thời.
7. Hai contributions đụng cùng source field.
8. Worker crash giữa batch và resume.
9. MySQL deadlock/retry thật.

### 16.5 Security/audit

1. IDOR giữa owner/install/request/release.
2. Source note/field phải thuộc owner, deck subtree và release membership.
3. Field ID ngoài schema không được merge/apply.
4. Owner transfer/revocation được revalidate tại mutation time.
5. Diff richtext/HTML luôn escaped/sanitized.
6. Media vẫn đi qua proxy/asset safety flow.
7. Payload/rate/item limits cho large draft.
8. Collaboration audit không bị cascade-delete theo user/install.

### 16.6 Migration/dialect

1. Empty/populated upgrade trên SQLite và MySQL 8.
2. Partial schema/retry/backfill resume.
3. Old app trên expanded schema.
4. New app khi pointer/backfill còn null.
5. JSON canonical hash và MySQL datetime precision.
6. FK cascade proof: release retire/update không xóa CardProgress.

## 17. Performance gates

Benchmark datasets:

1. 10.000 và 50.000 Notes.
2. 1-2 Cards/Note.
3. 8 và 20 fields.
4. Change density: 1 field, 100 fields, 1%, 10%, 100%.
5. 1, 1.000 và 100.000 installs.

Mục tiêu ban đầu:

1. Một owner/local field edit: O(1) DB rows, p95 < 200 ms.
2. Publish một field: p95 < 500 ms và không scan/materialize toàn deck.
3. Diff summary 50.000 changes: p95 < 300 ms.
4. First page 100 diff items: p95 < 400 ms, <= 8 SQL queries, response < 1 MB.
5. Apply update với <= 100 local overrides: p95 < 500 ms.
6. Study next/count overhead do release projection <= 15%, p95 < 250 ms trên test host.
7. Publish 50.000 changes chạy async; final head swap < 1 giây, full job target < 60 giây trên MySQL test host.
8. Publish tạo O(1) head/notification writes dù có 100.000 installs.
9. Virtual diff giữ DOM rows xấp xỉ viewport + overscan, mục tiêu < 150.
10. Một changed field tạo một dirty row và một immutable delta; không full-card/full-install copies.

Theo dõi bắt buộc:

1. SQL query count và rows examined.
2. Temp table/filesort.
3. Lock wait/deadlock/retry.
4. Peak RSS của worker.
5. Serialized payload size.
6. Release/checkpoint storage growth.

## 18. Definition of Done

Feature chỉ được coi là hoàn tất khi:

1. Owner edit không leak sang clone trước publish.
2. Merge contribution không publish ngầm.
3. Reject và merge đều không làm mất local overlay.
4. Chỉ explicit publish mới tạo immutable release và update availability.
5. Clone luôn xem diff/changelog trước khi apply hoặc defer.
6. Apply update giữ stable Note/Card identity và toàn bộ study history.
7. Diff/API/UI hoạt động với 50.000 changed items theo performance gates.
8. Storage tăng theo changed fields, không theo toàn bộ cards/installs.
9. Mutation quan trọng idempotent và an toàn khi concurrent.
10. Migration/cutover được verify trên MySQL thật, không chỉ SQLite.
11. Legacy overlay-only install/cutover tests vẫn pass.
12. Tài liệu runtime/cutover/runbook được cập nhật khớp code.

## 19. Baseline verification trước khi bắt đầu implementation

Lần khảo sát gần nhất đã chạy:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_deck_change_request_flow tests.test_vocab_seed_sharing
```

Kết quả baseline: 19 tests pass.

Đây chỉ chứng minh flow hiện tại không regression ở SQLite test harness; chưa phải proof cho immutable releases, MySQL performance hoặc large-deck behavior.
