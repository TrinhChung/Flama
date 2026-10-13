# Báo cáo & Kế hoạch Xử lý: Versioning và Publish lại khi 1 NoteType gắn nhiều Template

> **Ngày lập báo cáo:** 2026-10-12
> **Phạm vi:** Kiến trúc Template Library (`Template`, `StudyApplication`), Versioning (`TemplateVersion`, `TemplateRelease`), phát hành lại Deck (`DeckRelease`, `DeckReleaseTemplatePin`), và phát hành lại `NoteType` độc lập trên Marketplace.

---

## 1. Quy chuẩn Mô hình Quan hệ giữa `NoteType` và `Template`

- **1 `NoteType` $\leftrightarrow$ Nhiều `Template` khác nhau (`N–N` ở cấp bảng, `1–1` trên mỗi cặp `(note_type_id, template_id)`)**:
  - Một `NoteType` có thể gắn nhiều `Template` khác nhau (ví dụ: Template Từ vựng, Template Nghe hiểu, Template Luyện gõ).
  - Một `Template` trong thư viện cá nhân có thể được tái sử dụng (gắn) cho nhiều `NoteType` khác nhau.
  - **Không gắn lặp cùng 1 `Template` nhiều lần vào cùng 1 `NoteType`**: Do các Template hiện đại đã nhận đầu vào có ngữ nghĩa (`input_schema`: `word`, `reading`, `meaning`, `audio`, `example`...), việc đảo chiều thẻ học được xử lý trực tiếp bởi logic của Template hoặc bằng các Template thiết kế chuyên biệt, thay vì gắn lặp cùng một `Template` với nhiều `occurrence_key` khác nhau.
  - Trên mỗi cặp `(note_type_id, template_id)`, chỉ tồn tại tối đa **1 bản ghi `StudyApplication` đang `ACTIVE`** (sử dụng `occurrence_key = "compat"`).

---

## 2. Các luồng Versioning & Publish ĐÃ hoạt động tốt

