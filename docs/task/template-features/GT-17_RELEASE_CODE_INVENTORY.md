# GT-17 — Kiểm kê code phát hành/kế thừa của deck (chỉ đọc)

> Historical inventory request. Candidate raw reports were never Accepted as complete inventories. The current Codex code/contract/test audit in [backend handoff](reviews/CT-04_CT-08_BACKEND_HANDOFF_2026-10-08.md) supersedes this prerequisite; do not assign this old read-only task before Gemini FE. Counts and line numbers below describe the earlier snapshot only.
- Owner: Gemini. Reviewer: Claude. Milestone: M0 (kế hoạch v2). Phụ thuộc: không. Trạng thái: **Superseded (2026-10-08)**.
- Loại: **chỉ đọc**, đầu ra là một báo cáo Markdown. Không sửa code, test hay tài liệu khác.
- Người dùng kết quả: CT-02 (ADR-R lõi phát hành và kế thừa), CT-09 (bảng kịch bản đặc tả), CT-11 (refactor deck sang lõi chung).

## 1. Bối cảnh

Người dùng yêu cầu tách logic phát hành/kế thừa của deck thành lõi chung dùng cho nhiều loại nội dung (deck, template, …). Logic hiện nằm trong 4 service:

| File | Kích thước tại `1689a0f` |
|---|---|
| `app/services/deck_release_service.py` | 2.158 dòng |
| `app/services/deck_install_rebase_service.py` | 1.195 dòng |
| `app/services/deck_working_tree_service.py` | 489 dòng |
| `app/services/deck_auto_publish_service.py` | 191 dòng |

Cơ chế người dùng muốn dùng lại cho template: tác giả bật `DeckMarketplaceItem.auto_publish_enabled` (mặc định tắt) thì `trigger_auto_publish_for_deck_item` tự đăng bản mới khi working tree đổi; người nhận bật `DeckInstall.auto_update_enabled` (mặc định tắt) thì `process_subscriber_auto_updates` tự áp dụng bản mới nếu không có xung đột.

Package trùng lặp cũ `app/services/release/` đã được Claude xóa ở CT-10 (bằng chứng: `tools/compare_duplicate_definitions.py` cho `DIFFERENT=3 IDENTICAL=55`, không có chỗ import). Không kiểm kê phần đó.

## 2. File được tạo (không sửa file nào khác)

| File | Nội dung |
|---|---|
| `docs/task/template-features/reports/GT-17_RELEASE_CODE_INVENTORY.md` | Báo cáo theo §4. |
| `docs/task/template-features/reports/gt17-defs.txt` | Do script §3 sinh ra, không sửa tay. |
| `docs/task/template-features/reports/gt17-callers.txt` | Do script §3 sinh ra, không sửa tay. |
| `docs/task/template-features/reports/gt17-kinds.txt` | Do script §3 sinh ra, không sửa tay. |

## 3. Lệnh (chạy từ repo root, giữ nguyên lệnh)

### 3.1–3.3 Dòng ứng viên

Dùng script (mẫu tìm kiếm nằm trong script):

```powershell
python docs/task/template-features/tools/list_candidates.py gt17-defs
python docs/task/template-features/tools/list_candidates.py gt17-callers
python docs/task/template-features/tools/list_candidates.py gt17-kinds
```

| Preset | Nội dung | Tại `1689a0f` |
|---|---|---|
| `gt17-defs` (§3.1) | Dòng `def`/`class` cấp module của 4 service | 117 dòng, 4 file |
| `gt17-callers` (§3.2) | Nơi gọi 4 service từ code khác (trừ chính 4 file) | 110 dòng, 26 file |
| `gt17-kinds` (§3.3) | `entity_kind`, `"note_field"`, `"field_def"` trong 4 service | 85 dòng, 3 file |

Nếu số dòng của các preset khác số ghi trên, ghi số thật vào báo cáo và tiếp tục.

## 4. Định dạng báo cáo (bắt buộc)

