# GT-16 — Kiểm kê mọi chỗ đọc/ghi Template và đường render (chỉ đọc)

> Historical inventory request. Candidate raw reports were never Accepted as complete inventories. The current Codex code/contract/test audit in [backend handoff](reviews/CT-04_CT-08_BACKEND_HANDOFF_2026-10-08.md) supersedes this prerequisite; do not assign this old read-only task before Gemini FE. Counts and line numbers below describe the earlier snapshot only.
- Owner: Gemini. Reviewer: Claude. Milestone: M0 (kế hoạch v2). Phụ thuộc: không. Trạng thái: **Superseded (2026-10-08)**.
- Loại: **chỉ đọc**, đầu ra là một báo cáo Markdown. Không sửa code, test hay tài liệu khác.
- Người dùng kết quả: CT-01 (ADR-T), CT-03..CT-06 (chuyển chỗ đọc `Template.note_type_id` sang attachment, render theo binding, seam ghi phiên bản).

## 1. Bối cảnh

Kế hoạch v2 biến Template thành thực thể độc lập dùng chung nhiều loại thẻ (NoteType). Trước khi đổi, Claude cần danh sách **đầy đủ, kiểm chứng được** mọi chỗ code:

- tạo/sửa/xóa Template;
- dựa vào `Template.note_type_id` hoặc quan hệ `NoteType.templates` để biết template thuộc loại thẻ nào;
- render nội dung template (server và client);
- tạo/xóa/lọc Card theo template;
- dùng `position`/`is_default`;
- serialize template ra API;
- composition/phiên học, phân phối (cài deck, clone, cutover, release), tích hợp (Anki/Connect/MCP);
- frontend gọi API template hoặc hiển thị template.

Gemini dễ bịa số dòng hoặc nội dung, vì vậy **mỗi dòng báo cáo phải có trích dẫn nguyên văn** và báo cáo phải phủ **mọi** dòng ứng viên; script ở §5 kiểm tra cả hai.

## 2. File được tạo (không sửa file nào khác)

| File | Nội dung |
|---|---|
| `docs/task/template-features/reports/GT-16_TEMPLATE_USAGE_INVENTORY.md` | Báo cáo theo §4. |
| `docs/task/template-features/reports/gt16-backend.txt` | Do script §3 sinh ra, không sửa tay. |
| `docs/task/template-features/reports/gt16-frontend.txt` | Do script §3 sinh ra, không sửa tay. |

## 3. Lệnh lấy dòng ứng viên (chạy từ repo root, giữ nguyên lệnh)

Dùng script (mẫu tìm kiếm nằm trong script để PowerShell không làm hỏng dấu ngoặc):

```powershell
python docs/task/template-features/tools/list_candidates.py gt16-backend
python docs/task/template-features/tools/list_candidates.py gt16-frontend
```

Script ghi `docs/task/template-features/reports/gt16-backend.txt` và `gt16-frontend.txt`. Tại commit `1689a0f` kết quả là **637 dòng trong 71 file** (backend: `app/`, `models/`, `connect_wsgi.py`, `study_worker.py`, trừ worksheets) và **108 dòng trong 16 file** (frontend `frontend/src`, trừ test và worksheets). Nếu số khác, ghi số thật vào báo cáo và tiếp tục.

## 4. Định dạng báo cáo (bắt buộc)

### 4.1 Đầu báo cáo

- Commit đã kiểm kê (`git rev-parse --short HEAD`), số dòng ứng viên backend/frontend thực tế.

### 4.2 Bảng A — theo hàm/khối (backend)

Mỗi **hàm hoặc khối cấp module** có dòng ứng viên là **một hàng**:

```text
| ID | Vị trí | Trích dẫn | Hàm/khối | Các dòng ứng viên | Loại | Ảnh hưởng v2 | Ghi chú |
|---|---|---|---|---|---|---|---|
| B001 | `app/services/study_artifact_service.py:118` | `template=card.template,` | build_effective_study_card | 118, 147 | R-RENDER | RENDER_THEO_BINDING | Thẻ deck đã cài dùng template tác giả |
```

Quy tắc từng cột:

