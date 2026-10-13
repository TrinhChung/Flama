# Native array — việc còn lại sau cutover

Ngày 2026-10-13. Đối chiếu tại `0d2965fe` (HEAD `feat/typing-back-audio-usage`).

Đã xong, không lặp lại ở đây: renderer chỉ đưa list vào Mustache, write path API/Connect/MCP note và giới hạn 3 cấp (`e14d78db`); production backfill 41.199 note, 9 template ([runbook](../../runbooks/NATIVE_ARRAY_CLEANUP_20261011.md)). Browse editor, kiểu `Record<string, unknown>` và sửa mảng lồng đang làm trong working tree ([BROWSE_FIELDS_REVIEW](../../architecture/BROWSE_FIELDS_REVIEW.md)), chưa commit.

| ID | Mức | Việc | Loại |
| --- | --- | --- | --- |
| NA-01 | P1 | MCP `sync_notes` ghi đè list bằng chuỗi | Backend |
| NA-02 | P2 | Import CSV/APKG ghi đè list bằng chuỗi | Backend |
| NA-03 | P2 | Phát hành release mới và rebase deck đã cài | Vận hành |
| NA-04 | P2 | 113 note cần biên tập nội dung/bản dịch | Nội dung |
| NA-05 | P2 | Chính sách quyền riêng tư hứa export `.apkg` | Quyết định |
| NA-06 | P3 | Trường array bắt buộc nhận `[""]` | Backend |
| NA-07 | P3 | Frontend parse chuỗi giống JSON thành list | Review |

## NA-01 — MCP `sync_notes` ghi đè list bằng chuỗi

**Vấn đề.** `sync_notes` (`app/services/mcp/note_tools.py` → `note_sync_service.preview_sync_notes` / `execute_sync_notes`) không đi qua validator note:

- `app/services/note_sync_service.py:216`: `_validate_and_normalize_note_fields` chỉ gọi `normalize_anki_field_values`, nên giá trị chữ cho trường `array` được giữ nguyên là chuỗi.
- `note_sync_service.py:39-44`: `normalize_compare_text` gọi `str(value)`. List đã lưu so sánh dưới dạng repr `['a', 'b']`.
- Vì vậy so sánh ở `:424` và `:697` luôn thấy khác, và `:718` ghi chuỗi đè lên list. Hash nội dung (`compute_note_content_hash`) cũng dùng repr.

**Ảnh hưởng.** Mỗi lần agent đồng bộ, list trở lại thành chuỗi; preview báo "thay đổi" dù nội dung giống hệt; production lại có dữ liệu trộn lẫn sau khi đã backfill.

**Hướng sửa.** Sau `normalize_anki_field_values`, gọi `clean_array_fields(normalized, field_defs)` (`app/validators/flashcard_input.py`), trả lỗi validation vào `errors` như các lỗi khác. `normalize_compare_text` dùng `field_value_text()` (`models/field_types.py`). Đổi kiểu trả về sang `dict[str, Any]`.

**Xong khi.** Test trong `tests/test_note_sync_and_mcp.py`: NoteType có trường `array`; sync với chuỗi nhiều dòng và với list đều lưu list; sync lại cùng nội dung thì preview và execute báo không đổi; list sâu 4 cấp bị từ chối.

## NA-02 — Import CSV/APKG ghi đè list bằng chuỗi

**Vấn đề.** `app/services/flashcard_import.py` không biết kiểu `array`:

- `:712` tạo Note mới với giá trị chuỗi từ file.
- `:446-450` `_normalize_compare_value` gọi `str(value)`; so sánh ở `:972` luôn thấy list đã lưu khác chuỗi tới, nên chế độ cập nhật ghi chuỗi đè list (`:985`).

**Ảnh hưởng.** Import vào NoteType đã có trường `array` tạo dữ liệu trộn lẫn; import lại cùng file vẫn báo "updated" cho mọi note.

**Hướng sửa.** Chuẩn hoá giá trị của trường `array` bằng `clean_array_fields` trước khi insert/merge; so sánh bằng giá trị đã chuẩn hoá (list với list). Seed (`seeding_service.py`) không khai báo `field_type`, nên không thuộc phạm vi.

**Xong khi.** Test import CSV vào NoteType có trường `array` (ô nhiều dòng) lưu list; import lại cùng file báo `unchanged`.

## NA-03 — Phát hành release mới và rebase deck đã cài

**Hiện trạng.** Cleanup không publish/rebase: 28 install, 27 release pin; 70.818 slot STRING còn trong checkpoint lịch sử. Clone đã cài vẫn đọc nội dung của release đang pin; sửa đổi của chủ deck chưa tới learner.

**Việc.** Khi chủ deck sẵn sàng, theo quy trình marketplace: xem preview thay đổi release (dirty atoms đã tăng 674 → 23.270 từ cutover trước, cộng thêm từ cleanup), publish release mới, rebase install. Smoke test browse/study trên clone sau rebase: item boundary, typing nhận từng đáp án, overlay của learner còn nguyên.

**Không làm.** Sửa checkpoint/release cũ trực tiếp.

## NA-04 — 113 note cần biên tập nội dung/bản dịch

Danh sách riêng tư nằm trong `/var/backups/flama/native-array-20261011/` (`production-evidence.json`, `private-manifest.json`) trên VPS. Gồm các note lệch số cột source/bản dịch và note `spacious` (lệch nhiều cột, item `bố cục thoáng roomy`). Không tự dịch hoặc xoá; chủ nội dung sửa từng note qua Browse.

## NA-05 — Chính sách quyền riêng tư hứa export `.apkg`

`frontend/src/data/legalDocumentsData.ts:546` và `legalDocumentsData.en.ts:508` hứa người dùng tải bộ thẻ dạng `.apkg`/CSV (quyền di chuyển dữ liệu). `AGENTS.md:65-68` ghi Flama không có và không làm export sang Anki.

**Cần quyết định:** sửa văn bản pháp lý (bỏ `.apkg`, giữ định dạng thực sự có) hoặc giữ cam kết và đổi chính sách sản phẩm. Trước khi sửa, xác nhận Flama hiện có export CSV hay chưa. Đổi văn bản pháp lý cần chủ sản phẩm duyệt.

## NA-06 — Trường array bắt buộc nhận `[""]`

`app/services/flashcard_renderer.py:754-761` `is_field_empty` coi list là rỗng chỉ khi `len == 0`. Validator giữ vị trí rỗng trong list (`flashcard_input.py:418`, cần cho cột cặp). Kết quả: `[""]`, `[[]]` qua được kiểm tra trường bắt buộc.

**Hướng sửa.** Kiểm tra bắt buộc coi `array` là rỗng khi không có item text nào khác rỗng (đệ quy). Vẫn lưu nguyên vị trí rỗng.

**Xong khi.** Trường bắt buộc từ chối `[""]`, `[[]]`, `[["", ""]]`; nhận `["", "a"]`.

## NA-07 — Frontend parse chuỗi giống JSON thành list

Ghi chú review cho phần Browse fields chưa commit: `parseArrayValue` trong `frontend/src/lib/arrayField.ts` (working tree) JSON-parse **mọi** chuỗi hợp lệ dạng mảng, không chỉ nội dung chế độ Code. Backend giữ chuỗi giống JSON là text (`tests/test_field_array_conversion.py`). Một item cũ có nội dung `["a"]` sẽ đổi thành list khi mở editor. Nên giới hạn parse JSON trong chế độ Code, giá trị đã lưu dạng chuỗi chỉ tách theo dòng.
