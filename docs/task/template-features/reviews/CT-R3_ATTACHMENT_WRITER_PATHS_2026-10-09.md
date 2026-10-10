# CT-R3: Đường ghi backend theo attachment — 2026-10-09

Phạm vi: rà lại backend template sau CT-04..08/CT-R2 theo yêu cầu "task backend nào chưa làm thì làm nốt". Tracker ghi mọi task Completed và module `templates` (197 test) vẫn xanh, nhưng mục tiêu gốc của GT-16 — chuyển mọi chỗ đọc `Template.note_type_id`/`NoteType.templates` sang occurrence ACTIVE — mới được làm ở REST tạo note, Connect `addNote`, MCP thêm note, danh sách/marketplace. Các đường ghi dưới đây vẫn coi template "thuộc" NoteType theo nguồn gốc legacy, trái với U1/U2 (template độc lập gắn nhiều NoteType, bản nhận không có NoteType gốc). Nhánh `refactor/frontend-fsd-renderer-boundary`, đối chiếu tại HEAD `83854b0`. Chưa commit.

## Lỗi đã sửa

| Mức | Đường | Hành vi tại HEAD | Sau sửa |
|---|---|---|---|
| P1 mất dữ liệu | `DELETE /api/note-types/<nt>/templates/<tid>`; MCP `update_note_type` gỡ template (cả nhánh legacy và NOTE) | Template legacy của NoteType A đã được gắn vào NoteType B qua library: xóa ở A xóa luôn Template, mọi Card và tiến độ của B | Template dùng chung hoặc gắn từ library chỉ bị **gỡ khỏi NoteType này** (occurrence → RETIRED, giữ Template/Card/progress, như DELETE template-application). Template legacy chỉ thuộc A vẫn xóa cứng như cũ |
| P1 mất dữ liệu | Connect `importCards` (cả Anki import trong app) | Import lại note xóa Card + tiến độ của template gắn thêm; note mới thiếu Card của template gắn thêm; tạo Card cho occurrence đã RETIRED | Reconcile theo occurrence của NoteType: chỉ xóa Card không thuộc NoteType (ví dụ đổi NoteType), giữ Card của occurrence RETIRED, tạo Card cho occurrence ACTIVE còn thiếu |
| P1 hỏng chức năng | Connect preflight/import vào NoteType đã nhận từ marketplace | Bản nhận có `note_type_id = NULL` nên NoteType không có template legacy: preflight `blocked_note_types` hoặc "model has no card template" | Ordinal Anki khớp template legacy như cũ (kể cả template đã retire để ordinal không lệch); NoteType không có template legacy dùng thứ tự occurrence ACTIVE |
| P1 hỏng chức năng | `PATCH/preview/reset/DELETE /api/note-types/<nt>/templates/<tid>` (trình sửa loại thẻ, tab đồng bộ Anki) | Template gắn từ library và bản nhận được liệt kê nhưng mọi thao tác trả 404 `Template not found.` | Route NoteType tìm template qua occurrence ACTIVE; preview chiếu input theo binding của occurrence giống render khi học (binding chưa đặt/đồng nhất giữ nguyên trường) |
| P2 | Import CSV/batch | Chỉ tạo Card cho template legacy: NoteType đã nhận ra note **không có Card**; occurrence RETIRED vẫn nhận Card mới | Card theo occurrence ACTIVE, dùng cùng quy tắc với REST tạo note |
| P2 | MCP `sync_notes` | NoteType đã nhận báo `NOTE_TYPE_HAS_NO_TEMPLATE`; template gắn thêm không có Card | Như import CSV |
| P2 | REST xóa template: mặc định và "ít nhất một template" | Đếm template legacy, bỏ qua occurrence; có thể xóa template ACTIVE cuối cùng khi template còn lại đã retire | Mặc định lấy theo occurrence (như danh sách editor), quy tắc còn lại tính occurrence ACTIVE |
| P2 rò rỉ | MCP `get_note_type_schema` cho NoteType đã publish của người khác | Trả HTML/CSS bản nháp hiện tại của tác giả | Dùng nội dung release đã đăng như marketplace; chủ sở hữu vẫn thấy bản nháp |
| P3 | Connect `addNote`, nhánh tạo template dự phòng | Truyền `front_format/back_format` không tồn tại trên `Template` (TypeError nếu chạy tới) | Dùng `front_html/back_html` |

Helper dùng chung ở `app/repositories/template_library_repository.py`: `card_slots`, `build_cards`, `plan_note_cards`, `template_used_outside`, `detach_template`. `create_cards_for_note` giữ nguyên ngữ nghĩa (occurrence ACTIVE; chỉ NoteType không có occurrence ACTIVE nào mới dùng template legacy chưa từng có occurrence; NoteType bị retire hết vẫn rỗng).

## Kiểm tra

Test mới `tests/test_template_attachment_writers.py` (14 test, đã thêm vào module `templates` của `scripts/run_tests.py`): route NoteType sửa/preview template gắn thêm, gỡ template dùng chung qua REST và MCP (legacy + NOTE), quy tắc template cuối, xóa cứng template không dùng chung, import CSV, NoteType không có template legacy, `sync_notes`, Connect import/import lại (legacy + NOTE, giữ CardProgress), và schema MCP không lộ bản nháp. Chạy trên worktree HEAD chưa sửa: 13/14 fail đúng các lỗi trên (test còn lại cố ý giữ hành vi xóa cứng).

Lệnh chạy bằng `.venv` Python, để trống 7 cờ `STUDY_*` của `.env` local:

| Lệnh | Kết quả |
|---|---|
| `scripts/run_tests.py --module templates,flashcards,connect_mcp --backend-only` | PASS: 831 test, 59 file |
| `scripts/run_tests.py --module templates,connect_mcp --backend-only` (chạy lại sau khi sửa schema MCP) | PASS: 511 test, 35 file |
| `scripts/run_tests.py --file` note-template/consolidated-connect/application-occurrence/dirty-tracking/session-api/oauth-MCP | PASS: 118 test, 6 file |
| `py_compile` các file đổi, `git diff --check` | PASS |

Không chạy migration, không ghi DB thật; không đổi schema, renderer, scheduler hay frontend.

## Chưa làm (đề xuất tiếp)

- MCP `list_note_types`/`get_note_type_schema` của chủ sở hữu và `update_note_type` vẫn chỉ thao tác template legacy: NoteType đã nhận hiện 0 template; template gắn từ library không sửa được qua MCP. Cần chốt ngữ nghĩa sửa template dùng chung qua MCP trước khi mở rộng (tránh nhánh list-mode tạo template mới khi gặp ID lạ).
- `app/services/share/note_types.py` là bản trùng không được gọi, còn mặc định `{{Word}}`; package `share/` đang được phiên khác sửa nên không động vào.
- Chuẩn hóa media template (`flashcard_media_normalizer`) bỏ qua template không có NoteType gốc; quick edit sau khi đổi tên FieldDef đồng thời vẫn dùng payload theo tên (giới hạn đã ghi ở handoff CT-04/08).