- **ID**: `B001`, `B002`, … theo thứ tự file rồi số dòng.
- **Vị trí**: `path:line` (đường dẫn tương đối từ repo root, dấu `/`) của **một** dòng ứng viên trong hàm, đặt trong backtick.
- **Trích dẫn**: một đoạn **chép nguyên văn** từ đúng dòng ở cột Vị trí, đặt trong backtick, dài ≥ 12 ký tự, không chứa ký tự backtick. Ký tự `|` trong trích dẫn phải viết `\|`.
- **Hàm/khối**: tên hàm (`Class.method` nếu là method); khối cấp module ghi `<module>`.
- **Các dòng ứng viên**: **mọi** số dòng ứng viên của file đó nằm trong hàm này, cách nhau dấu phẩy (gồm cả dòng ở cột Vị trí).
- **Loại**: một hoặc nhiều mã, cách nhau dấu cách: `W-CREATE` (tạo Template), `W-UPDATE` (sửa nội dung/tên/position/is_default), `W-DELETE`, `R-RENDER` (đọc nội dung để render/preview/artifact), `R-NOTETYPE` (dựa vào `Template.note_type_id`/`NoteType.templates` để biết thuộc loại thẻ nào), `R-CARD` (tạo/xóa/lọc/đếm Card theo template), `R-ORDER` (dùng `position`/`is_default`), `R-SERIALIZE` (đưa template ra API), `R-COMPOSITION` (composition/phiên học), `R-DISTRIBUTION` (cài/clone/release/cutover/marketplace), `R-INTEGRATION` (Anki/Connect/MCP/import), `MODEL` (định nghĩa model/quan hệ).
- **Ảnh hưởng v2**: đúng **một** mã: `KHONG_DOI`, `NOTE_TYPE_TU_ATTACHMENT`, `RENDER_THEO_BINDING`, `GHI_PHIEN_BAN`, `TAO_CARD_THEO_ATTACHMENT`, `PHAN_PHOI`, `CAN_CLAUDE_XEM`. Không chắc thì chọn `CAN_CLAUDE_XEM`, không đoán.
- **Ghi chú**: ≤ 1 câu, chỉ mô tả điều đọc được từ code.

### 4.3 Bảng B — frontend

Cùng định dạng, ID `F001…`, Hàm/khối là tên component/hàm. Thêm mã Loại `FE-API` (gọi API), `FE-UI` (hiển thị/sửa), `FE-STUDY` (runtime học: renderer, session, restore).

### 4.4 Bảng C — dòng ứng viên bỏ qua

Dòng ứng viên không liên quan template thẻ (ví dụ Jinja/email/worksheet "template", comment, docstring, import không dùng):

```text
| Vị trí | Trích dẫn | Lý do |
|---|---|---|
| `app/services/email_service.py:12` | `render_template(...)` | UNRELATED_TEMPLATE |
```

Lý do dùng một mã: `COMMENT`, `DOCSTRING`, `IMPORT_ONLY`, `UNRELATED_TEMPLATE`, `OTHER` (kèm mô tả ngắn sau dấu `:`). (Hàng ví dụ trên chỉ minh họa định dạng, **không** có trong code thật; không chép vào báo cáo.)

### 4.5 Bảng D — tóm tắt (không có cột Vị trí)

- Số hàng theo từng mã **Loại** và từng mã **Ảnh hưởng v2**.
- Danh sách riêng mọi hàng `R-RENDER` (ID + hàm) — đây là danh sách đường render cho CT-05.
- Danh sách riêng mọi hàng `W-CREATE`/`W-UPDATE`/`W-DELETE` — danh sách writer cho seam phiên bản CT-04.

## 5. Kiểm tra (bắt buộc chạy, dán output thật)

```powershell
python docs/task/template-features/tools/verify_inventory_quotes.py docs/task/template-features/reports/GT-16_TEMPLATE_USAGE_INVENTORY.md --candidates docs/task/template-features/reports/gt16-backend.txt
python docs/task/template-features/tools/verify_inventory_quotes.py docs/task/template-features/reports/GT-16_TEMPLATE_USAGE_INVENTORY.md --candidates docs/task/template-features/reports/gt16-frontend.txt
git status --short
```

Cả hai lệnh phải in `failures=0 uncovered_candidates=0` và exit 0. Nếu còn lỗi: sửa báo cáo (không sửa script, không sửa file ứng viên), chạy lại. `git status --short` chỉ được có 3 file ở §2 (và thư mục `reports/` mới).

## 6. Ghi chú review cho Claude (không gửi Gemini)
