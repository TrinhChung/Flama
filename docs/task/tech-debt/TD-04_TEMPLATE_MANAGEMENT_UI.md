# TD-04 — Trình quản lý Template: tạo, đổi tên, xóa, nhân bản, chống mất bản nháp

> Mức: **P1** · Đợt: W2 · Trạng thái: `TODO`
>
> Phụ thuộc: không; sau TD-16 thì luồng lưu trên NoteType đã phát hành đổi sang "bản làm việc" · Lane: Frontend Note types (+ API sẵn có) · Ước lượng: 3–4 ngày
>
> Nguồn: T1–T8 ở [hành trình người dùng](../../backend/old/decoupling/UIUX_COMPLETED_PHASES_USER_JOURNEY_AUDIT_2026-09-30.md) §2.1. Quyết định D-T4 (sao chép Template đang chọn) và D-T5 (cho xóa) là khuyến nghị, cần chủ sản phẩm xác nhận.

## Mục tiêu

Người dùng tạo, đặt tên, đổi tên, nhân bản, xóa Template một cách an toàn, hiểu hệ quả (thêm Template là thêm một cách học; tiến độ dùng chung theo Note), và không mất bản đang soạn.

## Bối cảnh và bằng chứng

| Vấn đề | Bằng chứng |
|---|---|
| Nút "Mới" tạo `Card N` với `{{Word}}`/`{{Word}}`, không hỏi | `frontend/src/features/note-types/pages/NoteTypeDetailPage.tsx:129-144` |
| Sinh Card cho mọi Note ngay | `app/services/flashcards_share_service.py:283-285` |
| API đổi tên và xóa có sẵn nhưng UI không dùng | `app/api/v1/flashcards/note_types.py:178-204`; `flashcard_content_service.py:883-884, 934+` |
| Đổi Template hoặc rời trang làm mất bản nháp | `NoteTypeDetailPage.tsx:95-106` |
| "Reset" thay bằng mẫu legacy của hệ thống, dùng `window.confirm` | `NoteTypeDetailPage.tsx:320-330`; `flashcard_content_service.py:915-932` |
| Lỗi backend tiếng Anh hiện trong toast | `NoteTypeDetailPage.tsx:141-143` |

## Phạm vi file dự kiến

- `features/note-types/pages/NoteTypeDetailPage.tsx` (tách hook `useTemplateEditor`, component danh sách Template).
- Component mới: `TemplateCreateDialog`, `TemplateDeleteDialog`, `TemplateListPanel`.
- Ánh xạ lỗi dùng chung: `shared/api/errorMessages.ts`.
- Backend (nhỏ, tùy chọn): endpoint đếm Note/Card bị ảnh hưởng. Có thể dùng `note_count`/`card_count` trong `serialize_note_type`.
- Test component và hook.

## Công việc chi tiết

1. **Danh sách Template** thay cho `NativeSelect`: tên, số Card, nhãn "Mặc định", menu Đổi tên / Nhân bản / Xóa.
2. **Dialog tạo:**
   - tên bắt buộc;
   - nguồn: *Sao chép Template đang chọn* (mặc định) hoặc *Mẫu trống theo các trường hiện có* (sinh placeholder từ FieldDef thật, không cứng `{{Word}}`);
   - xem trước;
   - câu giải thích "Tạo thêm một cách học cho N Note; tiến độ học dùng chung theo Note".
3. **Đổi tên** qua `PATCH` với `name`. Chặn tên trùng ở client và hiển thị lỗi server nếu có.
4. **Xóa:**
   - dialog nêu số Card sẽ gỡ và khẳng định tiến độ Note được giữ;
   - chặn Template mặc định hoặc Template cuối cùng (backend đã chặn; UI giải thích trước);
   - thông báo "Phiên đang mở không bị ảnh hưởng; áp dụng từ phiên sau".
5. **Nhân bản:** như tạo, với nguồn là Template được chọn.
6. **Chống mất bản nháp:**
   - trạng thái "chưa lưu";
   - hỏi trước khi đổi Template hoặc rời trang (`useBlocker` + `beforeunload`);
   - lưu nháp cục bộ trong `localStorage` (bọc try/catch) để khôi phục.
7. **Reset:**
   - đổi nhãn thành "Thay bằng mẫu mặc định của Flama";
   - dialog của design system;
   - giữ bản trước trong phiên làm việc để "Hoàn tác" ngay.
8. Toast sau khi lưu: "Đã lưu. Áp dụng từ phiên học tiếp theo."; xóa lời gọi no-op `updateTemplateInSessions`.
9. Ánh xạ lỗi (`SHARED_SCHEMA_VERSIONING_REQUIRED`, `TEMPLATE_COMPILE_ERROR`, `VALIDATION_ERROR`…) sang tiếng Việt kèm hướng xử lý.

## Output đầu ra bắt buộc

Các thành phần UI trên kèm test; ảnh chụp trước/sau (trang có thay đổi hình thức, cần duyệt); handoff.

## Acceptance criteria

- Tạo Template mới không còn nội dung `{{Word}}` cứng; tên do người dùng đặt xuất hiện trong bộ chọn cách học.
- Đổi tên và xóa hoạt động; xóa giữ tiến độ Note (test backend hiện có + test UI).
- Không thể mất bản nháp khi đổi Template hoặc rời trang mà không được hỏi.
- Không còn `window.confirm` và toast tiếng Anh trên trang.
- NoteType của deck đã phát hành: UI giải thích vì sao bị chặn (trước TD-16) hoặc lưu vào bản làm việc (sau TD-16).

## Verification

```text
python scripts/run_tests.py --module flashcards --frontend-only
python scripts/run_tests.py --module flashcards --backend-only
```

Kèm luồng trình duyệt: tạo → đổi tên → vào học chọn cách mới → xóa (profile Chrome riêng).

## Rollback

Revert frontend. API không đổi.

## Không làm trong task này

Slot/binding (TD-18), fork cho deck đã cài (TD-17), sắp xếp Template (chờ `study_applications`/TD-18).
