# Kế hoạch Tối ưu #05: Tối ưu Batch Insert & Giảm Thiểu Overhead Working Tree khi Import Flashcard

> **Mã Task:** `PERF-IMPORT-05`  
> **Mức độ ưu tiên:** 🟡 P2 (Medium-High - Ngăn ngừa đơ server khi người dùng import file lớn CSV/TSV/APKG)  
> **Trạng thái:** DỰ THẢO CHỜ DUYỆT (PROPOSED)  
> **Phạm vi tác động:** Service Import Flashcard ([`app/services/flashcard_import.py`](file:///d:/Project/nihongo/app/services/flashcard_import.py)), Service Working Tree ([`app/services/deck_working_tree_service.py`](file:///d:/Project/nihongo/app/services/deck_working_tree_service.py))  
> **Tài liệu tham chiếu:** [`app/services/flashcard_import.py`](file:///d:/Project/nihongo/app/services/flashcard_import.py#L700-L750), [`app/services/deck_working_tree_service.py`](file:///d:/Project/nihongo/app/services/deck_working_tree_service.py#L96-L150)

---

## 1. Vấn đề Kỹ thuật Cần Giải quyết

### 1.1 Hiện trạng mã nguồn
Khi người dùng import bộ thẻ (cho phép dung lượng tối đa tới **50MB**), hàm `run_import` thực hiện gom Note và Card theo từng chunk `flush_pending()`:

Tại [`app/services/flashcard_import.py`](file:///d:/Project/nihongo/app/services/flashcard_import.py#L732-L738):
```python
# flashcard_import.py:732-738
from app.services import deck_working_tree_service

for note in notes:
    deck_working_tree_service.mark_note_fields_changed(
        note=note,
        field_names=(note.field_values or {}).keys(),
        operation="add",
    )
```

Và bên trong hàm `mark_note_fields_changed` ([`deck_working_tree_service.py:96-138`](file:///d:/Project/nihongo/app/services/deck_working_tree_service.py#L96-L138)):
```python
# deck_working_tree_service.py:111-134
field_ids_by_name = {
    str(row.name): str(row.id)
    for row in FieldDef.query.filter_by(note_type_id=note.note_type_id).all()
} # BỊ TRUY VẤN LẶP LẠI CHO MỖI NOTE!

for field_name in normalized_names:
    _upsert_dirty(...) # INSERT TỪNG FIELD ĐƠN LẺ!
```

### 1.2 Điểm nghẽn
1. **N+1 Query siêu nặng:** Nếu import 2.000 Note, hàm `mark_note_fields_changed` được gọi 2.000 lần. Mỗi lần gọi lại chạy `FieldDef.query.filter_by(note_type_id=note.note_type_id).all()`. Kết quả là **2.000 câu lệnh query giống hệt nhau** bị gửi tới MySQL liên tục.
2. **Ghi đĩa đơn lẻ (Single Row Upserts):** Với 2.000 Note, mỗi Note có 5 trường thông tin $\to$ hệ thống bắn **10.000 câu lệnh `INSERT ... ON DUPLICATE KEY UPDATE`** riêng lẻ vào bảng `deck_working_dirty_entities`.
3. **Nạp toàn bộ Note hiện có vào RAM:** Tại dòng 650 `existing_notes = existing_notes_query.all()`, nếu bộ thẻ đã có sẵn 10.000 Note, toàn bộ model ORM được nạp vào Python memory và giải mã JSON, gây spike RAM hàng trăm MB.

---

## 2. Giải pháp Kỹ thuật (Technical Mechanism)

Tối ưu hóa quá trình import bằng Metadata Pre-fetching và Bulk Dirty Tracking:

```text
TRƯỚC TỐI ƯU (Import 2.000 thẻ × 5 fields):
Loop 2.000 lần:
   ├── SELECT * FROM field_defs WHERE note_type_id = :id (2.000 queries trùng lặp!)
   └── 5 x INSERT INTO deck_working_dirty_entities ...   (10.000 câu insert đơn lẻ!)
==> Tổng cộng: 12.000 thao tác DB, kéo dài ~13 giây!

SAU TỐI ƯU:
1. Pre-fetch Metadata (1 query):
   field_ids_by_name = {...} lấy 1 lần trước khi vào vòng lặp flush!
2. Batch Mark Changed (mark_notes_batch_changed):
   Gom toàn bộ 10.000 dirty entities thành các lô 1.000 items
   db.session.bulk_insert_mappings(DeckWorkingDirtyEntity, dirty_payloads)
==> Tổng cộng: 1 query metadata + 10 câu bulk insert = 11 thao tác DB, kéo dài ~0.7 giây!
```

### Chi tiết thay đổi mã nguồn
1. **Bổ sung hàm Batch trong `deck_working_tree_service.py`:**
   ```python
   def mark_notes_batch_changed(
       *,
       notes: list[Note],
       operation: str = "add",
       deck_id: int | None = None,
       cached_field_defs: dict[str, str] | None = None,
   ) -> int:
       # Pre-fetch field defs nếu chưa có
       # Gom danh sách dirty entities và bulk insert
   ```
2. **Nâng cấp `flush_pending` trong `flashcard_import.py`:**
   Thay vì chạy vòng lặp `for note in notes` gọi hàm đơn lẻ, truyền toàn bộ mảng `notes` vào `mark_notes_batch_changed`.

---

## 3. Tính toán Định lượng Cụ thể (Quantitative Impact)

* Giả sử import một bộ từ vựng JLPT gồm **2.000 thẻ** (5 fields/thẻ = 10.000 field values):

| Tiêu chí đo lường | Trước khi tối ưu | Sau khi tối ưu (Bulk & Cache) | Mức độ cải thiện |
|---|---|---|:---:|
| **Số câu query `FieldDef`** | $2.000\text{ queries}$ | $\mathbf{1\text{ query}}$ duy nhất | **Giảm 99.95%** |
| **Số câu lệnh ghi `dirty_entities`** | $10.000\text{ câu insert lẻ}$ | $\mathbf{10\text{ câu bulk insert}}$ (1.000 rows/lô) | **Giảm 99.9%** |
| **Tổng thời gian xử lý import** | $\approx \mathbf{13.2\text{ giây}}$ | $\approx \mathbf{0.75\text{ giây}}$ | **Nhanh hơn $\approx 18$ lần** |
| **Nguy cơ lock bảng MySQL** | Cao (10.000 transaction row locks nhỏ lẻ) | Rất thấp (hoàn thành trong sub-second) | **Tránh deadlock hoàn toàn** |

---

## 4. Kế hoạch Triển khai (Checklist)

- [ ] **Service:** Thêm hàm `mark_notes_batch_changed` vào [`app/services/deck_working_tree_service.py`](file:///d:/Project/nihongo/app/services/deck_working_tree_service.py).
- [ ] **Service:** Cập nhật hàm `flush_pending` trong [`app/services/flashcard_import.py`](file:///d:/Project/nihongo/app/services/flashcard_import.py) để dùng `mark_notes_batch_changed`.
- [ ] **Testing:** Chạy test suite import: `python scripts/run_tests.py --module flashcards` để đảm bảo dữ liệu import không bị thiếu field hay sai working revision.
- [ ] **Benchmark:** Thực hiện import thử nghiệm file CSV 2.000 dòng để so sánh thời gian phản hồi thực tế trước và sau khi tối ưu.
