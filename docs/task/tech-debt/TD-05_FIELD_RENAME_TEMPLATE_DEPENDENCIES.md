# TD-05 — Đổi tên hoặc xóa Field làm Template render rỗng, không cảnh báo

> Mức: **P1** · Đợt: W2 · Trạng thái: `TODO`
>
> Phụ thuộc: không · Bị thay thế lâu dài bởi: TD-18 (binding theo ID) · Lane: Backend + Frontend Note types · Ước lượng: 2–3 ngày
>
> Quyết định đã chốt ([điều tra §14](../../architecture/template-notetype-decoupling-investigation.md)):
> - #19: Template legacy còn nhúng tên Field → hiển thị các phụ thuộc và **hỏi** người dùng có cập nhật hay không; không phải cơ chế định danh hay ép viết lại toàn cục;
> - #20: Field bị xóa → cảnh báo, không làm hỏng Note.

## Mục tiêu

Khi đổi tên hoặc xóa Field, người dùng thấy Template nào đang dùng Field đó và chọn cập nhật placeholder, thay vì Template âm thầm hiển thị trống.

## Bối cảnh

- `update_field` đổi tên bằng cách viết lại khóa JSON trong mọi Note của NoteType (`app/services/flashcard_content_service.py:618-632, 1622-1662`), nhưng **không** đụng Template.
- Placeholder như `{{TênCũ}}`, `{{#TênCũ}}…{{/TênCũ}}`, `{{text:TênCũ}}`, `{{TênCũ_url}}` sau đó render rỗng.
- Renderer đã có logic nhận diện token Field (`app/services/flashcard_renderer.py:265-300, 399-426`) để tái sử dụng.

## Phạm vi file dự kiến

- Backend:
  - `app/services/flashcard_content_service.py`: hàm phân tích phụ thuộc; tham số `rewrite_templates`; áp dụng cho `delete_field` để chỉ cảnh báo;
  - `app/services/flashcard_renderer.py`: tách hàm liệt kê token dùng chung.
- API: `app/api/v1/flashcards/note_types.py` (`PATCH` field nhận `rewrite_templates`; `GET` phụ thuộc).
- Frontend: `features/note-types/pages/NoteTypeFieldsPage.tsx` (dialog đổi tên/xóa hiện danh sách Template bị ảnh hưởng).
- Test backend + frontend.

## Công việc chi tiết

1. **Phân tích phụ thuộc:** với mỗi Template của NoteType, liệt kê vị trí dùng Field theo mọi cú pháp:
   - biến `{{F}}`;
   - section `{{#F}}`, `{{^F}}`, `{{/F}}`;
   - filter `{{xxx:F}}`;
   - `{{F_url}}`;
   - trong thuộc tính media.

   Đánh dấu riêng các tham chiếu trong `<script>` (chỉ cảnh báo, không tự sửa).
2. **Endpoint xem trước:** `GET /note-types/<id>/fields/<field_id>/template-dependencies` trả `[{template_id, template_name, occurrences, script_refs}]`.
3. **Đổi tên:**
   - `PATCH` với `rewrite_templates: true` viết lại placeholder trong **cùng transaction** với rename job;
   - bảo toàn khoảng trắng và định dạng;
   - áp dụng guard version-safe hiện có (NoteType có deck phát hành thì trước TD-16 bị chặn kèm giải thích; sau TD-16 thì ghi vào bản làm việc).
4. **Xóa Field:** dialog liệt kê Template sẽ hiển thị trống; không tự sửa; gợi ý mở trình soạn.
5. **UI:**
   - dialog đổi tên có danh sách phụ thuộc;
   - lựa chọn "Cập nhật N Template" (mặc định bật) hoặc "Chỉ đổi tên";
   - cảnh báo riêng cho tham chiếu trong script.
6. Audit log ghi Template đã được viết lại.

## Output đầu ra bắt buộc

Phân tích phụ thuộc + endpoint + rewrite có transaction + UI + test cú pháp (bảng fixture); handoff.

## Acceptance criteria

- Đổi tên Field có chọn cập nhật: mọi Template render như trước khi đổi (test so sánh output render).
- Chọn "Chỉ đổi tên": UI đã cảnh báo trước và liệt kê đúng Template bị ảnh hưởng.
- Xóa Field: cảnh báo đúng; Note không hỏng; phiên đang mở không đổi.
- Tham chiếu trong script không bị tự sửa và được báo riêng.

## Verification

```text
python scripts/run_tests.py --module flashcards --backend-only
python scripts/run_tests.py --module flashcards --frontend-only
```

## Rollback

Tham số `rewrite_templates` mặc định `false` ở API. Revert UI.

## Không làm trong task này

Binding theo ID (TD-18); đổi tên Field trên deck đã cài (overlay field hiện có).
