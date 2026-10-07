# ADR-T1 — Nền phiên bản template v2

- Ngày: 2026-10-07. Người thực hiện/review: Codex, tiếp nhận công việc Claude theo yêu cầu người dùng.
- Phạm vi đã triển khai: CT-02/CT-03; Contract A2 cho lịch sử của chủ sở hữu. Quyết định U1–U8 trong kế hoạch tổng vẫn có hiệu lực.
- Đây là bước **expand**: `Template.note_type_id` vẫn bắt buộc. Template độc lập, attachment bindings, market copy cấp người dùng và release core chưa triển khai.

## Căn cứ và lựa chọn

`models/template.py`, `models/study_application.py` và `study_artifact_service.py` hiện dùng Template ID cho Card, attachment, composition và artifact. Đổi ID sẽ ảnh hưởng phiên học và tiến độ. Các writer trong content/share, MCP, Connect import, import legacy, media normalization và study-note-template dùng ORM instance; riêng lệnh purge và script raw SQL bỏ qua ORM hooks.

Chọn mở rộng trực tiếp `templates` và thêm `template_versions`. Phương án v1 tạo `template_definitions` và fork theo từng install không đáp ứng U1/U2. Cutover toàn bộ attachment/render/release trong cùng migration có phạm vi lớn và chưa đủ seam tương thích; làm sau nền phiên bản, với contract riêng.

## Bất biến

- Giữ nguyên Template/Card/StudyApplication ID và nguồn HTML/CSS, không đổi renderer, sanitizer, media proxy, scheduler hoặc overlay.
- Version lưu chính xác nguồn, kể cả Unicode và CRLF. Hash dùng GT-08; so sánh cả `input_schema` khi chống bản trùng.
- Một transaction thành công tạo tối đa một bản cuối cho mỗi template đã đổi nội dung. Nhiều flush khi import không thành nhiều version. Sửa hàng cũ chưa backfill giữ thêm baseline trước sửa.
- Đổi tên hoặc lưu lại nội dung giống hệt không thêm version. Restore được xác nhận luôn thêm version, kể cả nguồn giống hiện tại; không sửa/xóa bản cũ.
- Version được ghi trong transaction của nội dung. Rollback toàn transaction hoặc savepoint không để lại version hay metadata của thay đổi đã hủy.
- Owner history/restore trả 404 cho template ngoài quyền sở hữu. Schema của template đã có release vẫn chịu guard hiện tại; restore chỉ nội dung giữ luật hotfix #138 cho tới CT-07.
- Artifact freeze hiện tại giữ nguyên cơ chế hash nguồn/field/ABI và ID; `current_version_id` không thay thế version của artifact.

## Schema và concurrency

Migration `20261007_000053` nối sau `20261006_000052`. `templates` thêm `owner_user_id` nullable (FK users, CASCADE), `input_schema` JSON nullable, `current_version_id` UUID nullable. Pointer được quản lý bởi ứng dụng, không tạo FK vòng với bảng version.

`template_versions` có UUID PK, `template_id` FK CASCADE, `version_no > 0`, unique `(template_id, version_no)`, ba nguồn Text, schema JSON, hash 64 ký tự, origin, change note, creator FK SET NULL và timestamp. `input_schema = []` cho dữ liệu cũ: chưa suy diễn binding trước bước attachment. Không thay đổi `note_type_id` hay các bảng progress.

Session hook `before_flush` thu thay đổi; `before_commit` flush và chụp trạng thái cuối. Template row là khóa `FOR UPDATE`; đọc head và cấp sequence cũng dùng current read để không lấy snapshot cũ ở MySQL REPEATABLE READ. Restore refresh identity map dưới khóa trước khi xét schema guard. Nguồn ORM chưa khai báo actor ghi `created_by = null`; không suy đoán người sửa từ owner.

Các đường raw/bulk SQL phải gọi repository/backfill rõ ràng. ORM chặn update/delete trực tiếp TemplateVersion; đây là bảo vệ ứng dụng, không phải quyền bất biến ở DB. Xóa Template/NoteType/User theo quyền hiện có được phép cascade lịch sử.

## Contract A2 đã chạy

Canonical:

```text
GET  /api/card-templates/<template_id>/versions
GET  /api/card-templates/<template_id>/versions/<version_id>
POST /api/card-templates/<template_id>/versions/<version_id>/restore
```

Alias tương thích có prefix `/api/note-types/<note_type_id>/templates/<template_id>/versions`. Login và quyền owner bắt buộc. List trả `schema_version: "template-versions.v2"`, `template_id`, `current_version_id` nullable, `items` giảm dần theo version_no. Không có `definition_id`.

Summary: `id`, `template_id`, `version_no`, `content_hash`, `change_note` (chuỗi), `origin`, `created_at` (ISO UTC), `created_by: {id, username} | null`, `is_current`. Detail thêm `front_html`, `back_html`, `shared_css`, `input_schema`.

Restore body chỉ nhận `{}` hoặc `{change_note: string}`; note tối đa 1000 ký tự. Thành công 200 trả serializer Template hiện có, thêm `current_version_id`. Lỗi: `TEMPLATE_NOT_FOUND`/`TEMPLATE_VERSION_NOT_FOUND` 404, `VALIDATION_ERROR`/`TEMPLATE_COMPILE_ERROR` 400, `SHARED_SCHEMA_VERSIONING_REQUIRED` 409. Restore version của template khác cũng 404. GET thành công không cache công khai.

PATCH content hiện có nhận `change_note`; rename/no-op không tạo version. Reset dùng origin `reset`. List schema có thể chưa có version cho raw SQL row; backfill phải chạy trước khi phát hành UI cho dữ liệu cũ.

## Deploy và rollback

1. Backup schema/data và dừng writer chính + Connect. Chạy Alembic upgrade tới `20261007_000053` bằng migration runner, trước khi process mới đọc Template columns. Không dùng `db.create_all()` để bổ sung cột bảng đã có.
2. Migration preflight kiểm tra schema, owner, pointer, nguồn/hash trước DDL; giữ nguyên timestamp nguồn, backfill theo lô 500 bằng UUID5. Có thể chạy lại khi schema đã đúng; drift phải được xử lý trước.
3. Đối chiếu số Template/Card, orphan, pointer/version và byte nguồn; khởi động thật qua `wsgi.py` và Connect. Không bật startup compatibility repair để thay cho migration.
4. CLI bổ sung: `flask --app wsgi.py template-versions-backfill` mặc định rollback dry run; thêm `--apply` mới commit, dành cho row raw SQL hoặc dữ liệu tạo bằng schema mới chưa có lịch sử.
5. Rollback application giữ schema expand và lịch sử. Downgrade chỉ phục vụ rehearsal baseline chưa sửa; từ chối lịch sử authored hoặc nhiều version để tránh mất dữ liệu.

Không áp dụng migration lên database ứng dụng thật trong phiên làm việc này. Kết quả test và rehearsal ghi ở [báo cáo CT-02/03](../task/template-features/reviews/CT-02_CT-03_CODEX_IMPLEMENTATION_2026-10-07.md).

## Các bước còn lại

CT-04 thêm resolver tương thích; CT-06 chuyển attachment và bindings theo FieldDef ID trước khi cho NoteType nullable. CT-05 làm market copy theo user/source, không theo install. CT-07 đưa release core và #137 theo U7. Chưa đóng băng Contract D/E/F; GT-11/12/13 tiếp tục blocked, tránh triển khai theo spec v1.