1. **Lịch sử phiên bản (`TemplateVersion`) và phát hành (`TemplateRelease`) độc lập cho từng Template**:
   - Mỗi [`Template`](file:///d:/Project/nihongo/models/template.py) quản lý lịch sử [`TemplateVersion`](file:///d:/Project/nihongo/models/template_version.py) append-only riêng thông qua [`template_version_service.snapshot_template`](file:///d:/Project/nihongo/app/services/template_version_service.py#L78-L143).
   - Các thông tin gắn kết (`input_bindings`, `display_name`, `position`, `is_default`, `status_code`) nằm trên [`StudyApplication`](file:///d:/Project/nihongo/models/study_application.py), tách biệt hoàn toàn với mã nguồn HTML/CSS của `Template`.
2. **Theo dõi thay đổi Working Tree & Auto-Publish của Deck**:
   - [`deck_working_tree_service.py`](file:///d:/Project/nihongo/app/services/deck_working_tree_service.py#L31-L92) lắng nghe sự kiện ORM trên cả `Template` và `StudyApplication`, tự động tăng `working_revision` của các `DeckMarketplaceItem` liên quan và kích hoạt [`trigger_auto_publish_for_deck_item`](file:///d:/Project/nihongo/app/services/deck_auto_publish_service.py#L26-L78) khi bật auto-publish.
3. **Tính Diff và Đóng băng (Pin) danh sách Template theo từng bản `DeckRelease`**:
   - [`_build_release_diff_plan`](file:///d:/Project/nihongo/app/services/deck_release_service.py#L1223-L1244) gọi [`deck_template_presentations`](file:///d:/Project/nihongo/app/services/template_release_service.py#L515-L539) để phát hiện mọi thay đổi: gắn thêm template mới, gỡ (`RETIRED`) template cũ, sửa `input_bindings`, hoặc sửa HTML/CSS/`input_schema`.
   - Khi phát hành bản `DeckRelease` mới, [`capture_deck_release_template_pins`](file:///d:/Project/nihongo/app/services/template_release_service.py#L489-L512) tự động snapshot + publish `TemplateRelease` cho từng `Template` đang `ACTIVE` trên `NoteType` và lưu vào bảng [`DeckReleaseTemplatePin`](file:///d:/Project/nihongo/models/template_publication.py#L77-L108).
   - [`query_clone_scope_cards`](file:///d:/Project/nihongo/app/services/flashcards_share_service.py#L2982-L3000) lọc thẻ nguồn theo đúng cặp `(Card.template_id, Card.application_id)` được pin trong `DeckReleaseTemplatePin` của bản release mà người học đang dùng (`applied_release_id`).

---

## 3. Các Điểm Chưa Ổn (Unresolved Issues) Cần Xử Lý Tiếp

### Điểm 1: [ĐÃ XỬ LÝ] Khi người học bấm Update Deck (Rebase sang `DeckRelease` mới), tự động 3-way merge các Template đã cài và đồng bộ `StudyApplication` trên `installed_note_type_id`

- **Vị trí code**:
  - [`app/services/deck_install_rebase_service.py`](file:///d:/Project/nihongo/app/services/deck_install_rebase_service.py#L1102-L1108) (`apply_prepared_update`)
  - [`app/services/template_release_service.py`](file:///d:/Project/nihongo/app/services/template_release_service.py#L591-L725) (`_sync_subscription_to_pinned_release`, `_attach_received_template`, `_retire_unpinned_received_applications`, `stage_install_template_subscriptions`)
- **Giải pháp đã triển khai**:
  1. Trong `stage_install_template_subscriptions`: Khi `subscription["applied_release_id"] != pin["template_release_id"]` và bản pin mới có `sequence_no` cao hơn, gọi `_sync_subscription_to_pinned_release` để tự động chạy 3-way merge (`_prepare` + `_apply` nếu `status == "ready"`) cho `local_template_id`, bảo toàn chỉnh sửa không xung đột của người học.
  2. Trong `_attach_received_template`: Tự động bổ sung `FieldDef` còn thiếu từ `source_note_type` sang `installed_note_type_id`, đồng thời thực hiện 3-way merge `input_bindings`, `display_name`, `is_default`, `position` so với `base_app` của bản release trước (chỉ cập nhật các thuộc tính người học chưa tự tùy biến riêng) và kích hoạt lại `status_code = "ACTIVE"` nếu Template được gắn lại.
  3. Trong `_retire_unpinned_received_applications`: Tự động chuyển `status_code = "RETIRED"` cho các `StudyApplication` trên `installed_note_type_id` của những Template từng có trong các bản release trước của Deck nhưng đã bị gỡ khỏi `DeckReleaseTemplatePin` hiện tại.

---

### Điểm 2: Publish lại `NoteType` độc lập trên Marketplace không tự phát hành `TemplateRelease` mới nếu payload không gửi kèm `publish_status`

- **Vị trí code**:
  - [`app/services/flashcards_share_service.py`](file:///d:/Project/nihongo/app/services/flashcards_share_service.py#L1727-L1748) (`apply_note_type_marketplace_payload`)
  - [`app/services/template_release_service.py`](file:///d:/Project/nihongo/app/services/template_release_service.py#L550-L588) (`stage_note_type_publications`, `stage_note_type_template_subscriptions`)
- **Hiện trạng & Nguyên nhân**:
  1. Trong `apply_note_type_marketplace_payload`, lệnh `stage_note_type_publications(db.session, note_type_id=note_type.id, actor_user_id=note_type.user_id)` chỉ được gọi bên trong khối `if "publish_status" in payload:`. Nếu một `NoteType` đã ở trạng thái `published` hoặc `unlisted`, sau đó tác giả sửa Template hoặc gắn thêm Template mới rồi cập nhật `NoteType` (ví dụ chỉ truyền `version: "1.1.0"`, `changelog: "..."` mà không truyền lại `"publish_status"`), thì `stage_note_type_publications` không chạy.
  2. Khi người học mới cài đặt `NoteType` đó, `stage_note_type_template_subscriptions` gọi `stage_note_type_publications(..., initialize_only=True)`. Do `initialize_only=True` bỏ qua mọi Template đã từng có `head` release trước đó, người cài mới sẽ nhận bản `TemplateRelease` cũ thay vì bản Template hiện tại của `NoteType`.
- **Hướng xử lý đề xuất**:
  - Trong `apply_note_type_marketplace_payload`, luôn gọi `stage_note_type_publications(..., initialize_only=False)` mỗi khi trạng thái hiệu lực của `NoteType` sau cập nhật nằm trong `visible_statuses` (`published`, `unlisted`), bất kể `publish_status` có mặt trong payload hay đã được bật từ trước.
  - Khi tác giả sửa `Template` hoặc `StudyApplication` của một `NoteType` đang được chia sẻ độc lập, cân nhắc tự động stage hoặc cung cấp luồng republish rõ ràng.

---

### Điểm 3: Chốt chặn cũ `_ensure_version_safe_template_mutation` xung đột với kiến trúc Template Library mới

- **Vị trí code**:
  - [`app/services/flashcard_content_service.py`](file:///d:/Project/nihongo/app/services/flashcard_content_service.py#L859) (`create_template`, `reset_template`, `delete_template`)
  - [`app/services/flashcard_content_service.py`](file:///d:/Project/nihongo/app/services/flashcard_content_service.py#L1618-L1660) (`_ensure_version_safe_template_mutation`)
  - [`app/services/template_version_service.py`](file:///d:/Project/nihongo/app/services/template_version_service.py#L229-L236) (`restore_version`)
- **Hiện trạng & Nguyên nhân**:
  - Ở các API mới trong [`template_library_service.py`](file:///d:/Project/nihongo/app/services/template_library_service.py), tác giả được phép gắn thêm Template, retire Template, và sửa `input_schema` trên `NoteType` đã có Deck phát hành vì `DeckReleaseTemplatePin` đã cô lập hoàn toàn các bản release cũ.
  - Tuy nhiên, các hàm cũ trong `flashcard_content_service.py` và hàm khôi phục phiên bản `template_version_service.restore_version` (khi phiên bản cũ có `input_schema` khác hiện tại) vẫn gọi `_ensure_version_safe_template_mutation` và trả lỗi cứng `409 SHARED_SCHEMA_VERSIONING_REQUIRED`.
- **Hướng xử lý đề xuất**:
  - Gỡ bỏ chốt chặn `SHARED_SCHEMA_VERSIONING_REQUIRED` đối với thao tác thêm/xóa/reset Template và khôi phục `TemplateVersion` khi các Deck liên quan đã sử dụng cơ chế `DeckReleaseTemplatePin`.

---

### Điểm 4: Migration `20261012_000057_modernize_flashcard_templates.py` chỉ tra `FieldDef` theo cột `templates.note_type_id` cũ

- **Vị trí code**:
  - [`migrations/versions/20261012_000057_modernize_flashcard_templates.py`](file:///d:/Project/nihongo/migrations/versions/20261012_000057_modernize_flashcard_templates.py#L106-L150)
- **Hiện trạng & Nguyên nhân**:
  - Khi nâng cấp các Template cũ, script migration lấy danh sách `fields` dựa trên cột `templates.note_type_id`. Đối với các Template độc lập trong thư viện (`templates.note_type_id IS NULL`) được gắn vào `NoteType` thông qua bảng `study_applications`, `fields` sẽ rơi vào danh sách rỗng `[]` (chỉ suy luận được từ các token `{{...}}` có sẵn trong HTML).
- **Hướng xử lý đề xuất**:
  - Nếu cần chạy lại hoặc viết script backfill bổ sung, cần fallback sang truy vấn `study_applications` (`status_code = 'ACTIVE'`) để lấy `note_type_id` và `field_defs` khi `templates.note_type_id IS NULL`.
