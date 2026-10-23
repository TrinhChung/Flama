# TD-18 — Template độc lập có Slot và binding Field → Slot

> Mức: **P2** · Đợt: W5 · Trạng thái: `TODO`
>
> Phụ thuộc: TD-16 (và TD-15); thay thế lâu dài cho TD-05 · Chặn: TD-19 · Lane: Backend + Database + Frontend (Note types) · Ước lượng: 8–12 ngày
>
> Quyết định đã chốt ([điều tra §14](../../architecture/template-notetype-decoupling-investigation.md)): #3–#7 (Slot, gán linh hoạt, một Field vào nhiều Slot, ánh xạ theo NoteType, áp dụng một Template nhiều lần), #16–#18 (JS tạm đọc toàn bộ Field, giữ biến hệ thống `FrontSide`, `${field}_url`), #19 (binding ổn định khi đổi tên Field), #20 (Field bị xóa thì Slot trống + cảnh báo). Nguồn thiết kế: [đề xuất TPL-01](../../plans/proposals/DECOUPLE_TEMPLATE_NOTE_TYPE_PROPOSAL.md) §2–§5, [canonical plan §5](../../architecture/study-interaction-trigger-algorithm-plan.md).

## Mục tiêu

Template trở thành **component độc lập**, khai báo Slot (ví dụ `question`, `answer`, `audio`). Việc áp dụng Template vào một NoteType là **binding** Slot → FieldDef theo ID. Một Template dùng được cho nhiều NoteType và nhiều lần trên một NoteType. Đổi tên Field không làm gãy Template.

## Bối cảnh

- Hiện `templates.note_type_id` bắt buộc; placeholder `{{TênField}}` là định danh.
- Binding duy nhất là `legacy-fielddef-direct` (`app/services/study_session_service.py:767`, `study_session_config.py:122`).
- Phase 6 đã có `study_applications` (application = Template áp dụng vào NoteType), nhưng chưa có binding.
- P6 plan đẩy "binding kind mới" sang Phase 8. Task này kéo phần binding lên trước theo chỉ đạo "module hóa Template" (không cần Interaction mới).

## Phạm vi file dự kiến

- Model/migration (theo ADR TD-14):
  - định nghĩa Template độc lập (sở hữu bởi user/package, `slot_schema` phiên bản hóa);
  - `application_bindings` (application → slot → `field_def_id` | hằng | để trống) có `binding_fingerprint`;
  - Template cũ chuyển thành định nghĩa + binding tương thích, suy ra Slot từ placeholder (giữ nguyên hành vi).
- Renderer: `app/services/flashcard_renderer.py`, `frontend/src/features/study/renderer/clientRenderer.ts` (phân giải Slot trước Mustache; alias cũ vẫn chạy).
- Phiên học: `study_session_service.py`, `study_session_config.py`, `frontend/src/features/study/types.ts` (`StudyCompositionBinding` thêm `binding_kind: 'slot-map.v1'`).
- Adapter engine: `kinds/slot_binding.py` (release, fork, đóng góp cho binding).
- Frontend: trình soạn Template ở chế độ Slot; **Field Mapping Editor** (Slot trái, dropdown Field phải, cảnh báo đỏ khi thiếu Slot bắt buộc); **Áp dụng Template cho NoteType**; áp dụng lặp (D6-09).
- Anki import (#13–#14): chuẩn hóa token Field của Anki thành Slot khi nhập (có thể tách thành sub-task).

## Công việc chi tiết

1. Chốt `slot_schema` v1: key máy bất biến, nhãn hiển thị, kiểu (`text`, `richtext`, `audio`, `image`…), bắt buộc/tùy chọn, giá trị mặc định.
2. Migration tương thích:
   - mỗi Template hiện có sinh định nghĩa + binding 1:1 với placeholder đang dùng;
   - Card ID, application và `source_ord` giữ nguyên;
   - kết quả render phải trùng từng byte trên toàn bộ fixture.
3. Renderer:
   - phân giải Slot → giá trị theo `field_def_id`;
   - binding thiếu thì hiện placeholder mờ `[Chưa gán: <Slot>]` và cảnh báo trong trình soạn, không lỗi toàn thẻ (#20);
   - biến hệ thống giữ nguyên (#18);
   - JS vẫn đọc được toàn bộ Field qua ABI legacy có đo lường (#16–#17).
4. Đổi tên Field chỉ đổi nhãn. Binding không đổi, không cần viết lại Template (thay giải pháp tạm TD-05).
5. Xóa Field: Slot liên quan thành trống + cảnh báo, Note không hỏng.
6. Áp dụng lặp:
   - cùng Template gắn nhiều lần vào một NoteType với binding khác nhau (ví dụ xuôi và ngược);
   - mỗi lần gắn là một application mới, sinh Card qua content topology;
   - tiến độ vẫn một phần cho mỗi Note.
7. Phiên học ghim version định nghĩa + binding fingerprint. Khôi phục phiên kiểm tra khớp.
8. Engine: adapter `slot_binding` để binding được phát hành, fork, rebase và đóng góp như các kind khác.
9. UI:
   - thư viện Template của tôi;
   - áp dụng Template vào NoteType qua wizard ánh xạ Field;
   - xem trước bằng dữ liệu mẫu hoặc một Note thật (không ghi tiến độ).
10. Cập nhật canonical plan §5/§9 và P6 plan (binding kind không còn chờ Phase 8).

## Output đầu ra bắt buộc

Schema + migration có rehearsal MySQL; renderer server + client khớp nhau (golden fixture render); UI ánh xạ; adapter `slot_binding`; test đổi tên/xóa Field; tài liệu cập nhật.

## Acceptance criteria

- Toàn bộ Template hiện có render giống hệt trước migration (fixture production-like).
- Một Template gắn cho hai NoteType khác schema render đúng; gắn hai lần trên một NoteType tạo hai cách học, chung tiến độ Note.
- Đổi tên Field không làm đổi kết quả render; xóa Field hiện cảnh báo, không lỗi phiên học.
- Phiên đang mở không đổi khi sửa binding.
- Thẻ đã cài dùng binding tại release đã ghim; fork binding hoạt động qua engine.

## Verification

```text
python scripts/run_tests.py --module study,flashcards,decks,deck_collaboration,connect_mcp --backend-only
python scripts/run_tests.py --module study,flashcards --frontend-only
```

Kèm golden fixture render chạy ở cả Python và TypeScript, và probe MySQL cho migration.

## Rollback

Flag render theo placeholder cũ. Binding tương thích 1:1 bảo đảm rollback không mất dữ liệu. Migration mở rộng chưa xóa cột `templates.note_type_id` (việc thu hẹp để P9 hoặc task riêng).

## Không làm trong task này

Template Marketplace (TD-19), input tính toán/biểu thức/danh sách (để quyết định sau), Interaction mới (P8).