Quy tắc chung cho mọi bảng có cột **Vị trí**: `path:line` trong backtick; cột **Trích dẫn** chép **nguyên văn** một đoạn ≥ 12 ký tự từ đúng dòng đó, trong backtick, không chứa backtick, `|` viết `\|`.

### Bảng A — định nghĩa (phủ toàn bộ §3.1)

```text
| ID | Vị trí | Trích dẫn | Tên | Trách nhiệm | Bảng đọc | Bảng ghi | Theo loại nội dung | Ghi chú |
|---|---|---|---|---|---|---|---|---|
| D001 | `app/services/deck_auto_publish_service.py:127` | `def trigger_auto_publish_for_deck_item(` | trigger_auto_publish_for_deck_item | AUTO_PUBLISH | DeckMarketplaceItem | DeckMarketplaceItem | KHONG | Gọi publish_release rồi process_subscriber_auto_updates |
```

- **Vị trí/Trích dẫn**: dòng `def`/`class`.
- **Trách nhiệm**: một mã: `PUBLISH`, `AUTO_PUBLISH`, `DIRTY_TRACKING`, `DIFF`, `RECONSTRUCT`, `QUERY_SERIALIZE`, `SUBSCRIBE_PIN`, `UPDATE_PREPARE`, `UPDATE_APPLY`, `CONFLICT_RESOLVE`, `AUTO_UPDATE`, `DETACH`, `SETTINGS`, `VALIDATION`, `ERROR_TYPE`, `UTIL`, `OTHER`.
- **Bảng đọc / Bảng ghi**: tên **class model** (`DeckRelease`, `DeckReleaseChange`, `DeckInstall`, …) mà chính hàm query/add/update/delete, cách nhau dấu phẩy; không có thì `-`. Chỉ ghi điều thấy trong thân hàm, không suy từ hàm được gọi.
- **Theo loại nội dung**: `CO` nếu thân hàm có so sánh/literal `entity_kind`, `"note_field"`, `"field_def"`; ngược lại `KHONG`.

### Bảng B — điểm vào từ code khác (phủ toàn bộ §3.2)

```text
| ID | Vị trí | Trích dẫn | Loại điểm vào | Hàm được gọi | Ghi chú |
|---|---|---|---|---|---|
```

- **Loại điểm vào**: `API_ROUTE`, `CLI`, `SERVICE`, `MCP`, `CONNECT`, `JOB`, `OTHER`.
- **Hàm được gọi**: tên hàm của 4 service xuất hiện trong dòng đó.
- Một dòng ứng viên = một hàng.

### Bảng C — nhánh theo loại nội dung (phủ toàn bộ §3.3)

```text
| ID | Vị trí | Trích dẫn | Hàm chứa | Mục đích |
|---|---|---|---|---|
```

- **Mục đích**: một mã: `DIFF_PLAN`, `RECONSTRUCT`, `CONFLICT_DETECT`, `APPLY_OVERLAY`, `MEMBERSHIP`, `SERIALIZE`, `VALIDATION`, `DIRTY_TRACKING`, `OTHER`.

### Bảng D — test (không bắt buộc kiểm phủ)

Liệt kê file test trong `tests/` gọi 4 service hoặc route `/releases`, `/installations/`: mỗi hàng `| Vị trí | Trích dẫn | File test | Tên test | Điểm vào được gọi |` với Vị trí là dòng `def test_...`. Lệnh tìm file gợi ý:

```powershell
git grep -l -E "deck_release_service|deck_install_rebase_service|deck_auto_publish_service|deck_working_tree_service|/releases|/installations/" -- "tests/*.py"
```

### Mục E — tóm tắt (không có cột Vị trí)

- Số định nghĩa theo **Trách nhiệm**; số điểm vào theo **Loại điểm vào**; số nhánh theo **Mục đích**.
- Danh sách hàm vừa CO theo loại nội dung vừa là PUBLISH/DIFF/RECONSTRUCT/UPDATE_PREPARE/UPDATE_APPLY/CONFLICT_RESOLVE (ứng viên tách adapter).
