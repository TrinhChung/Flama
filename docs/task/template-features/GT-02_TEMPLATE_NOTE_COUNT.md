# GT-02 — `note_count` cho danh sách template của NoteType (Contract C)

- Owner: Gemini. Reviewer: Claude. Milestone: M1. Phụ thuộc: CT-00.
- Loại: backend Python, read-only, có test mới.

## 1. Bối cảnh

UI cần biết mỗi template đang được bao nhiêu note dùng (để hiển thị "N note" và cảnh báo trước khi xóa). Endpoint `GET /api/note-types/<note_type_id>/templates` đã có và gọi `flashcard_content_service.list_templates`.

Code hiện tại trong `app/services/flashcard_content_service.py` (khoảng dòng 770-782, commit `faa3c7d`):

```python
def list_templates(*, user_id: int, note_type_id: str) -> dict[str, Any]:
    note_type = _owned_note_type(user_id=user_id, note_type_id=note_type_id)
    rows = (
        Template.query.filter_by(note_type_id=note_type.id)
        .order_by(Template.position.asc())
        .all()
    )
    return {
        "items": [
            marketplace_query_service.serialize_template(row)
            for row in rows
        ]
    }
```

`Card`, `Template`, `db` đã được import ở đầu file (`from models.card import Card`, `from models.template import Template`, `from models import db`).

## 2. Mục tiêu (Contract C, kế hoạch §5.2)

Mỗi item trả thêm key `note_count: int` = số `Note` **khác nhau** có ít nhất một `Card` với `Card.template_id == template.id`. Template chưa có Card → `0`. Mọi key cũ giữ nguyên giá trị và thứ tự sắp xếp item giữ nguyên.

## 3. File được sửa

| File | Được làm gì |
|---|---|
| `app/services/flashcard_content_service.py` | Chỉ sửa thân hàm `list_templates`. |
| `tests/test_template_note_count.py` | Tạo mới. |

CẤM: `marketplace_query_service.serialize_template` (dùng ở nhiều nơi, không được thêm key vào đó), route `app/api/v1/flashcards/note_types.py` (không cần sửa), mọi file khác.

## 4. Cài đặt chính xác

```python
def list_templates(*, user_id: int, note_type_id: str) -> dict[str, Any]:
    note_type = _owned_note_type(user_id=user_id, note_type_id=note_type_id)
    rows = (
        Template.query.filter_by(note_type_id=note_type.id)
        .order_by(Template.position.asc())
        .all()
    )
    template_ids = [str(row.id) for row in rows]
    note_counts: dict[str, int] = {}
    if template_ids:
        note_counts = {
            str(template_id): int(count or 0)
            for template_id, count in db.session.query(
                Card.template_id,
                db.func.count(db.distinct(Card.note_id)),
            )
            .filter(Card.template_id.in_(template_ids))
            .group_by(Card.template_id)
            .all()
        }
    return {
        "items": [
            {
                **marketplace_query_service.serialize_template(row),
                "note_count": note_counts.get(str(row.id), 0),
            }
            for row in rows
        ]
    }
```

Đúng **một** truy vấn đếm, không lặp truy vấn theo từng template.

## 5. Test bắt buộc (`tests/test_template_note_count.py`)

Harness: sao chép nguyên `setUpClass`/`setUp`/`tearDown` của `FlashcardApiIntegrationTests` (`tests/test_flashcard_api_integration.py` dòng ~50-90). Tên lớp `TemplateNoteCountTests`. Dữ liệu tạo trực tiếp bằng model trong `with self.app.app_context():` (`NoteType`, `FieldDef`, `Template`, `Note`, `Card` từ `models.*`), `user_id=self.user_id`, `deck_id=self.deck_id`.

| Test | Dữ liệu | Kỳ vọng |
|---|---|---|
| `test_counts_distinct_notes_per_template` | NoteType 2 template T1 (pos 0), T2 (pos 1); 3 note; Card(note1,T1), Card(note2,T1), Card(note3,T1), Card(note1,T2) | `GET /api/note-types/<id>/templates` 200; items theo thứ tự T1, T2; `note_count` lần lượt 3 và 1 |
| `test_template_without_cards_is_zero` | thêm T3 không có Card | item T3 có `note_count == 0` |
| `test_existing_keys_unchanged` | như test đầu | mỗi item có đủ các key `id, note_type_id, name, front_html, back_html, shared_css, position, is_default, updated_at` với giá trị đúng như model |
| `test_other_users_note_type_is_404` | NoteType của user khác | 404, body `error == "FIELD_NOT_FOUND"` |
| `test_detail_endpoint_has_no_note_count` | `GET /api/note-types/<id>` | mọi phần tử `templates` **không** có key `note_count` |

Ghi chú: hai Card cùng `(note_id, template_id)` không thể tạo trong một occurrence vì unique `(note_id, application_id)`; không cần test trường hợp đó.

## 6. Kiểm tra

```powershell
& .\.venv\Scripts\python.exe -m unittest tests.test_template_note_count -v
& .\.venv\Scripts\python.exe -m unittest tests.test_flashcard_api_integration
& .\.venv\Scripts\python.exe scripts/run_tests.py --module flashcards --backend-only
git diff --check
git diff --stat
```

## 7. Ghi chú review cho Claude

- Xác nhận không có N+1; `db.distinct` hoạt động trên SQLite và MySQL.
- Card của template trên overlay vẫn là Card của note nguồn; với NoteType của chính user, đếm này đúng nghĩa "note của loại thẻ đang dùng template".

## 8. Prompt cho Gemini

```text
<dán nguyên khối QUY TẮC BẮT BUỘC trong docs/task/template-features/README.md §2>

Task GT-02. Đọc và làm đúng theo docs/task/template-features/GT-02_TEMPLATE_NOTE_COUNT.md
(§1–§6). Đọc thêm: AGENTS.md; app/services/flashcard_content_service.py (hàm list_templates,
_owned_note_type); app/services/marketplace_query_service.py (serialize_template, chỉ đọc);
tests/test_flashcard_api_integration.py (dòng 1-120, chỉ để sao chép harness).
Chỉ sửa thân hàm list_templates và tạo tests/test_template_note_count.py.
Chạy các lệnh ở §6, báo cáo theo mẫu README §3. Không commit.
```
